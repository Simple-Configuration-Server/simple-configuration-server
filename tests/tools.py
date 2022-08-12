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
    Use the safe_load function to load a simple yaml file
    """
    with open(path, 'r', encoding='utf8') as yamlfile:
        return yaml.safe_load(yamlfile)


def get_test_client(config_dir: Path, testing: bool = False) -> Client:
    """
    Get a test client, configured using the files from the given config
    directory. 'testing' is set as the app.testing attribute
    """
    os.environ['SCS_CONFIG_DIR'] = config_dir.as_posix()

    app = create_app()
    if testing:
        app.testing = True

    return app.test_client()


def load_jsonlines_file(path: Path) -> list:
    """
    Load the lines of a JSON-lines file
    """
    lines = []
    with open(path, 'r', encoding='utf8') as jsonlinesfile:
        for line in jsonlinesfile:
            lines.append(json.loads(line))

    return lines
