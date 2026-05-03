"""Tests for the remote agent command queue endpoints (T5)."""

from __future__ import annotations

import time

from server.auth import get_api_key
from server.extensions import db
from server.models import AgentCommand, Organization


def _h():
    return {'X-API-Key': get_api_key()}


def test_queue_command_rejects_unknown_type(client):
    resp = client.post(
        '/api/agent/commands',
        headers=_h(),
        json={'command_type': 'rm_rf_root', 'payload': {}},
    )
    assert resp.status_code == 400
    body = resp.get_json()
    assert 'command_type' in body['details']


def test_queue_command_rejects_non_object_payload(client):
    resp = client.post(
        '/api/agent/commands',
        headers=_h(),
        json={'command_type': 'ping', 'payload': 'oops'},
    )
    assert resp.status_code == 400
    assert 'payload' in resp.get_json()['details']


def test_queue_command_success_writes_row(client, app_fixture):
    resp = client.post(
        '/api/agent/commands',
        headers=_h(),
        json={
            'command_type': 'ping',
            'payload': {},
            'target_serial_number': 'SERIAL-A',
            'expires_in_seconds': 600,
        },
    )
    assert resp.status_code == 201
    cmd = resp.get_json()['command']
    assert cmd['command_type'] == 'ping'
    assert cmd['status'] == 'pending'
    assert cmd['target_serial_number'] == 'SERIAL-A'

    with app_fixture.app_context():
        row = db.session.get(AgentCommand, cmd['id'])
        assert row is not None
        assert row.status == 'pending'


def test_queue_restart_agent_writes_row(client, app_fixture):
    resp = client.post(
        '/api/agent/commands',
        headers=_h(),
        json={'command_type': 'restart_agent', 'payload': {'delay_seconds': 1}},
    )
    assert resp.status_code == 201
    cmd = resp.get_json()['command']
    assert cmd['command_type'] == 'restart_agent'
    assert cmd['status'] == 'pending'

    with app_fixture.app_context():
        row = db.session.get(AgentCommand, cmd['id'])
        assert row is not None
        assert row.command_type == 'restart_agent'
        assert row.status == 'pending'


def test_pending_endpoint_dispatches_command_for_serial(client, app_fixture):
    queue = client.post(
        '/api/agent/commands',
        headers=_h(),
        json={'command_type': 'ping', 'target_serial_number': 'HOST-X'},
    )
    cmd_id = queue.get_json()['command']['id']

    poll = client.get('/api/agent/commands/pending?serial_number=HOST-X', headers=_h())
    assert poll.status_code == 200
    cmds = poll.get_json()['commands']
    assert any(c['id'] == cmd_id for c in cmds)

    with app_fixture.app_context():
        row = db.session.get(AgentCommand, cmd_id)
        assert row.status == 'dispatched'
        assert row.dispatched_at is not None


def test_pending_endpoint_dispatches_restart_agent_for_serial(client, app_fixture):
    """Ensure a queued `restart_agent` is visible to the target and marked dispatched."""
    queue = client.post(
        '/api/agent/commands',
        headers=_h(),
        json={'command_type': 'restart_agent', 'target_serial_number': 'HOST-R'},
    )
    cmd_id = queue.get_json()['command']['id']

    poll = client.get('/api/agent/commands/pending?serial_number=HOST-R', headers=_h())
    assert poll.status_code == 200
    cmds = poll.get_json()['commands']
    assert any(c['id'] == cmd_id for c in cmds)

    with app_fixture.app_context():
        row = db.session.get(AgentCommand, cmd_id)
        assert row.status == 'dispatched'
        assert row.dispatched_at is not None


def test_pending_endpoint_returns_broadcast_commands(client):
    """Commands without target_serial_number should be visible to any agent."""
    client.post(
        '/api/agent/commands',
        headers=_h(),
        json={'command_type': 'ping'},
    )
    poll = client.get('/api/agent/commands/pending?serial_number=ANY-HOST', headers=_h())
    assert poll.status_code == 200
    assert len(poll.get_json()['commands']) >= 1


def test_expired_command_marked_expired_not_dispatched(client, app_fixture):
    queue = client.post(
        '/api/agent/commands',
        headers=_h(),
        json={'command_type': 'ping', 'expires_in_seconds': 1},
    )
    cmd_id = queue.get_json()['command']['id']
    time.sleep(1.2)

    poll = client.get('/api/agent/commands/pending', headers=_h())
    assert poll.status_code == 200
    cmds = poll.get_json()['commands']
    assert all(c['id'] != cmd_id for c in cmds)

    with app_fixture.app_context():
        row = db.session.get(AgentCommand, cmd_id)
        assert row.status == 'expired'


def test_submit_result_marks_command_completed(client, app_fixture):
    queue = client.post(
        '/api/agent/commands',
        headers=_h(),
        json={'command_type': 'ping'},
    )
    cmd_id = queue.get_json()['command']['id']
    client.get('/api/agent/commands/pending', headers=_h())

    resp = client.post(
        f'/api/agent/commands/{cmd_id}/result',
        headers=_h(),
        json={'status': 'success', 'result': {'pong': True}},
    )
    assert resp.status_code == 200
    body = resp.get_json()['command']
    assert body['status'] == 'completed'

    with app_fixture.app_context():
        row = db.session.get(AgentCommand, cmd_id)
        assert row.status == 'completed'
        assert row.result == {'pong': True}


def test_submit_result_failure_records_error(client, app_fixture):
    queue = client.post(
        '/api/agent/commands',
        headers=_h(),
        json={'command_type': 'restart_service', 'payload': {'service_name': 'ghost'}},
    )
    cmd_id = queue.get_json()['command']['id']

    resp = client.post(
        f'/api/agent/commands/{cmd_id}/result',
        headers=_h(),
        json={'status': 'failure', 'error': 'service not found', 'result': {'stdout': ''}},
    )
    assert resp.status_code == 200
    body = resp.get_json()['command']
    assert body['status'] == 'failed'
    assert body['error_message'] == 'service not found'


def test_submit_result_invalid_status_rejected(client):
    queue = client.post('/api/agent/commands', headers=_h(), json={'command_type': 'ping'})
    cmd_id = queue.get_json()['command']['id']
    resp = client.post(
        f'/api/agent/commands/{cmd_id}/result',
        headers=_h(),
        json={'status': 'maybe'},
    )
    assert resp.status_code == 400


def test_submit_result_unknown_command_returns_404(client):
    resp = client.post(
        '/api/agent/commands/999999/result',
        headers=_h(),
        json={'status': 'success'},
    )
    assert resp.status_code == 404


def test_endpoints_require_api_key(client):
    assert client.post('/api/agent/commands', json={'command_type': 'ping'}).status_code == 401
    assert client.get('/api/agent/commands/pending').status_code == 401
    assert client.post('/api/agent/commands/1/result', json={'status': 'success'}).status_code == 401
