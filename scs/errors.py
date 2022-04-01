# -*- coding; utf-8 -*-
"""
Flask Blueprint that contains the custom error handlers for SCS
"""
import re

from flask import Blueprint, jsonify
from jinja2 import TemplateError
from yaml import YAMLError
from werkzeug.exceptions import HTTPException

from .configs import EnvFileFormatException


bp = Blueprint('errors', __name__)

non_word_chars_regex = re.compile(r'\W+')

# All custom error messages are defined below. When no other context is
# available, the error handler falls back on the first message.
definitions = {
    400: {
        'bad-request': (
            'Your request is invalid. For POST requests, check the JSON'
            ' payload format'
        )
    },
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
    405: {
        'method-not-allowed': (
            'This HTTP request method cannot be used on the endpoint'
        ),
    },
    500: {
        'internal-server-error': (
            'An internal server error occured'
        ),
        'template-rendering-error': (
            'An error occured while trying to render the template'
        ),
        'env-syntax-error': (
            'The YAML syntax in an env file could not be parsed'
        ),
        'env-format-error': (
            'An env file was provided in an invalid format'
        ),
    }
}

exception_ids = [
    (YAMLError, 'env-syntax-error'),
    (TemplateError, 'template-rendering-error'),
    (EnvFileFormatException, 'env-format-error')
]


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
    id_ = next(iter(definitions[500].keys()))
    for exception_cls, error_id in exception_ids:
        if isinstance(error.original_exception, exception_cls):
            id_ = error_id
            break

    return id_


@bp.app_errorhandler(HTTPException)
def json_error_response(e):
    if e.code == 500:
        id_ = get_500_error_id(e)
        message = definitions[e.code][id_]
    elif e.code in definitions:
        id_ = next(iter(definitions[e.code].keys()))
        if isinstance(e.description, dict):
            id_ = e.description.get('id', id_)
        message = definitions[e.code][id_]
    else:
        id_ = non_word_chars_regex.sub('-', e.name.lower())
        message = e.description

    return error_response(
        id_,
        message,
        e.code
    )
