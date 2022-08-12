# -*- coding: utf-8 -*-
"""
Tests for the scs.auth module


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

file_dir = Path(__file__).parent.absolute()
config_dir = Path(file_dir, 'data/3')
client = tools.get_test_client(config_dir)
tokens = tools.safe_load_yaml_file(
    Path(config_dir, 'secrets/scs-tokens.yaml')
)


def test_template_rendering_error():
    """
    Test if a simple yml configuration file is properly parsed and if the
    headers are properly set
    """
    response = client.get(
        '/configs/elasticsearch/heap_size',
        headers={
            'Authorization': (
                f"Bearer {tokens['test-user']}"
            ),
        },
        environ_base={'REMOTE_ADDR': '127.0.0.1'},
    )
    assert response.status_code == 500
    assert response.get_json()['error']['id'] == 'template-rendering-error'


def test_env_file_format_error():
    """
    Test if a simple yml configuration file is properly parsed and if the
    headers are properly set
    """
    response = client.get(
        '/configs/elasticsearch/cluster_name_redirect',
        headers={
            'Authorization': (
                f"Bearer {tokens['test-user']}"
            ),
        },
        environ_base={'REMOTE_ADDR': '127.0.0.1'},
    )
    assert response.status_code == 500
    assert response.get_json()['error']['id'] == 'env-format-error'


def test_env_file_syntax_error():
    """
    Test if a simple yml configuration file is properly parsed and if the
    headers are properly set
    """
    response = client.get(
        '/configs/elasticsearch/cluster_name',
        headers={
            'Authorization': (
                f"Bearer {tokens['test-user']}"
            ),
        },
        environ_base={'REMOTE_ADDR': '127.0.0.1'},
    )
    assert response.status_code == 500
    assert response.get_json()['error']['id'] == 'env-syntax-error'
