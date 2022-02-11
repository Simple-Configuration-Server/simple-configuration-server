# -*- coding: utf-8 -*-
"""
Flask Blueprint containing all behaviour related to the authentication and
authorization of users/clients
"""
from flask import Blueprint

bp = Blueprint('auth', __name__)


# Load all users
@bp.before_app_request
def check_auth():
    """
    Check the authentication and authorization of the given user
    """
    pass
    # 1. Check if the credentials match any recorded credentials

    # 2. Check if the given user is authorized for the current endpoint
