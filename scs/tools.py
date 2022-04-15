# -*- coding: utf-8 -*-
"""
Module containing functions and classes that are used in multiple parts of the
SCS code
"""
import importlib
from string import Formatter

from typing import Any


def get_object_from_name(full_ref: str) -> Any:
    """
    Gets the object of a module, based on a string describing the location
    (e.g. 'logging.handlers.RotatingFileHandler')
    """
    path_components = full_ref.split('.')
    module_ref = '.'.join(path_components[:-1])
    objectname = path_components[-1]

    module = importlib.import_module(module_ref)
    return getattr(module, objectname)


_string_formatter = Formatter()


def get_referenced_fields(format_string: str) -> set:
    """
    Gets a set of the fields that are referenced in a format-string
    """
    fields = set()
    for parsed_section in _string_formatter.parse(format_string):
        field = parsed_section[1]
        if field is not None:
            fields.add(field)

    return fields
