"""
Tools used by the testing suites


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
import yaml
from pathlib import Path
from typing import Any
import os
import sys
import json

from werkzeug.test import Client

# Add the root folder to path, so scs can be loaded
tests_path = Path(__file__).parent.absolute()
sys.path.append(
    Path(tests_path, '../').absolute().as_posix()
)
from scs import create_app  # noqa: E402


def safe_load_yaml_file(path: Path) -> Any:
    """
    Returns parsed YAML data from the file at the given path, loaded using
    the yaml.safe_load function
    """
    with open(path, 'r', encoding='utf8') as yamlfile:
        return yaml.safe_load(yamlfile)


def get_test_client(config_dir: Path, testing: bool = False) -> Client:
    """
    Returns a flask test client, configured using the files from the given
    config directory.

    Args:
        config_dir:
            The directory to search for configuration files
        testing:
            If True, exceptions are raised. If false, a 500 error response is
            returned for exceptions
    """
    os.environ['SCS_CONFIG_DIR'] = config_dir.as_posix()

    app = create_app()
    app.testing = testing

    return app.test_client()


def load_jsonlines_file(path: Path) -> list:
    """
    Returns the parsed content of a JSON-lines file, each line being a list
    item
    """
    lines = []
    with open(path, 'r', encoding='utf8') as jsonlinesfile:
        for line in jsonlinesfile:
            lines.append(json.loads(line))

    return lines
