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

from flask import Blueprint, g, request
from flask.blueprints import BlueprintSetupState
from flask.logging import default_handler

bp = Blueprint('audit', __name__)

audit_logger = logging.getLogger(__name__)
audit_logger.propagate = False  # This will be a seperate log file

audit_events = {
    'unauthenticated': {
        'level': logging.WARNING,
        'message_template': 'Unauthenticated request to {path} from {ip}',
    },
    'unauthorized-ip': {
        'level': logging.WARNING,
        'message_template': "User '{user}' used from unauthorized IP {ip}",
    },
    'unauthorized-path': {
        'level': logging.WARNING,
        'message_template': (
            "User '{user}' tried to access {path} but is not authorized"
        )
    },
    'config-loaded': {
        'level': logging.INFO,
        'message_template': "User '{user}' has loaded {path}",
    },
    'secrets-loaded': {
        'level': logging.INFO,
        'message_template': (
            "User '{user}' has loaded the following secrets: {secrets}"
        ),
    },
}


def configure_logger(
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
    configure_logger(
        audit_logger,
        audit_log_config,
        AuditLogFormatter(),
    )

    app_log_config = setup_state.app.config['SCS']['logs']['application']
    app_logger = setup_state.app.logger
    app_logger.removeHandler(default_handler)
    configure_logger(
        app_logger,
        app_log_config,
        AppLogFormatter(),
    )


def add_audit_event(
        *, event_type: str, secrets: list[str] = None
        ):
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

    if hasattr(g, 'user'):
        event['details']['user'] = g.user['id']
    if secrets is not None:
        event['details']['secrets'] = secrets

    g.audit_events.append(event)


@bp.before_app_request
def init_events_function():
    """
    Initializes the events for the global object, and adds the function
    """
    g.audit_events = []
    g.add_audit_event = add_audit_event


@bp.after_app_request
def log_audit_event(response):
    """
    Create a log entries in case audit requests are attached to the request
    """
    for event in g.audit_events:
        event_properties = audit_events[event['type']]
        level = event_properties['level']
        message = event_properties['message_template'].format(
            **event['details']
        )
        audit_logger.log(level, message, extra={'audit_event': event})

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
