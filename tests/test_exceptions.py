# -*- coding: utf-8 -*-
"""
Tests for the scs.auth module
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
