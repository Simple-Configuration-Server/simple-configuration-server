"""
Script to validate an SCS configuration, by sing an auth-less Flask test client
and testing requests to every resource


Copyright 2022 Tom Brouwer

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""
import os
from pathlib import Path
from typing import Any
from json import JSONDecodeError
import copy

from flask import Blueprint
import fastjsonschema
from yaml import YAMLError

import scs
from scs import tools, auth, yaml

current_dir = Path(__file__).parent.absolute()

auth_dummy = Blueprint('dummy_auth', __name__)


def constructor(
        loader: scs.yaml.Loader, node: scs.yaml.Node, return_data=None
        ) -> Any:
    """
    Constructor that can be used with functools.partial to create a PyYaml
    constructor function with a specific return value.
    """
    return return_data


def load_script_configuration() -> dict:
    """
    Load the scs-validate.yaml configuration file
    """
    schema_path = Path(current_dir, 'scs-validate.SCHEMA.yaml')
    configuration_schema = scs.yaml.safe_load_file(schema_path)
    config_dir = Path(os.environ['SCS_CONFIG_DIR']).absolute()
    script_conf_path = Path(config_dir, 'scs-validate.yaml')
    # Add endpoints._default to the configuration, so the script can load the
    # 'default' endpoint test definition based on the JSON schema
    if script_conf_path.is_file():
        configuration_data = scs.yaml.safe_load_file(script_conf_path)
        configuration_data.setdefault('endpoints', {})
        configuration_data['endpoints']['_default'] = {}
    else:
        print(
            'scs-validate.yaml not found, using default settings',
            flush=True,
        )
        configuration_data = {'endpoints': {'_default': {}}}
    return fastjsonschema.validate(configuration_schema, configuration_data)


def get_test_definition(
        path: str, default: dict, endpoints: dict
        ) -> bool | dict:
    """
    Get the test definition for the given path, based on the endpoint
    configurations matching the path

    Args:
        path:
            The path to test (e.g. /configs/test.json)

        default:
            The default test definition, as defined in the scs-validate JSON
            schema

        endpoints:
            The configuration under the 'endpoints' property of the config file

    Returns:
        The test definition for this endpoint. If wildcard paths
        are defined, these are applied first, with definitions for longer
        paths (more specific) taking precedence over definitions for shorter
        ones
    """
    matching_config_paths = []
    for config_path in endpoints.keys():
        if tools.contains_wildcard(config_path):
            pattern = tools.build_pattern_from_path(config_path)
            if pattern.match(path):
                matching_config_paths.append(config_path)
        else:
            if path.lower() == config_path.lower():
                matching_config_paths.append(config_path)

    # First apply shorter (less specific) configurations
    matching_config_paths.sort(key=lambda k: len(k))

    path_config = copy.deepcopy(default)
    for config_path in matching_config_paths:
        endpoint_config = endpoints[config_path]

        if endpoint_config is False:
            path_config = False
        else:
            if path_config is False:
                path_config = copy.deepcopy(endpoint_config)
            else:
                for key, value in endpoint_config.items():
                    if key not in path_config:
                        path_config[key] = copy.deepcopy(value)
                    else:
                        path_config[key].update(
                            copy.deepcopy(value)
                        )

    return path_config


def validate_user_configuration(path: Path):
    """
    Validates if the user configuration matches the scs-users schema.

    Raises:
        JsonSchemaValueException in case the users file fails validation
    """
    dummy_secret_constructor = yaml.SCSSimpleValueConstructor(
        tag='!scs-secret',
        value='DUMMY_REFERENCED_SECRET',
    )
    auth._SCSUsersFileLoader.add_constructor(
        dummy_secret_constructor.tag, dummy_secret_constructor.construct
    )
    scs_users = yaml.load_file(path, loader=auth._SCSUsersFileLoader)
    auth.validate_user_configuration(scs_users)


if __name__ == '__main__':
    print('Validating SCS configuration...', flush=True)
    scs_config = scs.load_application_configuration()
    script_config = load_script_configuration()
    default_test_definition = script_config['endpoints'].pop('_default')

    # Override configuration with validation specific properties
    for key, value in script_config['scs_configuration'].items():
        scs_config[key] = value

    # Since the 'auth' module is not used during validation, the 'scs-users'
    # file is not valided by SCS. Therefore, validate it here first.
    auth_blueprint = scs_config['auth']['blueprint']
    if auth_blueprint == 'scs.auth.bp':
        user_config_path = Path(
            scs_config['auth']['options']['users_file']
        )
        if user_config_path.is_file():
            validate_user_configuration(user_config_path)

    # For validation, auth is disabled, and all !scs-secret references are
    # replaced by a fixed value, because secrets are not included in
    # repositories with configuration files
    scs_config['auth']['blueprint'] = 'validate.auth_dummy'
    scs_config['extensions']['constructors'].append(
        {
            'name': 'scs.yaml.SCSSimpleValueConstructor',
            'options': {
                'tag': '!scs-secret',
                'value': 'DUMMY_REFERENCED_SECRET',
            }
        }
    )

    # re-validate the configuration with overriden properties
    scs_config = scs.validate_configuration(scs_config)

    app = scs.create_app(configuration=scs_config)
    if not script_config['handle_errors']:
        app.testing = True
    client = app.test_client()
    client.environ_base = {'REMOTE_ADDR': '127.0.0.1'}

    # In case secrets are not allowed, validate that these are indeed not
    # present
    if not script_config['allow_secrets']:
        if 'secrets' in scs_config['directories']:
            secrets_dir = Path(scs_config['directories']['secrets'])
            if secrets_dir.is_dir():
                assert not any(secrets_dir.iterdir()), (
                    'Secrets directory is not emtpy, even though '
                    'allow_secrets: false is set'
                )

    # Build the list of paths to test, and check if these are in-line with any
    # configured overrides
    all_test_paths = [
        f'/configs/{p.lstrip("/")}'.lower()
        for p in scs.configs.get_relative_endpoint_paths()
    ]

    configured_endpoints = script_config['endpoints']
    invalid_paths = set()
    for path in configured_endpoints.keys():
        if tools.contains_wildcard(path):
            pattern = tools.build_pattern_from_path(path)
            if not any([pattern.match(url) for url in all_test_paths]):
                invalid_paths.add(path)
        else:
            if path.lower() not in all_test_paths:
                invalid_paths.add(path)

    if invalid_paths:
        raise ValueError(
            'Endpoints configuration in scs-validate.yaml contains invalid '
            f'paths: {invalid_paths}'
        )

    test_results = {}
    for path in all_test_paths:
        definition = get_test_definition(
            path, default_test_definition, configured_endpoints
        )
        if not definition:
            continue

        if definition['request']['method'] == 'GET':
            response = client.get(
                path
            )
        else:
            response = client.post(
                path,
                json=definition['request']['json'],
            )

        base_message = f'Validation of path {path} failed:'

        validate_status = definition['response'].get('status')
        if validate_status is not None:
            assert response.status_code == validate_status, \
                f'{base_message} Wrong status code {response.status_code}'
        else:
            assert response.status_code < 400, \
                f'{base_message} Wrong status code {response.status_code}'

        validate_headers = definition['response'].get('headers')
        if validate_headers is not None:
            for key, value in validate_headers.items():
                actual_value = response.headers.get(key)
                assert actual_value == value, \
                    f'{base_message} Wrong header \'{key}: {actual_value}\''

        validate_text = definition['response'].get('text')
        if validate_text is not None:
            assert response.text == validate_text, \
                f'{base_message} Wrong text response \'{response.text}\''

        parse_as = definition['response'].get('format')

        validate_json = definition['response'].get('json')
        parse_json = (parse_as == 'json' or validate_json is not None)
        if parse_json:
            try:
                data = response.get_json(force=True)
            except JSONDecodeError:
                print(
                    f'{base_message} Response could not be parsed as JSON',
                    flush=True,
                )
                raise
            if validate_json is not None:
                assert data == validate_json, \
                    f'{base_message} Wrong JSON response {data}'

        validate_yaml = definition['response'].get('yaml')
        parse_yaml = (parse_as == 'yaml' or validate_yaml is not None)
        if parse_yaml:
            try:
                data = scs.yaml.safe_load(response.text)
            except YAMLError:
                print(
                    f'{base_message} Response could not be parsed as YAML',
                    flush=True,
                )
                raise
            if validate_yaml is not None:
                assert data == validate_yaml, \
                    f'{base_message} Wrong YAML response {data}'

    print('SCS configuration validation succesful!', flush=True)
