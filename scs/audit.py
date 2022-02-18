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

bp = Blueprint('audit', __name__)

logger = logging.getLogger(__name__)

events = {
    'unauthenticated': {
        'level': logging.WARNING,
        'message_template': 'Unauthenticated request to {path} from {ip}',
    },
    'unauthorized_ip': {
        'level': logging.WARNING,
        'message_template': "User '{user}' used from unauthorized IP {ip}",
    },
    'unauthorized_path': {
        'level': logging.WARNING,
        'message_template': (
            "User '{user}' tried to access {path} but is not authorized"
        )
    },
    'config_loaded': {
        'level': logging.INFO,
        'message_template': "User '{user}' has loaded {path}",
    },
    'secrets_loaded': {
        'level': logging.INFO,
        'message_template': (
            "User '{user}' has loaded the following secrets: {secrets}"
        ),
    },
}


@bp.record
def init(setup_state: BlueprintSetupState):
    """
    Initialize the audit module logging

    Args:
        setup_state:
            Should have a .options attribute (options passed to
            register_blueprint function) containing a dict with
            the following key/value pairs:
                log: dict; containing:
                    path: os.Pathlike
                    max_size_mb: int
                    backup_count: int
    """
    # Get the options
    opts = setup_state.options
    log_path = Path(opts['log']['path']).absolute()
    log_max_size = opts['log']['max_size_mb'] * 1024 * 1024
    log_backup_count = opts['log']['backup_count']

    if not log_path.parent.is_dir():
        raise ValueError(
            'Invalid audit log path provided!'
        )

    # Apply the logging options
    logger.setLevel('INFO')
    handler = handlers.RotatingFileHandler(
        filename=log_path,
        maxBytes=log_max_size,
        backupCount=log_backup_count
    )
    handler.setFormatter(AuditLogFormatter())
    handler.setLevel('INFO')
    logger.addHandler(handler)


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
        event_properties = events[event['type']]
        level = event_properties['level']
        message = event_properties['message_template'].format(
            **event['details']
        )
        logger.log(level, message, extra={'audit_event': event})

    return response


class AuditLogFormatter(logging.Formatter):
    """
    Formatter for creating JSON lines log files for the Audit Logs, so they
    can be streamed to a monitoring system

    Arguments:
        log_source_name --- str: The name if the script that is being logged
    """
    def format(self, record):
        """
        Format a log record to the json format
        """

        payload = {
            'level': record.levelname,
            'date': datetime.datetime.utcfromtimestamp(
                    record.created
                ).isoformat(),
            'message': record.getMessage(),
            'event': record.audit_event
        }

        return json.dumps(payload, ensure_ascii=False)
