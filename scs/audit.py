# -*- coding: utf-8 -*-
"""
Contains the configuration related to creating audit logs. Audit logs record
actions related to authentication and retrieving information. For all possible
events, see the 'events' variable below.
"""
import logging
import json
import datetime

from flask import Blueprint, g, request

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
    Initializes the events for the g object
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


# For testing, log to console
logger.setLevel('INFO')
handler = logging.StreamHandler()
handler.setFormatter(AuditLogFormatter())
logger.addHandler(handler)
