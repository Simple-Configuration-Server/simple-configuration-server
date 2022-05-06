"""
Tests for audit logging
"""
from pathlib import Path
import time

import tools

file_dir = Path(__file__).parent.absolute()
config_dir = Path(file_dir, 'data/4')

log_path = Path(config_dir, 'temp')
log_path.mkdir(exist_ok=True)
count_log_file = Path(log_path, 'counts.log')
count_log_file.unlink(missing_ok=True)


client = tools.get_test_client(config_dir)
tokens = tools.safe_load_yaml_file(
    Path(config_dir, 'secrets/scs-tokens.yaml')
)


def test_yaml_constructor():
    """
    Test if the configured YAML constructor is working
    """
    response = client.get(
        '/configs/tag-constructor-test',
        headers={
            'Authorization': (
                f"Bearer {tokens['test-user']}"
            ),
        },
        environ_base={'REMOTE_ADDR': '127.0.0.1'},
    )
    assert response.status_code == 200
    assert response.text == 'THIS IS THE BASE PHRASE with additional phrase'


def test_jinja_extension():
    """
    Test if the configured jinja extension is working
    """
    response = client.get(
        '/configs/jinja-extension-test',
        headers={
            'Authorization': (
                f"Bearer {tokens['test-user']}"
            ),
        },
        environ_base={'REMOTE_ADDR': '127.0.0.1'},
    )
    assert response.status_code == 200
    assert response.text == 'this is a test for SCS'


def test_blueprint_extension():
    """
    Test if the configured jinja extension is working
    """
    # 2 requests were performed, so the last line should contain '2'. wait
    # shortly to ensure it's written
    time.sleep(0.2)
    with open(count_log_file, 'r', encoding='utf8') as logfile:
        for line in logfile:
            continue
        assert line.strip() == '2'
