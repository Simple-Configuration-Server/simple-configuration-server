# -*- coding: utf-8 -*-
"""
Tests for the scs.auth module
"""
from pathlib import Path
import tools
import yaml

file_dir = Path(__file__).parent.absolute()
config_dir = Path(file_dir, 'data/1')
client = tools.get_test_client(config_dir)
tokens = tools.safe_load_yaml_file(
    Path(file_dir, 'data/1/secrets/scs-tokens.yaml')
)


def test_request_file():
    """
    Test if a simple yml configuration file is properly parsed and if the
    headers are properly set
    """
    response = client.get(
        '/configs/elasticsearch/elasticsearch.yml',
        headers={
            'Authorization': (
                f"Bearer {tokens['test-user']}"
            ),
        },
        environ_base={'REMOTE_ADDR': '192.168.1.34'},
    )
    assert response.status_code == 200

    # Check contents
    file_content = yaml.safe_load(response.text)
    assert file_content['network.host'] == ['127.0.0.1', '192.168.1.1']
    # since 'keep_trailing_newline' is set to false:
    assert not response.text.endswith('\n')
    assert response.headers['Content-Type'] == 'application/x-yaml'


def test_wrong_method():
    """
    Using a disallowed method should give a 405 status code
    """
    response = client.post(
        '/configs/elasticsearch/elasticsearch.yml',
        headers={
            'Authorization': (
                f"Bearer {tokens['test-user']}"
            ),
        },
        environ_base={'REMOTE_ADDR': '192.168.1.34'},
    )
    assert response.status_code == 405


def test_redirect():
    """
    Test if the redirect is properly working
    """
    response = client.get(
        '/configs/elasticsearch/cluster_name_redirect',
        headers={
            'Authorization': (
                f"Bearer {tokens['test-user']}"
            ),
        },
        environ_base={'REMOTE_ADDR': '192.168.1.34'},
    )
    assert response.status_code == 301

    response = client.get(
        response.headers['Location'],
        headers={
            'Authorization': (
                f"Bearer {tokens['test-user']}"
            ),
        },
        environ_base={'REMOTE_ADDR': '127.0.0.1'},
    )
    assert response.status_code == 200
    assert response.text == 'scs-production'


def test_path_traversal():
    """
    Attempts for path traversal should return a 404 error
    """
    response = client.get(
        '/configs/../scs-users.yaml',
        headers={
            'Authorization': (
                f"Bearer {tokens['test-user-2']}"
            ),
        },
        environ_base={'REMOTE_ADDR': '192.168.1.34'},
    )
    # First ensure the path is not simplified during the request
    assert response.request.path == '/configs/../scs-users.yaml'
    assert response.status_code == 404


def test_post_request():
    """
    Check if post requests properly update the context
    """
    response = client.post(
        '/configs/elasticsearch/cluster_name',
        headers={
            'Authorization': (
                f"Bearer {tokens['test-user-2']}"
            ),
        },
        environ_base={'REMOTE_ADDR': '192.168.1.34'},
        json={'cluster_name': 'new-name'},
    )
    # First ensure the path is not simplified during the request
    assert response.status_code == 200
    assert response.text == 'new-name'


def test_post_malformed():
    """
    A 400 error should be returned, if malformed json is sent
    """
    response = client.post(
        '/configs/elasticsearch/cluster_name',
        headers={
            'Authorization': (
                f"Bearer {tokens['test-user-2']}"
            ),
        },
        environ_base={'REMOTE_ADDR': '192.168.1.34'},
        data='henkieisdebeste',
    )
    # First ensure the path is not simplified during the request
    assert response.status_code == 400
