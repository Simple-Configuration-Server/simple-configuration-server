# -*- coding: utf-8 -*-
"""
Test if configuration files are properly validated during server initialization


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
from pathlib import Path
import tools
import fastjsonschema

file_dir = Path(__file__).parent.absolute()


def test_invalid_configuration_rejected():
    """
    App initialization must fail in case the configuration fails validation
    """
    config_dir = Path(file_dir, 'data/5')

    initialization_failed = False
    try:
        tools.get_test_client(config_dir)
    except fastjsonschema.exceptions.JsonSchemaValueException:
        initialization_failed = True

    assert initialization_failed


def test_invalid_users_rejected():
    """
    App initialization must fail in case the users.yaml fails validation
    """
    config_dir = Path(file_dir, 'data/6')

    initialization_failed = False
    try:
        tools.get_test_client(config_dir)
    except fastjsonschema.exceptions.JsonSchemaValueException:
        initialization_failed = True

    assert initialization_failed
