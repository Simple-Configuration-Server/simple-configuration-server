# -*- coding: utf-8 -*-
"""
Tests for the scs.auth module
"""
from pathlib import Path
import os
import sys

tests_path = Path(__file__).parent.absolute()

sys.path.append(
    Path(tests_path, '../').absolute().as_posix()
)

from scs import create_app  # noqa: E402

os.environ['SCS_CONFIG_DIR'] = Path(
    tests_path,
    'data/1'
).as_posix()

app = create_app()
app.testing = True
client = app.test_client()


def test_if_user_authenticates():
    """
    Test if bearer token authentication works
    """
    response = client.get(
        '/configs/elasticsearch/elasticsearch.yml',
        headers={
            'Authorization': (
                'Bearer K27HUC-0geVXv0Aq6wXCq4tilJvImP3_Rx3MGrwbC9g'
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
                    'Bearer K27HUC-0geVXv0Aq6wXCq4tilJvImP3_Rx3MGddbC9g'
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
                'Bearer K27HUC-0geVXv0Aq6wXCq4tilJvImP3_Rx3MGrwbC9g'
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
                'Bearer gYOWKAcNIu42rg1Fajw3RwKrFNDK9aObVVA1hhk2gLA'
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
                'Bearer K27HUC-0geVXv0Aq6wXCq4tilJvImP3_Rx3MGrwbC9g'
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
                'Bearer K27HUC-0geVXv0Aq6wXCq4tilJvImP3_Rx3MGrwbC9g'
            ),
        },
        environ_base={'REMOTE_ADDR': '172.16.94.2'}
    )
    assert response.status_code == 401
