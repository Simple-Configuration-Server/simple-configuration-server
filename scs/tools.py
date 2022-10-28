# -*- coding: utf-8 -*-
"""
Module containing tools used by multiple SCS modules


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
import importlib
from string import Formatter
import re

from typing import Any


def get_object_from_name(full_ref: str) -> Any:
    """
    Gets the object of a module, based on a string describing the location

    Args:
        full_ref:
            The reference to the object (e.g.
            'logging.handlers.RotatingFileHandler')

    Returns:
        The object matching the reference
    """
    path_components = full_ref.split('.')
    module_ref = '.'.join(path_components[:-1])
    objectname = path_components[-1]

    module = importlib.import_module(module_ref)
    return getattr(module, objectname)


_string_formatter = Formatter()


def get_referenced_fields(format_string: str) -> set[str]:
    """
    Gets a set of the fields that are referenced in a format-string

    Args:
        format_string:
            A string that references one or more fields/variables

    Returns:
        A set containing all the names of the fields referenced in the
        format_string
    """
    fields = set()
    for parsed_section in _string_formatter.parse(format_string):
        field = parsed_section[1]
        if field is not None:
            fields.add(field)

    return fields


# Matches wildcard characters that are not escaped
_wildcard_pattern = re.compile(r'(?<!\\)\\\*')


def contains_wildcard(path: str) -> bool:
    """Returns 'true' if the given path if the path contains a wildcard"""
    return bool(_wildcard_pattern.search(re.escape(path)))


def build_pattern_from_path(wildcard_path: str) -> re.Pattern:
    """
    Builds a regex pattern based on a path string that contais a wildcard
    character (*)

    Args:
        wildcard_path:
            For example '/configs/*.json'. To excape wildcard characters,
            prefix them with a backslash (\\).

    Returns:
        The compiled regex to match paths
    """
    regex_escaped = re.escape(wildcard_path)
    wildcard_converted = _wildcard_pattern.sub('(.*)', regex_escaped)
    non_wildcard_normalized = wildcard_converted.replace(r'\\\*', r'\*')
    regex_str = f"^{non_wildcard_normalized}$"
    return re.compile(regex_str, re.IGNORECASE)
