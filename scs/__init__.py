# -*- coding: utf-8 -*-
"""
Main entrypoint for the Simple Configuration Server
"""
from pathlib import Path
import os
import importlib

from flask import Flask

from . import configs, audit, yaml, errorhandlers

current_dir = Path(__file__).absolute().parent


def create_app():
    """
    Factory to create the Flask app for the Simple Configuration Server
    """
    # create and configure the app
    app = Flask(__name__)

    # Load the SCS application configuration
    config_dir = Path(os.environ['SCS_CONFIG_DIR']).absolute()
    if not config_dir.is_dir():
        raise ValueError('The provided SCS_CONFIG_DIR does not exist!')

    scs_conf_path = Path(config_dir, 'scs_conf.yaml')
    scs_conf = load_app_config(scs_conf_path)

    if scs_conf['core']['load_env_on_demand']:
        yaml.filecache.disable()

    # Register blueprints and pass configuration
    app.register_blueprint(
        audit.bp, **scs_conf['core']['audit_log']
    )
    app.register_blueprint(errorhandlers.bp)
    app.register_blueprint(
        configs.bp,
        add_constructors=scs_conf.get('add_constructors', []),
        **scs_conf['core'],
    )

    auth_module = importlib.import_module(scs_conf['auth']['module'])
    app.register_blueprint(
        auth_module.bp,
        SCS_CONFIG_DIR=config_dir,
        reject_keys_with_dots=scs_conf['core']['reject_keys_with_dots'],
        **scs_conf['auth']['options'],
    )

    # Clear the cache that was used to load all files
    yaml.filecache.clear()

    return app


def load_app_config(path: Path) -> dict:
    """
    Loads the main SCS config file

    Args:
        path: The path to the configuration file

    Returns:
        The configuration file data
    """
    # Add constructors to the loader, and load the file
    expand_env_constructor = yaml.SCSExpandEnvConstructor()
    yaml.SCSAppConfigLoader.add_constructor(
        expand_env_constructor.tag, expand_env_constructor.construct
    )
    return yaml.load(path, yaml.SCSAppConfigLoader)
