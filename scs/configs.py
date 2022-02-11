# -*- coding; utf-8 -*-
"""
Flask Blueprint containing the code for the configs/ endpoints, that loads the
configuration data and returns the formatted data
"""
import argparse
from pathlib import Path
import re
import secrets
import os
from functools import partial

import yaml
import copy

from flask import (
    Blueprint, render_template, request, abort, current_app, Flask
)

bp = Blueprint('configs', __name__, url_prefix='/configs')

# Configure ninja2
file_folder = Path(__file__).absolute().parent
url_structure = {}

index_regex = re.compile(r'\[(\d+)\]')
env_variable_pattern = re.compile(r'\$\{([^}^{]+)\}')


class _ParsedFileCache:
    """
    Object to store the parsed contents of a YAML file during the construction
    of envdata for each path
    """
    def __init__(self):
        self.cache = {}

    def clear(self):
        self.cache = {}

    def get_file(self, path: os.PathLike):
        abspath = Path(path).absolute().as_posix()
        return self.cache.get(abspath)

    def add_file(self, path: os.PathLike, data):
        abspath = Path(path).absolute().as_posix()
        self.cache[abspath] = data


filecache = _ParsedFileCache()


class SCSSecret:
    """
    A secret class, used to track which secrets end-up in the final Env, so
    secret access can be logged.

    Attributes:
        id:
            A unique identifier describing the secrets. This will be logged in
            the access logs
        value:
            The value of the secret
    """
    def __init__(self, id_: str, value):
        self.id = id_
        self.value = value


def construct_scs_ref(loader, node):
    """PyYaml constructor for scs-ref tags"""
    ref = node.value

    ref_parts = ref.split('#')

    if len(ref_parts) == 1:
        file_path = ref_parts
        attribute_loc = None
    else:
        file_path, attribute_loc = ref_parts

    # Resolve full path
    is_secrets_file = False
    if node.tag == '!scs-secret':
        file_path = Path(secrets_basepath, file_path)
        is_secrets_file = True
    elif node.tag == '!scs-common':
        file_path = Path(common_basepath, file_path)
    else:
        file_path = Path(loader.filepath.absolute().parent, file_path)

    file_data = load_yaml(file_path, is_secrets_file=is_secrets_file)

    if not attribute_loc:
        ref_data = file_data
    else:
        # TODO: How to support dots in variable names?
        loc_levels = attribute_loc.split('.')
        level_data = file_data
        for level in loc_levels:
            if match := index_regex.match(level):
                index = int(match.group(1))
                level_data = level_data[index]
            else:
                level_data = level_data[level]
        ref_data = level_data

    if is_secrets_file and not isinstance(ref_data, SCSSecret):
        ref_data = SCSSecret(ref, ref_data)

    return ref_data


def construct_secret(loader, node):
    """
    Constructs a random secret for a node, using the secrets.token_urlsafe
    function
    """
    loader.contents_changed = True

    return secrets.token_urlsafe(32)


def get_env_var(match):
    """
    Return the environment variable for the 'env_variable_pattern' match
    """
    env_var_name = match.group(1)
    try:
        return os.environ[env_var_name]
    except KeyError:
        raise KeyError(f'Environment Variable {env_var_name} not defined!')\
            from None


def expand_env_vars(loader, node):
    """
    Constructs a random secret for a node, using the secrets.token_urlsafe
    function
    """
    return env_variable_pattern.sub(get_env_var, node.value)


class SCSConfigLoader(yaml.SafeLoader):
    def __init__(self, *args, filepath: os.PathLike = None, **kwargs):
        # Filepath is required for relative loading,
        # and the loaded secrets need to be tracked
        self.filepath = filepath
        self.contents_changed = False
        super().__init__(*args, **kwargs)


SCSConfigLoader.add_constructor('!scs-relative', construct_scs_ref)
SCSConfigLoader.add_constructor('!scs-secret', construct_scs_ref)
SCSConfigLoader.add_constructor('!scs-common', construct_scs_ref)
SCSConfigLoader.add_constructor('!scs-expand-env', expand_env_vars)


class SCSSecretsLoader(yaml.SafeLoader):
    def __init__(self, *args, **kwargs):
        self.contents_changed = False
        super().__init__(*args, **kwargs)


SCSSecretsLoader.add_constructor('!scs-gen-secret', construct_secret)


