"""
Tests for audit logging
"""
from pathlib import Path
import tools

file_dir = Path(__file__).parent.absolute()
config_dir = Path(file_dir, 'data/2')

log_path = Path(config_dir, 'temp')
log_path.mkdir(exist_ok=True)
audit_log_file = Path(log_path, 'audit.log.jsonl')
audit_log_file.unlink(missing_ok=True)


client = tools.get_test_client(config_dir)
tokens = tools.safe_load_yaml_file(
    Path(config_dir, 'secrets/scs-tokens.yaml')
)


def test_audit_logs():
    """
    Test if audit logs are properly generated
    """
    event_types = []

    # Make a valid request, requesting secrets
    response = client.get(
        '/configs/production/password',
        headers={
            'Authorization': (
                f"Bearer {tokens['test-user']}"
            ),
        },
        environ_base={'REMOTE_ADDR': '127.0.0.1'},
    )
    assert response.status_code == 200
    event_types.append('config-loaded')
    event_types.append('secrets-loaded')

    # Make an invalid request, without credentials
    response = client.get(
        '/configs/production/password',
        environ_base={'REMOTE_ADDR': '127.0.0.1'},
    )
    assert response.status_code == 401
    event_types.append('unauthenticated')

    # Make an invalid request, from a wrong IP address
    response = client.get(
        '/configs/production/password',
        headers={
            'Authorization': (
                f"Bearer {tokens['test-user']}"
            ),
        },
        environ_base={'REMOTE_ADDR': '192.168.1.3'},
    )
    assert response.status_code == 403
    event_types.append('unauthorized-ip')

    # Now read the logs
    logs = tools.load_jsonlines_file(audit_log_file)
    assert len(logs) == len(event_types)
    for log, event_type in zip(logs, event_types):
        assert log['event']['type'] == event_type
