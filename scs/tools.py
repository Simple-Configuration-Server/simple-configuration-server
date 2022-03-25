# -*- coding: utf-8 -*-
"""
Module containing functions and classes that are used in multiple parts of the
SCS code
"""
import importlib

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
