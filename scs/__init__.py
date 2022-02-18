# -*- coding: utf-8 -*-
"""
Main entrypoint for the Simple Configuration Server
"""
from pathlib import Path
import yaml
import os

from flask import Flask

from . import configs, auth, audit

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
        auth.bp, **{'scs_auth_path': scs_auth_path, **scs_conf['auth']},
    )

    return app


def load_app_config(path):
    """
    Load the scs_conf.yaml file
    """
    with open(path, 'r', encoding='utf8') as yamlfile:
        return yaml.load(yamlfile, configs.SCSAppConfigLoader)
