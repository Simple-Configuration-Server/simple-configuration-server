"""
Tests for the scs.configs module


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
    expected response headers are sent
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
    The server must generate a 405 reponse in case a method is used that's not
    allowed for the endpoint
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
    Test if redirects using custom status codes are working
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
    # Ensure the path is not simplified by the test client
    assert response.request.path == '/configs/../scs-users.yaml'
    assert response.status_code == 404


def test_post_request():
    """
    Check if variables in POST requests properly update the context
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
    assert response.status_code == 200
    assert response.text == 'new-name'


def test_post_schema_validation():
    """
    Check if the POST request body is properly validated
    """
    response = client.post(
        '/configs/elasticsearch/cluster_name',
        headers={
            'Authorization': (
                f"Bearer {tokens['test-user-2']}"
            ),
        },
        environ_base={'REMOTE_ADDR': '192.168.1.34'},
        json={'cluster_way': 'wrongvalue'},
    )
    assert response.status_code == 400
    rdata = response.get_json()
    assert rdata['error']['id'] == 'request-body-invalid'


def test_post_malformed():
    """
    A 400 error must be returned if malformed json is sent
    """
    response = client.post(
        '/configs/elasticsearch/cluster_name',
        headers={
            'Authorization': (
                f"Bearer {tokens['test-user-2']}"
            ),
        },
        environ_base={'REMOTE_ADDR': '192.168.1.34'},
        data='this-is-not-even-serialized-json',
    )
    assert response.status_code == 400


def test_without_templating():
    """
    Test if disabling the templating for a specific endpoint works
    """
    response = client.get(
        '/configs/elasticsearch/elasticsearch_template.yml',
        headers={
            'Authorization': (
                f"Bearer {tokens['test-user']}"
            ),
        },
        environ_base={'REMOTE_ADDR': '192.168.1.34'},
    )
    assert response.status_code == 200

    # Check contents
    actual_path = Path(
        config_dir, 'config/elasticsearch/elasticsearch_template.yml'
    )
    with open(actual_path, 'r', encoding='utf8') as textfile:
        original_file_contents = textfile.read()

    assert response.text == original_file_contents


def test_cache():
    """
    Test if caching works as expected. Cache is enabled, so:
    (1) On first request the scs-env is not there, response is empty
    (2) On second request, the scs-env is there, response contains data
    (3) On third request, the scs-env is changed, but still the data from the
        second request is returned
    """
    response = client.get(
        '/configs/elasticsearch/cache_test',
        headers={
            'Authorization': (
                f"Bearer {tokens['test-user']}"
            ),
        },
        environ_base={'REMOTE_ADDR': '192.168.1.34'},
    )
    assert response.text == ''

    env_path = Path(
        config_dir, 'config/elasticsearch/cache_test.scs-env.yaml'
    )
    with open(env_path, 'w', encoding='utf8') as yamlfile:
        yaml.dump({'template': {'context': {'cache_var': 'cached'}}}, yamlfile)

    try:
        response = client.get(
            '/configs/elasticsearch/cache_test',
            headers={
                'Authorization': (
                    f"Bearer {tokens['test-user']}"
                ),
            },
            environ_base={'REMOTE_ADDR': '192.168.1.34'},
        )
        assert response.text == 'cached'

        with open(env_path, 'w', encoding='utf8') as yamlfile:
            yaml.dump(
                {'template': {'context': {'cache_var': 'updated'}}},
                yamlfile,
            )

        response = client.get(
            '/configs/elasticsearch/cache_test',
            headers={
                'Authorization': (
                    f"Bearer {tokens['test-user']}"
                ),
            },
            environ_base={'REMOTE_ADDR': '192.168.1.34'},
        )
        assert response.text == 'cached'
    finally:
        env_path.unlink()
