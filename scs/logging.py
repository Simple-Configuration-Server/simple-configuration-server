# -*- coding: utf-8 -*-
"""
Contains the configuration related to creating audit logs. Audit logs record
actions related to authentication and retrieving information. For all possible
events, see the 'events' variable below.
"""
import logging
from logging import handlers
import json
import datetime
from pathlib import Path
import copy

from flask import Blueprint, g, request
from flask.blueprints import BlueprintSetupState
from flask.logging import default_handler

from .tools import get_referenced_fields

bp = Blueprint('audit', __name__)

_audit_logger = logging.getLogger(__name__)
_audit_logger.propagate = False  # This will be a seperate log file

_audit_events = {}


def register_audit_event(
        type_: str, level: str | int, message_template: str
        ):
    """
    Registers an audit event so it can be logged. After registration, you can
    use the g.add_audit_event function, to add an audit event with the given
    id

    Args:
        type_:
            A unique identifier for the type of event to register
        level:
            The level at which this event should be logged (logging module
            level)
        message_template:
            A template string,
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

    # Set the lowest level on the logger itself
    logger_level = min(numeric_levels)
    logger.setLevel(logger_level)


@bp.record
def init(setup_state: BlueprintSetupState):
    """
    Initialize the audit module logging

    Args:
        setup_state: The Flask BluePrint Setup State
    """
    audit_log_config = setup_state.app.config['SCS']['logs']['audit']
    _configure_logger(
        _audit_logger,
        audit_log_config,
        AuditLogFormatter(),
    )

    app_log_config = setup_state.app.config['SCS']['logs']['application']
    app_logger = setup_state.app.logger
    app_logger.removeHandler(default_handler)
    _configure_logger(
        app_logger,
        app_log_config,
        AppLogFormatter(),
    )


def _add_audit_event(event_type: str, **kwargs):
    """
    Add an audit event to the request context
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
    Initializes the events for the global object, and adds the function
    """
    g.audit_events = []
    g.add_audit_event = _add_audit_event


@bp.after_app_request
def log_audit_event(response):
    """
    Create a log entries in case audit requests are attached to the request
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
    Formatter for creating JSON lines log files for the Audit Logs, so they
    can be streamed to a monitoring system

    Arguments:
        log_source_name --- str: The name if the script that is being logged
    """
    source_name = 'scs'

    def format(self, record: logging.LogRecord) -> str:
        """
        Format a log record to the json format
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
    """
    source_name = 'scs'

    def get_error_info(self, record: logging.LogRecord) -> str:
        """
        Gets an error information string, if an error has occured, otherwise
        returns None. Code partially from logging.Formatter
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
        Format a log record to the json format
        """
        err = record.exc_info
        if err is False or err is True:
            # This is somehow the case for some elasticsearch package errors..
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
