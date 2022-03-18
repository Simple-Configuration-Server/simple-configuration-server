# -*- coding; utf-8 -*-
"""
Flask Blueprint that contains the custom error handlers for SCS
"""
from flask import Blueprint, jsonify

from jinja2 import TemplateError
from yaml import YAMLError

import re

from werkzeug.exceptions import HTTPException

bp = Blueprint('errorhandlers', __name__)

non_word_chars_regex = re.compile(r'\W+')

# All custom error messages are defined below. When no other context is
# available, the error handler falls back on the first message.
errors = {
    401: {
        'unauthenticated': 'Invalid authentication credentials provided',
    },
    403: {
        'unauthorized': (
            'You are not authorized to access this resource'
        ),
        'unauthorized-ip': (
            'You are not authorized to access the server from this IP'
        ),
        'unauthorized-path': (
            'You are not authorized to access this path on the server'
        ),
    },
    500: {
        'internal-server-error': (
            'An internal server error occured'
        ),
        'template-rendering-error': (
            'An error occured while trying to render the template'
        ),
        'env-loading-error': (
            'An error occured while loading the template env files'
        ),
    }
}


def error_response(id_, message, code):
    """Return a SCS error response"""
    return jsonify({
        'error': {
            'id': id_,
            'message': message,
        }
    }), code


def get_500_error_id(error):
    """
    Get the ID for a 500 error
    """
    id_ = next(iter(errors[500].keys()))
    if isinstance(error.original_exception, YAMLError):
        id_ = 'env-loading-error'
    elif isinstance(error.original_exception, TemplateError):
        id_ = 'template-rendering-error'

    return id_


@bp.app_errorhandler(HTTPException)
def json_error_response(e):
    if e.code == 500:
        id_ = get_500_error_id(e)
        message = errors[e.code][id_]
    elif e.code in errors:
        id_ = next(iter(errors[e.code].keys()))
        if isinstance(e.description, dict):
            id_ = e.description.get('id', id_)
        message = errors[e.code][id_]
    else:
        id_ = non_word_chars_regex.sub('-', e.name.lower())
        message = e.description

    return error_response(
        id_,
        message,
        e.code
    )
