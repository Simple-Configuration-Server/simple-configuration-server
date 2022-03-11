# -*- coding; utf-8 -*-
"""
Flask Blueprint that contains the custom error handlers for SCS
"""
from flask import Blueprint, jsonify

from jinja2 import TemplateError
from yaml import YAMLError

bp = Blueprint('errorhandlers', __name__)

errors = {
    401: {
        'unauthenticated': 'Invalid authentication credentials provided'
    },
    403: {
        'unauthorized_ip': (
            'You are not authorized to access the server from this IP'
        ),
        'unauthorized_path': (
            'You are not authorized to access this path on the server'
        ),
        'unauthorized': (
            'You are not authorized to access this resource'
        )
    },
    500: {
        'failed_rendering_template': (
            'An error occured while trying to render the template'
        ),
        'failed_loading_env': (
            'An error occured while loading the template env files'
        ),
        'internal_error': (
            'An internal server error occured'
        )
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


@bp.app_errorhandler(401)
def unauthenticated(e):
    id_ = 'unauthenticated'
    return error_response(
        id_,
        errors[e.code][id_],
        e.code
    )


@bp.app_errorhandler(403)
def unauthorized(e):
    id_ = 'unauthorized'
    if isinstance(e.description, dict):
        id_ = e.description.get('id', id_)

    return error_response(
        id_,
        errors[e.code][id_],
        e.code
    )


@bp.app_errorhandler(500)
def server_error(e):
    id_ = 'internal_error'
    print(type(e).__name__)
    if isinstance(e.original_exception, YAMLError):
        id_ = 'failed_loading_env'
    elif isinstance(e.original_exception, TemplateError):
        id_ = 'failed_rendering_template'

    return error_response(
        id_,
        errors[e.code][id_],
        e.code
    )
