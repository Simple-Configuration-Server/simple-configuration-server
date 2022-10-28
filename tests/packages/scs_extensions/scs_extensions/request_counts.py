"""
Contains a test blueprint that logs the total number of requests to a server


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
from pathlib import Path

from flask import Blueprint, Response
from flask.blueprints import BlueprintSetupState

bp = Blueprint('request_counts', __name__)

_count_logger = logging.getLogger('counts')
_count_logger.propagate = False  # This will be a seperate log file

_count = 0


def _configure_logger(
        logger: logging.Logger, log_path: Path
        ):
    """
    Make sure logs are stored in a file on the defined path

    Args:
        logger:
            The logger to configure
        log_path:
            The path to store the logs
    """

    level = 'INFO'
    handler = logging.FileHandler(
        filename=log_path,
    )
    handler.setLevel(level)
    logger.addHandler(handler)
    logger.setLevel(level)


@bp.record
def init(setup_state: BlueprintSetupState):
    """
    Initialize the logging module

    Args:
        setup_state: The Flask BluePrint Setup State
    """
    _configure_logger(_count_logger, setup_state.options['log_path'])


@bp.after_app_request
def count_request(response: Response) -> Response:
    """
    Create a log entries in case audit events were added during the request

    Args:
        response: The flask response (passed-through)

    Returns:
        The Flask response, passed through from the input parameter
    """
    global _count
    _count += 1
    _count_logger.info(_count)

    return response
