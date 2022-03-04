# -*- coding; utf-8 -*-
"""
Flask Blueprint containing the code for the configs/ endpoints, that loads the
configuration data and returns the formatted data
"""
from pathlib import Path
import re
import os
from functools import partial
import copy

from flask import (
    Blueprint, render_template, request, abort, g
)
from flask.blueprints import BlueprintSetupState

from . import yaml

bp = Blueprint('configs', __name__, url_prefix='/configs')

# Configure ninja2
file_folder = Path(__file__).absolute().parent
url_structure = {}

@bp.record
def init(setup_state: BlueprintSetupState):
    """
    Initializes the configs/* endpoints

    Args:
        setup_state:
            The .options attribute of this (options passed to 
            register_blueprint function) should contain the following dict
            data:
                directories: dict; containing:
                    common, config, secrets: str


    """
    global config_basepath, common_basepath, secrets_basepath

    # Load setup_state options
    opts = setup_state.options
    config_basepath = Path(opts['directories']['config']).absolute()
    common_basepath = Path(opts['directories']['common']).absolute()
    secrets_basepath = Path(opts['directories']['secrets']).absolute()
    check_templates = opts['template_check_during_init']

    _initialize_yaml_loaders(
        common_dir=common_basepath,
        secrets_dir=secrets_basepath
    )

    # Configure template rendering options
    setup_state.app.jinja_options.update({
        # Make sure if statements and for-loops do not add unnecessary new lines
        'trim_blocks': True,
        'lstrip_blocks': True,
        # Keep traling newlines in configuration files
        'keep_trailing_newline': True,
    })

    bp.template_folder = config_basepath

    envs = get_config_envs()
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

        if check_templates:
            testenv = copy.deepcopy(envdata)
            serialize_secrets(testenv)
            template = setup_state.app.jinja_env.get_template(
                relative_url.lstrip('/')
            )
            template.render(**testenv)


def _initialize_yaml_loaders(*, common_dir: Path, secrets_dir: Path):
    """
    Initialize the loader with the right constructors
    """
    ENV_FILE_CONSTRUCTORS = [
        yaml.SCSRelativeConstructor(),
        yaml.SCSSecretConstructor(secrets_dir=secrets_dir),
        yaml.SCSCommonConstructor(common_dir=common_dir),
        yaml.SCSExpandEnvConstructor(),
    ]

    SECRET_FILE_CONSTRUCTORS = [
        yaml.SCSGenSecretConstructor(),
    ]

    for constructor in ENV_FILE_CONSTRUCTORS:
        yaml.SCSEnvFileLoader.add_constructor(
            constructor.tag, constructor.construct
        )

    for constructor in SECRET_FILE_CONSTRUCTORS:
        yaml.SCSSecretFileLoader.add_constructor(
            constructor.tag, constructor.construct
        )


def contains_keys_with_dots(data):
    """
    Verify that there are no dots in the keynames of dicts embedded in the data

    Raises:
        KeyError in case keynames contain dots
    """
    if isinstance(data, dict):
        for key, value in data.items():
            if '.' in key:
                return True
            if contains_keys_with_dots(value):
                return True
    elif isinstance(data, list):
        for item in data:
            if contains_keys_with_dots(item):
                return True

    return False


def load_env_file(relative_path: str) -> dict:
    """
    Load the data from the given env file, if it exists
    """
    path = Path(config_basepath, relative_path)
    if not path.is_file():
        return {}

    return yaml.load(path, loader=yaml.SCSEnvFileLoader)


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


def serialize_secrets(data: dict | list) -> list[str]:
    """
    Serialize all secrets in the data

    Args:
        env_data:
            The environment data, possible containg SCSSecret objects. This
            will be serialized IN PLACE

    Returns:
        The id's of the secrets that were serialized
    """
    secret_ids = set()
    if isinstance(data, list):
        for i, item in enumerate(data):
            if isinstance(item, yaml.SCSSecret):
                secret_ids.add(item.id)
                data[i] = item.value
            else:
                serialize_secrets(item)
    elif isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                serialized_secrets = serialize_secrets(value)
                secret_ids.update(serialized_secrets)
            elif isinstance(value, yaml.SCSSecret):
                secret_ids.add(value.id)
                data[key] = value.value

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
    try:
        response = render_template(path.lstrip('/'), **env)
        g.add_audit_event(event_type='config_loaded')
        if secret_ids:
            g.add_audit_event(
                event_type='secrets_loaded', secrets=list(secret_ids),
            )
        return response
    except Exception:
        abort(400)
