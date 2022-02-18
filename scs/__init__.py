# -*- coding: utf-8 -*-
"""
Main entrypoint for the Simple Configuration Server
"""
from pathlib import Path

from flask import Flask

from . import configs, auth

current_dir = Path(__file__).absolute().parent


def create_app():
    """
    Factory to create the Flask app for the Simple Configuration Server
    """
    # create and configure the app
    app = Flask(__name__)

    # Make sure if statements and for-loops do not add unnecessary new lines
    app.jinja_options.update({
        'trim_blocks': True,
        'lstrip_blocks': True,
        'keep_trailing_newline': True,
    })

    # Register blueprints
    configs.init(
        config_dir=Path(current_dir, '../data/config_example/config'),
        common_dir=Path(current_dir, '../data/config_example/common'),
        secrets_dir=Path(current_dir, '../data/config_example/secrets')
    )
    app.register_blueprint(configs.bp)
    auth.init()
    app.register_blueprint(auth.bp)

    return app
