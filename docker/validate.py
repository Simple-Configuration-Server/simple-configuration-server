"""
Script to validate an SCS configuration, by sing an auth-less Flask test client
and testing requests to every resource
"""
import os
from pathlib import Path
from typing import Any
from json import JSONDecodeError

from flask import Blueprint
import fastjsonschema
from yaml import YAMLError

import scs

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
    if script_conf_path.is_file():
        configuration_data = scs.yaml.safe_load_file(script_conf_path)
    else:
        print(
            'scs-validate.yaml not found, using default settings',
            flush=True,
        )
        configuration_data = {}
    return fastjsonschema.validate(configuration_schema, configuration_data)


if __name__ == '__main__':
    print('Validating SCS configuration...', flush=True)
    scs_config = scs.load_application_configuration()
    script_config = load_script_configuration()

    # Override configuration with validation specific properties
    for key, value in script_config['scs_configuration'].items():
        scs_config[key] = value

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
    all_test_paths = set([
        f'/configs/{p.lstrip("/")}'
        for p in scs.configs.get_relative_config_template_paths()
    ])

    configured_endpoints = script_config['endpoints']
    configured_paths = set(configured_endpoints.keys())
    invalid_paths = configured_paths.difference(all_test_paths)
    if invalid_paths:
        raise ValueError(
            'Endpoints configuration in scs-validate.yaml contains invalid '
            f'paths: {invalid_paths}'
        )

    # Build test definitions for each endpoint, based on the overrides that
    # are configured
    test_definitions = {}
    for path in all_test_paths:
        path_config = configured_endpoints.get(path, True)
        if not path_config:
            # endpoint validation explicitly disabled
            continue
        if not isinstance(path_config, dict):
            path_config = {
                'request': {'method': 'GET'},
                'response': {},
            }
        test_definitions[path] = path_config

    test_results = {}
    for path, defininition in test_definitions.items():
        if defininition['request']['method'] == 'GET':
            response = client.get(
                path
            )
        else:
            response = client.post(
                path,
                json=defininition['request']['json'],
            )

        base_message = f'Validation of path {path} failed:'

        validate_status = defininition['response'].get('status')
        if validate_status is not None:
            assert response.status_code == validate_status, \
                f'{base_message} Wrong status code {response.status_code}'
        else:
            assert response.status_code < 400, \
                f'{base_message} Wrong status code {response.status_code}'

        validate_headers = defininition['response'].get('headers')
        if validate_headers is not None:
            for key, value in validate_headers.items():
                actual_value = response.headers.get(key)
                assert actual_value == value, \
                    f'{base_message} Wrong header \'{key}: {actual_value}\''

        validate_text = defininition['response'].get('text')
        if validate_text is not None:
            assert response.text == validate_text, \
                f'{base_message} Wrong text response \'{response.text}\''

        parse_as = defininition['response'].get('format')

        validate_json = defininition['response'].get('json')
        parse_json = (parse_as == 'json' or validate_json is not None)
        if parse_json:
            try:
                data = response.get_json(force=True)
            except JSONDecodeError:
                print(
                    f'Response from {path} could not be parsed as JSON:',
                    flush=True,
                )
                raise
            if validate_json is not None:
                assert data == validate_json, \
                    f'{base_message} Wrong JSON response {data}'

        validate_yaml = defininition['response'].get('yaml')
        parse_yaml = (parse_as == 'yaml' or validate_yaml is not None)
        if parse_yaml:
            try:
                data = scs.yaml.safe_load(response.text)
            except YAMLError:
                print(
                    f'Response from {path} could not be parsed as YAML:',
                    flush=True,
                )
                raise
            if validate_yaml is not None:
                assert data == validate_yaml, \
                    f'{base_message} Wrong YAML response {data}'

    print('SCS configuration validation succesful!', flush=True)