def load_yaml(path: os.PathLike, is_secrets_file=False) -> dict:
    """
    Load the YAML file from the given directory id
    """
    # Try to load from cache
    if (filedata := filecache.get_file(path)) is not None:
        data = filedata
        return data

    with open(path, 'r', encoding='utf8') as yamlfile:
        if is_secrets_file:
            loader = SCSSecretsLoader(yamlfile)
        else:
            loader = SCSConfigLoader(yamlfile, filepath=path)

        data = loader.get_single_data()

        filecache.add_file(path, data)

        return data


def load_env_file(relative_path: str) -> dict:
    """
    Load the data from the given env file, if it exists
    """
    path = Path(config_basepath, relative_path)
    if not path.is_file():
        return {}

    return load_yaml(path)


def get_env_file_hierarchy(relative_path: str) -> list[str]:
    """Gets all possible relative paths of env files"""
    path_parts = relative_path.split('/')

    ordered_envfiles = ['scs-env.yaml']
    envfile_basepath = ''
    for part in path_parts[:-1]:
        envfile_basepath += f'{part}/'
        ordered_envfiles.append(envfile_basepath + '/scs-env.yaml')
    ordered_envfiles.append(relative_path + '.scs-env.yaml')

    return ordered_envfiles


def serialize_secrets(env_data: dict) -> list[str]:
    """
    Serialize all secrets in the env_data

    Args:
        env_data:
            The environment data, possible containg SCSSecret objects. This
            will be serialized IN PLACE

    Returns:
        The id's of the secrets that were serialized
    """
    secret_ids = set()
    for key, value in env_data.items():
        if isinstance(value, dict):
            serialized_secrets = serialize_secrets(value)
            secret_ids.update(serialized_secrets)
        elif isinstance(value, SCSSecret):
            secret_ids.add(value.id)
            env_data[key] = value.value

    return secret_ids


def load_env(relative_path):
    """
    Load the full environment for the given relative path
    """
    combined_env = {}
    rel_env_file_paths = get_env_file_hierarchy(relative_path)

    for rel_path in rel_env_file_paths:
        data = load_env_file(rel_path)
        combined_env.update(data)

    return combined_env


def get_config_envs():
    """
    Creates a dict with all config file paths, and the env data of each path
    """
    # 1. Load all paths
    config_template_paths = []
    for path in config_basepath.rglob('*'):
        if path.is_file() and not path.name.endswith('scs-env.yaml'):
            config_template_paths.append(path)

    # 2. Load env for each path
    config_envs = {}
    for path in config_template_paths:
        relative_template_path = \
            path.as_posix().removeprefix(config_basepath.as_posix())

        config_envs[relative_template_path] = load_env(
            relative_template_path.lstrip('/')
        )

    return config_envs


def view_config_file(path: str, envdata: dict):
    """
    Flask view for the file at the given path, with the given envdata
    """
    env = copy.deepcopy(envdata)
    if request.method == 'POST':
        env.update(request.get_json(force=True))
    secret_ids = serialize_secrets(env)
    print(secret_ids)
    try:
        return render_template(path.lstrip('/'), **env)
    except Exception:
        # return (
        #     "Error Parsing Config Template, Please check request body",
        #     400,
        # )
        abort(400)


def init_config_endpoints(
        *, config_dir: os.PathLike, common_dir: os.PathLike,
        secrets_dir: os.PathLike
        ):
    """
    This builds the URL structure of the configs/* endpoint, validates if all
    references in YAML files can be built, does an initial parsing of the
    config files to check the templating syntax, and initializes any secrets
    in the files, with the !scs-gen-secret tag.
    """
    global config_basepath, common_basepath, secrets_basepath

    config_basepath = Path(config_dir).absolute()
    common_basepath = Path(common_dir).absolute()
    secrets_basepath = Path(secrets_dir).absolute()

    bp.template_folder = config_basepath

    envs = get_config_envs()
    filecache.clear()
    for relative_url, envdata in envs.items():
        bp.add_url_rule(
            relative_url,
            endpoint=relative_url.replace('.', '_'),
            view_func=partial(
                view_config_file,
                path=relative_url,
                envdata=envdata
            ),
            methods=['GET', 'POST'],
        )

        # Below doesn't work, since we cannot access the app. The proper
        # Blueprint initialization mechanisms need to be used for this.
        # testenv = copy.deepcopy(envdata)
        # serialize_secrets(testenv)
        # template = bp.jinja_env.get_template(relative_url.lstrip('/'))
        # template.render(**testenv)
