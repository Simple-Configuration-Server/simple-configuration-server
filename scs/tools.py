# -*- coding: utf-8 -*-
"""
Module containing functions and classes that are used by multiple modules of
SCS
"""
import importlib
from string import Formatter

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
