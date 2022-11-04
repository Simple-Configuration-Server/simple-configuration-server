"""
Module that controls SCS logging. Seperate logs are used for the application
itself and for 'audit' logs.


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
import logging
from logging import handlers
import json
import datetime
from pathlib import Path
import copy

from flask import Blueprint, g, request, Response
from flask.blueprints import BlueprintSetupState
from flask.logging import default_handler

from .tools import get_referenced_fields

bp = Blueprint('audit', __name__)

_audit_logger = logging.getLogger('audit')
_audit_logger.propagate = False  # This will be a seperate log file

# This is filled by the register_audit_event() function
_audit_events = {}


def register_audit_event(
        type_: str, level: str | int, message_template: str
        ):
    """
    Registers an audit event so it can be logged. After registration, use the
    g.add_audit_event function, to log an audit event with the given id for a
    request

    Args:
        type_:
            A unique identifier for the type of event to register
        level:
            The level at which this event should be logged (logging module
            level)
        message_template:
            A template string that can use any of the variables in the event
            details. These at least contain the 'ip' of the user, and the
            'path' that is requested. See _add_audit_event function for
            available variables.

    Raises:
        ValueError in case the given type_ is already registered
    """
    if type_ in _audit_events:
        raise ValueError(
            f'CONFLICT: Audit event type {type_} is already registered'
        )

    _audit_events[type_] = {
        'level': level,
        'message_template': message_template,
        'required_fields': get_referenced_fields(message_template),
    }


def _configure_logger(
        logger: logging.Logger, settings: dict, formatter: logging.Formatter
        ):
    """
    Apply the settings from the SCS configuration file to the provided logger

    Args:
        logger:
            The logger to configure
        settings:
            The settings for the logger, as defined in the scs-configuration
            file
        formatter:
            Formatter to attach to the configured handler
    """
    numeric_levels = []
    if 'stdout' in settings:
        level = settings['stdout']['level']
        handler = logging.StreamHandler()
        handler.setLevel(level)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        numeric_levels.append(
            logging.getLevelName(level)
        )
    if 'file' in settings:
        # Check if a valid filename is provided
        log_path = settings['file']['path']
        log_dir = Path(log_path).absolute().parent
        if not log_dir.is_dir():
            raise ValueError(
                f'Invalid log path defined: {log_path}'
            )
        level = settings['file']['level']
        handler = handlers.RotatingFileHandler(
            filename=log_path,
            maxBytes=settings['file']['max_size_mb'] * 1024 * 1024,
            backupCount=settings['file']['backup_count']
        )
        handler.setLevel(level)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        numeric_levels.append(
            logging.getLevelName(level)
        )

    # make sure log records with relevant levels reach the handler
    logger_level = min(numeric_levels)
    logger.setLevel(logger_level)


@bp.record
def init(setup_state: BlueprintSetupState):
    """Initialize the logging module"""
    source_name = setup_state.app.config['SCS']['logs']['source_name']

    audit_log_config = setup_state.app.config['SCS']['logs']['audit']
    _configure_logger(
        _audit_logger,
        audit_log_config,
        AuditLogFormatter(source_name=source_name),
    )

    app_log_config = setup_state.app.config['SCS']['logs']['application']
    app_logger = setup_state.app.logger
    app_logger.removeHandler(default_handler)
    _configure_logger(
        app_logger,
        app_log_config,
        AppLogFormatter(source_name=source_name),
    )


def _add_audit_event(event_type: str, **kwargs):
    """
    Add an audit event to the request context

    Args:
        event_type:
            Unique identifier for the audit event to add. This type needs to be
            registered using the register_audit_event() function, prior to
            using it.
        **kwargs:
            These are added as 'details' to the logged event, and can therefore
            be referenced from a message template
    """
    event = {
        'type': event_type,
        'details': {
            'ip': request.remote_addr,
            'path': request.path
        }
    }

    required_fields = _audit_events[event_type]['required_fields']

    if hasattr(g, 'user_id'):
        event['details']['user'] = g.user_id
    elif 'user' in required_fields:
        # This occurs for audit events from the 'configs' blueprint, if
        # a third party auth module is used that does not set the 'g.user_id'
        # property
        event['details']['user'] = None

    event['details'].update(
        copy.deepcopy(kwargs)
    )

    fields = set(event['details'].keys())
    if (missing_fields := required_fields.difference(fields)):
        # If this is not caught, an error is generated while buidling the
        # log events, which is much harder to trace
        raise ValueError(
            f'The required fields {missing_fields} were not provided to the '
            f'add_audit_event function for event type {event_type}'
        )

    g.audit_events.append(event)


@bp.before_app_request
def init_events_function():
    """
    Before every request, initialize the events on the global object, and
    register the add_audit_event function
    """
    g.audit_events = []
    g.add_audit_event = _add_audit_event


@bp.after_app_request
def log_audit_event(response: Response) -> Response:
    """
    Creates an audit log record for each audit event added to the request
    context

    Args:
        response: The flask response (passed-through)

    Returns:
        The Flask response, passed through from the input parameter
    """
    for event in g.audit_events:
        event_properties = _audit_events[event['type']]
        level = event_properties['level']
        message = event_properties['message_template'].format(
            **event['details']
        )
        _audit_logger.log(level, message, extra={'audit_event': event})

    return response


class AuditLogFormatter(logging.Formatter):
    """
    Formatter for creating JSON-lines log files for the Audit Logs, so they
    can be streamed to a monitoring system

    Attributes:
        source_name:
            The value of the 'source' key for each log event
    """
    def __init__(self, *args, source_name: str, **kwargs):
        self.source_name = source_name
        super().__init__(*args, **kwargs)

    def format(self, record: logging.LogRecord) -> str:
        """
        Returns the relevant data from the LogRecored, formatted as JSON (str)
        """
        payload = {
            'level': record.levelname,
            'date': datetime.datetime.utcfromtimestamp(
                    record.created
                ).isoformat(),
            'message': record.getMessage(),
            'event': record.audit_event,
            'source': self.source_name,
        }

        return json.dumps(payload, ensure_ascii=False)


class AppLogFormatter(logging.Formatter):
    """
    Formatter for creating application logs in JSON-lines format

    Attributes:
        source_name:
            The value of the 'source' key for each log event
    """
    def __init__(self, *args, source_name: str, **kwargs):
        self.source_name = source_name
        super().__init__(*args, **kwargs)

    def get_error_info(self, record: logging.LogRecord) -> str | None:
        """
        Returns an error information string, if an error has occured, otherwise
        returns None. Code partially from python builtin logging.Formatter
        """
        s = ' '
        if record.exc_info:
            # Cache the traceback text to avoid converting it multiple times
            # (it's constant anyway)
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            if s[-1:] != "\n":
                s = s + "\n"
            s = s + record.exc_text
        if record.stack_info:
            if s[-1:] != "\n":
                s = s + "\n"
            s = s + self.formatStack(record.stack_info)

        if s == ' ':
            return None
        else:
            return s.strip()

    def format(self, record: logging.LogRecord) -> str:
        """
        Returns the log record contents, serialized as JSON
        """
        err = record.exc_info
        if err is False or err is True:
            # This is the case for some 3rd party package errors
            # (e.g. elasticsearch)
            error_type = None
        elif err is not None:
            error_type = record.exc_info[0].__name__
        else:
            error_type = None

        payload = {
            'level': record.levelname,
            'date': datetime.datetime.utcfromtimestamp(
                        record.created
                    ).isoformat(),
            'message': record.getMessage(),
            'source': self.source_name,
            'module': record.name,
            'errorType': error_type,
            'errorInfo': self.get_error_info(record)
        }

        return json.dumps(payload, ensure_ascii=False)
