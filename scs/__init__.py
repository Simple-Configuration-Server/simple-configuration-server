"""
Main entrypoint for the Simple Configuration Server


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
from pathlib import Path
import os

from flask import Flask
import fastjsonschema

from . import configs, errors, logging, yaml
from .tools import get_object_from_name

module_dir = Path(__file__).absolute().parent

# Load the schema to validate the configuration file against
_schema_path = Path(module_dir, 'schemas/scs-configuration.yaml')
_configuration_schema = yaml.safe_load_file(_schema_path)


class SCSObject:
    """
    Empty class for setting arbitrary attributes

    Used as app.scs in the code, to store global objects at the app level
    """
    pass


def create_app(configuration: dict | None = None) -> Flask:
    """
    Factory to create the Flask app for the Simple Configuration Server

    Args:
        configuration:
            If provided, this replaces the configuration loaded from the
            scs-configuration file by 'load_application_configuration()'. Use
            this to pass edited configuration files, e.g. for configuration
            file validation

    Returns:
        The main flask application
    """
    app = Flask(__name__)
    app.scs = SCSObject()  # emtpy class to store SCS related objects

    if configuration is None:
        configuration = load_application_configuration()

    # The auth config does not need to be available system wide, just pass it
    # to the auth module
    auth_configuration = configuration.pop('auth')

    app.config['SCS'] = configuration

    if not configuration['templates']['cache']:
        app.config['TEMPLATES_AUTO_RELOAD'] = True

    # Register default blueprints
    app.register_blueprint(logging.bp)
    app.register_blueprint(errors.bp)
    app.register_blueprint(configs.bp)

    try:
        auth_blueprint = get_object_from_name(auth_configuration['blueprint'])
    except ValueError:
        raise ValueError(
            f"Cannot find auth.blueprint: {auth_configuration['blueprint']}"
        )
    app.register_blueprint(
        auth_blueprint,
        **auth_configuration['options'],
    )

    for blueprint_definition in configuration['extensions']['blueprints']:
        blueprint_name = blueprint_definition['name']
        try:
            blueprint = get_object_from_name(blueprint_name)
        except ValueError:
            raise ValueError(
                f"Cannot find extensions.blueprint: {blueprint_name}"
            )

        app.register_blueprint(
            blueprint,
            **blueprint_definition.get('options', {})
        )

    return app


def load_application_configuration() -> dict:
    """
    Returns the parsed and validated contents of the scs-configuration.yaml
    file

    Returns:
        The configuration file data
    """
    config_dir = Path(os.environ['SCS_CONFIG_DIR']).absolute()
    if not config_dir.is_dir():
        raise ValueError('The provided SCS_CONFIG_DIR does not exist!')

    config_file_path = Path(config_dir, 'scs-configuration.yaml')

    expand_env_constructor = yaml.SCSExpandEnvConstructor()
    yaml.SCSAppConfigLoader.add_constructor(
        expand_env_constructor.tag, expand_env_constructor.construct
    )

    configuration_data = yaml.load_file(
        config_file_path, yaml.SCSAppConfigLoader,
    )

    return validate_configuration(configuration_data)


def validate_configuration(configuration_data: dict) -> dict:
    """
    Returns the configuration data, validated according to the JSON-schema,
    with defaults filled for missing properties
    """
    return fastjsonschema.validate(_configuration_schema, configuration_data)
