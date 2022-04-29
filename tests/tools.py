"""
Tools used by the testing suites
"""
import yaml
from pathlib import Path
from typing import Any


def safe_load_yaml_file(path: Path) -> Any:
    """
    Use the safe_load function to load a simple yaml file
    """
    with open(path, 'r', encoding='utf8') as yamlfile:
        return yaml.safe_load(yamlfile)
