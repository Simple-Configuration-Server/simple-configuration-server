# -*- coding: utf-8 -*-
"""
Main entrypoint for the Simple Configuration Server
"""
from pathlib import Path
import os
import importlib

from flask import Flask
import fastjsonschema

from . import configs, errors, logging, yaml
from .tools import get_object_from_name

current_dir = Path(__file__).absolute().parent


def create_app() -> Flask:
    """
    Factory to create the Flask app for the Simple Configuration Server

    Returns:
        The main flask application
    """
    app = Flask(__name__)

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
    auth_module = importlib.import_module(auth_config['module'])
    app.register_blueprint(
        auth_module.bp,
        **auth_config['options'],
    )

    # Load blueprint & jinja2 extensions
    for bp in configuration['extensions']['blueprints']:
        app.register_blueprint(
            get_object_from_name(bp['name']),
            **bp.get('options', {})
        )
    for jinja_extension in configuration['extensions']['jinja2']:
        app.jinja_env.add_extension(jinja_extension['name'])

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

    # Load the schema to validate the configuration file against
    schema_path = Path(
        Path(__file__).absolute().parent, 'schemas/scs-configuration.yaml',
    )
    configuration_schema = yaml.safe_load_file(schema_path)

    return fastjsonschema.validate(configuration_schema, configuration_data)
