# -*- coding: utf-8 -*-
"""
Test script to get the configuration from a parsed configuration file
"""
import argparse
from pathlib import Path
import re

import jinja2
import yaml

# Configure ninja2
file_folder = Path(__file__).absolute().parent
config_files_path = Path(file_folder, '../data/config')
loader = jinja2.FileSystemLoader(searchpath=config_files_path)
jinja_env = jinja2.Environment(
    loader=loader,
    trim_blocks=True,
    lstrip_blocks=True
)

secrets_dir = Path(file_folder, '../data/secrets')
common_dir = Path(file_folder, '../data/common')

index_regex = re.compile(r'\[(\d+)\]')


# Add scs-ref tag constructor for pyyaml
def construct_scs_ref(loader, node):
    """PyYaml constructor for scs-ref tags"""
    ref = node.value

    # expand scs variables
    ref = ref.replace('${scs-secrets}', secrets_dir.as_posix())
    ref = ref.replace('${scs-common}', common_dir.as_posix())

    # TODO: How to handle references to files in the same dir?
    ref_parts = ref.split('#')

    if len(ref_parts) == 1:
        file_path = ref_parts
        attribute_loc = None
    else:
        file_path, attribute_loc = ref_parts

    file_data = load_yaml(file_path)

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


yaml.SafeLoader.add_constructor('!scs-ref', construct_scs_ref)


def valid_config_path(relative_path, parser):
    """Check if the given path is valid and return the path"""
    path = Path(config_files_path, relative_path)
    if path.is_file() and not path.name.endswith('scs-env.yaml'):
        return relative_path
    else:
        parser.error('Invalid path provided!')


def get_args():
    """Get the input arguments of the script"""
    aparser = argparse.ArgumentParser(
        description="Script to test the parsing of configuration files"
    )
    aparser.add_argument(
        'path',
        help="Path, relative to the config file directory",
        type=lambda x: valid_config_path(x, aparser)
    )
    args = aparser.parse_args()
    return args


def load_yaml(path):
    """Load the YAML data from the given path"""
    with open(path, 'r', encoding='utf-8') as yaml_file:
        return yaml.safe_load(yaml_file)


def get_env(relative_path):
    """
    Get all environment variables for the given path
    """
    # Note: At this moment only loads the accompanying scs-env file
    path = Path(config_files_path, relative_path)
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
    args = get_args()

    env = get_env(args.path)

    print(render_config_file(args.path, env))


if __name__ == "__main__":
    main()
