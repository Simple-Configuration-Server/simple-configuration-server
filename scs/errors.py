"""
Flask Blueprint that contains the custom error handlers for SCS, making sure
that machine interpretable JSON responses are returned in case of errors.

Use the register() and register_exception() functions to configure the errors
module to respond with custom errors for your blueprints.


Copyright 2022 Tom Brouwer

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""
import re
import functools

from flask import Blueprint, jsonify, Response, Flask, current_app
from flask.blueprints import BlueprintSetupState
from werkzeug.exceptions import HTTPException

bp = Blueprint('errors', __name__)

_non_word_chars_regex = re.compile(r'\W+')


def _register(code: int, id_: str, message: str, *, app: Flask):
    """
    Registers an error id for a specific HTTP response code. To trigger the
    error, pass the id as a description to the flask abort command, e.g.:
    `abort(429, description={'id': 'rate-limited'})`

    Args:
        code:
            The HTTP response code to register the error for
        id_:
            A unique identifier, returned in the JSON response
        message:
            The message that should be returned in the JSON response
        app:
            The application to register the id to

    Raises:
        ValueError: In case the given id_ is already registered for the code
    """
    code_errors = app.scs._error_definitions.setdefault(code, {})
    if id_ in code_errors:
        raise ValueError(
            f'CONFLICT: id {id_} is already registered for code {code}',
        )

    code_errors[id_] = message


def _register_exception(
        exception_class: type, id_: str, *, message: str = None, app: Flask,
        ):
    """
    Registers a specific error id to be returned, if the given exception is
    raised when handling a request. If the given id is not yet registered for
    the 500 status code, also a message should be provided.

    Note that if you don't want the server to return a 500 status code when
    the exception occurs, you should handle it in your own code, and call the
    'abort()' function, as described in the register() function docstring.

    Args:
        exception_class:
            The class of the exception for which, if it occurs, the error with
            the given id should be returned
        id_:
            An error id, that is either (1) already registered for code 500
            using the register() function, or (2) a new error id. In case of
            the latter, also provide a message
        message:
            Provide a message in case the given id is not yet registered for
            the 500 response code
        app:
            The app to register the exception on

    Raises:
        ValueError:
            In case the given Exception or id/message combination is already
            registered
    """
    for existing_class, _ in app.scs._exception_ids:
        if existing_class == exception_class:
            raise ValueError(
                f'CONFLICT: Exception {exception_class.__name__} is already '
                f'linked to id {id_}',
            )

    if message is not None:
        _register(500, id_, message, app=app)
    elif id_ not in app.scs._error_definitions[500]:
        raise ValueError(
            f'Error id {id_} not registered as an error, so a message must'
            ' be provided'
        )

    app.scs._exception_ids.append((exception_class, id_))


@bp.record
def init(setup_state: BlueprintSetupState):
    """Initialize the errors module"""
    setup_state.app.scs._error_definitions = {
        400: {
            'bad-request': (
                'Your request is invalid. For POST requests, check if the '
                'request body contains valid JSON'
            )
        },
        401: {
            'unauthenticated': 'Invalid authentication credentials provided',
        },
        403: {
            'unauthorized': (
                'You are not authorized to access this resource'
            ),
        },
        405: {
            'method-not-allowed': (
                'The HTTP request method cannot be used on this endpoint'
            ),
        },
        500: {
            'internal-server-error': (
                'An internal server error occured'
            )
        }
    }
    setup_state.app.scs._exception_ids = []
    setup_state.app.scs.register_error = functools.partial(
        _register, app=setup_state.app
    )
    setup_state.app.scs.register_exception = functools.partial(
        _register_exception, app=setup_state.app
    )


def _error_response(code: int, id_: str, message: str) -> tuple[Response, int]:
    """
    Returns an SCS error response and the corresponding code

    Args:
        code: Status code to return
        id_: Error id to return
        message: Error message to return

    Returns:
        The Flask response from the jsonify function and the response code
    """
    return jsonify({
        'error': {
            'id': id_,
            'message': message,
        }
    }), code


def _get_500_error_id(error: Exception) -> str:
    """
    Returns the error id to use for the given exception
    """
    id_ = next(iter(current_app.scs._error_definitions[500].keys()))
    for exception_cls, error_id in current_app.scs._exception_ids:
        if isinstance(error.original_exception, exception_cls):
            id_ = error_id
            break

    return id_


@bp.app_errorhandler(HTTPException)
def json_error_response(e) -> tuple[Response, int]:
    """
    Application-wide error handler to generate a JSON response in case of
    errors

    Args:
        e: The exception that triggered the handler

    Returns:
        The JSON response and status code to respond with to the user
    """
    if e.code == 500:
        id_ = _get_500_error_id(e)
        message = current_app.scs._error_definitions[e.code][id_]
    elif e.code in current_app.scs._error_definitions:
        id_ = next(iter(current_app.scs._error_definitions[e.code].keys()))
        if isinstance(e.description, dict):
            id_ = e.description.get('id', id_)
        message = current_app.scs._error_definitions[e.code][id_]
    else:
        id_ = _non_word_chars_regex.sub('-', e.name.lower())
        message = e.description

    return _error_response(
        e.code,
        id_,
        message,
    )
