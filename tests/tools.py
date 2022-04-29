"""
Tools used by the testing suites
"""
import yaml
from pathlib import Path
from typing import Any
import os
import sys

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


def get_test_client(config_dir: Path) -> Client:
    """
    Get a test client, configured using the files from the given config
    directory
    """
    os.environ['SCS_CONFIG_DIR'] = config_dir.as_posix()

    app = create_app()
    app.testing = True
    return app.test_client()
