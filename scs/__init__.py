# -*- coding: utf-8 -*-
"""
Main entrypoint for the Simple Configuration Server
"""
from pathlib import Path
import os

from flask import Flask
import fastjsonschema

from . import configs, errors, logging, yaml
from .tools import get_object_from_name

current_dir = Path(__file__).absolute().parent

# Load the schema to validate the configuration file against
_schema_path = Path(current_dir, 'schemas/scs-configuration.yaml')
_configuration_schema = yaml.safe_load_file(_schema_path)


def create_app(configuration: dict = None) -> Flask:
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

    if configuration is None:
        configuration = load_application_configuration()

    # The auth configuration is passed to the blueprint directly
    # and not available under the app,config attribute
    auth_config = configuration.pop('auth')

    app.config['SCS'] = configuration

    if not configuration['environments']['cache']:
        yaml.filecache.disable()

    if not configuration['templates']['cache']:
        app.config['TEMPLATES_AUTO_RELOAD'] = True

    # Register default blueprints
    app.register_blueprint(logging.bp)
    app.register_blueprint(errors.bp)
    app.register_blueprint(configs.bp)

    # Dynamically Register auth blueprint, and pass the auth config options
    auth_blueprint = get_object_from_name(auth_config['blueprint'])
    app.register_blueprint(
        auth_blueprint,
        **auth_config['options'],
    )

    # Load blueprints (Other extensions loaded inside configs module)
    for bp in configuration['extensions']['blueprints']:
        app.register_blueprint(
            get_object_from_name(bp['name']),
            **bp.get('options', {})
        )

    return app


def load_application_configuration() -> dict:
    """
    Loads the main SCS configuration file

    Returns:
        The configuration file data
    """
    # Get the configuration file path
    config_dir = Path(os.environ['SCS_CONFIG_DIR']).absolute()
    if not config_dir.is_dir():
        raise ValueError('The provided SCS_CONFIG_DIR does not exist!')

    scs_conf_path = Path(config_dir, 'scs-configuration.yaml')

    # Enable Environment variable expansion for yaml loader and load the config
    # file
    expand_env_constructor = yaml.SCSExpandEnvConstructor()
    yaml.SCSAppConfigLoader.add_constructor(
        expand_env_constructor.tag, expand_env_constructor.construct
    )

    configuration_data = yaml.load_file(scs_conf_path, yaml.SCSAppConfigLoader)

    return validate_configuration(configuration_data)


def validate_configuration(configuration_data: dict) -> dict:
    """
    Validates the given configuration data using the schema, and sets
    any defaults that are defined in the schema
    """
    return fastjsonschema.validate(_configuration_schema, configuration_data)
