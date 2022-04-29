# -*- coding: utf-8 -*-
"""
Tests for the scs.auth module
"""
from pathlib import Path
import tools

file_dir = Path(__file__).parent.absolute()
config_dir = Path(file_dir, 'data/1')
client = tools.get_test_client(config_dir)
tokens = tools.safe_load_yaml_file(
    Path(file_dir, 'data/1/secrets/scs-tokens.yaml')
)


def test_if_user_authenticates():
    """
    Test if bearer token authentication works
    """
    response = client.get(
        '/configs/elasticsearch/elasticsearch.yml',
        headers={
            'Authorization': (
                f"Bearer {tokens['test-user']}"
            ),
        },
        environ_base={'REMOTE_ADDR': '127.0.0.1'},
    )
    assert response.status_code == 200


def test_wrong_credentials_and_limiting():
    """
    Test (1) if users with bad credentials are denied access, and (2) if the
    rate-limiter kicks in after too many faulty authentication requests

    Note: If this test is run exactly on the switch of one 15 minute window to
    the next, it may fail
    """
    global _rate_limited_requests
    for i in range(11):
        response = client.get(
            '/configs/elasticsearch/elasticsearch.yml',
            headers={
                'Authorization': (
                    'Bearer WrongBearerToken'
                ),
            },
            environ_base={'REMOTE_ADDR': '127.0.0.1'},
        )
        if i < 10:
            assert response.status_code == 401
        else:
            assert response.status_code == 429


def test_path_access_denied():
    """
    Access to the root configs path should be denied for user 1, but allowed
    for user 2
    """
    response = client.get(
        '/configs/host-name',
        headers={
            'Authorization': (
                f"Bearer {tokens['test-user']}"
            ),
        },
        environ_base={'REMOTE_ADDR': '192.168.1.34'}
    )
    assert response.status_code == 403
    assert response.get_json()['error']['id'] == 'unauthorized-path'

    response = client.get(
        '/configs/host-name',
        headers={
            'Authorization': (
                f"Bearer {tokens['test-user-2']}"
            ),
        },
        environ_base={'REMOTE_ADDR': '192.168.1.34'}
    )
    assert response.status_code == 200


def test_global_whitelisted_but_not_user_whitelisted():
    """
    An IP address that is globally whitelisted, but not whitelisted for the
    specific user should trigger a 403 error
    """
    response = client.get(
        '/configs/elasticsearch/elasticsearch.yml',
        headers={
            'Authorization': (
                f"Bearer {tokens['test-user']}"
            ),
        },
        environ_base={'REMOTE_ADDR': '192.168.1.2'}
    )
    assert response.status_code == 403
    assert response.get_json()['error']['id'] == 'unauthorized-ip'


def test_not_globally_whitelisted():
    """
    An IP address that is not globally whitelisted should trigger a generic
    401 unauthorized error
    """
    response = client.get(
        '/configs/elasticsearch/elasticsearch.yml',
        headers={
            'Authorization': (
                f"Bearer {tokens['test-user']}"
            ),
        },
        environ_base={'REMOTE_ADDR': '172.16.94.2'}
    )
    assert response.status_code == 401
