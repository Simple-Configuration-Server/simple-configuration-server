# -*- coding: utf-8 -*-
"""
Main entrypoint for the Simple Configuration Server
"""
from pathlib import Path
import os

from flask import Flask

from . import configs, auth, audit, yaml

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

    scs_auth_path = Path(config_dir, 'scs_auth.yaml')

    # Register blueprints and pass configuration
    app.register_blueprint(
        audit.bp, **scs_conf['audit']
    )
    app.register_blueprint(
        configs.bp, **scs_conf['configs']
    )
    app.register_blueprint(
        auth.bp,
        scs_auth_path=scs_auth_path,
        secrets_dir=scs_conf['configs']['directories']['secrets'],
        **scs_conf['auth'],
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
