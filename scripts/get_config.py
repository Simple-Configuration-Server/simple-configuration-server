# -*- coding: utf-8 -*-
"""
Test script to get the configuration from a parsed configuration file
"""
import argparse
from pathlib import Path
import re
import secrets
import os

import jinja2
import yaml

# Configure ninja2
file_folder = Path(__file__).absolute().parent

index_regex = re.compile(r'\[(\d+)\]')
env_variable_pattern = re.compile(r'\$\{([^}^{]+)\}')


# Add scs-ref tag constructor for pyyaml
def construct_scs_ref(loader, node):
    """PyYaml constructor for scs-ref tags"""
    ref = node.value

    # TODO: How to handle references to files in the same dir?
    ref_parts = ref.split('#')

    if len(ref_parts) == 1:
        file_path = ref_parts
        attribute_loc = None
    else:
        file_path, attribute_loc = ref_parts

    # Resolve full path
    contains_secrets = False
    if node.tag == '!scs-secret':
        file_path = Path(secrets_path, file_path)
        contains_secrets = True
    elif node.tag == '!scs-common':
        file_path = Path(common_path, file_path)
    else:
        file_path = Path(loader.filepath.absolute().parent, file_path)

    file_data = load_yaml(file_path, secrets=contains_secrets)

    if not attribute_loc:
        return file_data

    # TODO: How to support dots in variable names?
    loc_levels = attribute_loc.split('.')
    level_data = file_data
    for level in loc_levels:
        if match := index_regex.match(level):
            index = int(match.group(1))
            level_data = level_data[index]
        else:
            level_data = level_data[level]

    return level_data


def construct_secret(loader, node):
    """
    Constructs a random secret for a node, using the secrets.token_urlsafe
    function
    """
    loader.file_properties['secrets_parsed'] = True

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


class BaseSCSConfigLoader(yaml.SafeLoader):
    # To keep constructors different for secrets files and other files
    pass


BaseSCSConfigLoader.add_constructor('!scs-relative', construct_scs_ref)
BaseSCSConfigLoader.add_constructor('!scs-secret', construct_scs_ref)
BaseSCSConfigLoader.add_constructor('!scs-common', construct_scs_ref)
BaseSCSConfigLoader.add_constructor('!scs-expand-env', expand_env_vars)


class BaseSCSSecretsLoader(yaml.SafeLoader):
    # This class will only have a constructor to generate secrets, and variable
    # To indicate if they have been generated
    pass


BaseSCSSecretsLoader.add_constructor('!scs-gen-secret', construct_secret)
BaseSCSConfigLoader.add_constructor('!scs-secret', construct_scs_ref)


def get_args():
    """Get the input arguments of the script"""
    aparser = argparse.ArgumentParser(
        description="Script to test the parsing of configuration files"
    )
    aparser.add_argument(
        'settings_folder',
        help=(
            "Path of the folder containing the 'scs_auth' and 'scs_conf'"
            " files"
        ),
        type=str
    )
    aparser.add_argument(
        'path',
        help="Path, relative to the config file directory",
        type=str
    )
    args = aparser.parse_args()
    return args


def load_yaml(path, secrets=False):
    """Load the YAML data from the given path"""
    # A class is created for each load, so variables can be stored, to be
    # passed to the parsing function, and/or read afterwards
    if secrets:
        class Loader(BaseSCSSecretsLoader):
            file_properties = {'secrets_parsed': False}
    else:
        class Loader(BaseSCSConfigLoader):
            filepath = path

    with open(path, 'r', encoding='utf-8') as yaml_file:
        data = yaml.load(yaml_file, Loader)

    if secrets and Loader.file_properties['secrets_parsed']:
        with open(path, 'w', encoding='utf8') as yaml_file:
            yaml.dump(data, yaml_file, sort_keys=False)

    return data


def get_env(relative_path):
    """
    Get all environment variables for the given path
    """
    # Note: At this moment only loads the accompanying scs-env file
    path = Path(config_path, relative_path)
    env_file_name = path.name + '.scs-env.yaml'
    env_file_path = Path(path.parent, env_file_name)

    print(env_file_path)
    if env_file_path.is_file():
        return load_yaml(env_file_path)
    else:
        return {}


def render_config_file(relative_path, env):
    """
    Render the config file with the given environment
    """
    template = jinja_env.get_template(relative_path)
    return template.render(**env)


def main():
    global config_path, common_path, secrets_path, jinja_env
    args = get_args()

    # First load the configuration
    print('################ Configuration ###################')
    settings_path = Path(file_folder, args.settings_folder)
    config_data = load_yaml(Path(settings_path, 'scs_conf.yaml'))
    print(config_data)

    config_path = config_data['directories']['config']
    common_path = config_data['directories']['common']
    secrets_path = config_data['directories']['secrets']
    loader = jinja2.FileSystemLoader(
        searchpath=config_path
    )
    jinja_env = jinja2.Environment(
        loader=loader,
        trim_blocks=True,
        lstrip_blocks=True
    )

    # Load the user data
    print('################ Accounts ###################')
    print(load_yaml(Path(settings_path, 'scs_auth.yaml')))

    env = get_env(args.path)
    print('################ Config Data ###################')
    print(render_config_file(args.path, env))


if __name__ == "__main__":
    main()
