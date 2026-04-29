"""Tests for the agent's reliable HTTP transport (retry + offline buffer)."""

import os
import sys
import tempfile
from unittest.mock import patch, MagicMock

import pytest

# Ensure agent package importable
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from agent.transport import AgentTransport, collect_attempts, default_state_path


@pytest.fixture
def transport(tmp_path):
    db = tmp_path / "outbox.sqlite3"
    return AgentTransport(
        db_path=str(db),
        max_queue=20,
        max_attempts_per_call=2,
        backoff_base_seconds=0.001,
        backoff_cap_seconds=0.002,
        drain_batch=10,
    )


def _ok_response(status=200, text='ok'):
    response = MagicMock()
    response.status_code = status
    response.text = text
    return response


def test_successful_post_clears_no_queue(transport):
    with patch('agent.transport.requests.post', return_value=_ok_response()) as mock_post:
        result = transport.post('http://example/api', json={'k': 1}, headers={'H': 'v'})

    assert result.success is True
    assert result.queued is False
    assert result.status_code == 200
    assert transport.queue_size() == 0
    mock_post.assert_called_once()


def test_transient_failure_enqueues_payload(transport):
    response = _ok_response(status=503, text='busy')
    with patch('agent.transport.requests.post', return_value=response):
        result = transport.post('http://example/api', json={'metric': 42}, headers={'X-API-Key': 'k'})

    assert result.success is False
    assert result.queued is True
    assert transport.queue_size() == 1

    queued = list(collect_attempts(transport))
    assert queued[0]['payload'] == {'metric': 42}
    assert queued[0]['url'] == 'http://example/api'


def test_permanent_4xx_does_not_enqueue(transport):
    response = _ok_response(status=400, text='bad request')
    with patch('agent.transport.requests.post', return_value=response):
        result = transport.post('http://example/api', json={}, headers={})

    assert result.success is False
    assert result.queued is False
    assert transport.queue_size() == 0


def test_connection_error_enqueues(transport):
    import requests as _requests
    with patch('agent.transport.requests.post', side_effect=_requests.ConnectionError('network down')):
        result = transport.post('http://example/api', json={'x': 1}, headers={})

    assert result.success is False
    assert result.queued is True
    assert transport.queue_size() == 1


def test_drain_resends_queued_payload_when_network_restored(transport):
    import requests as _requests

    # First call: network down -> enqueued.
    with patch('agent.transport.requests.post', side_effect=_requests.ConnectionError('down')):
        transport.post('http://example/api', json={'i': 1}, headers={})
    assert transport.queue_size() == 1

    # Second call: network back. Should drain the previous + send the new one.
    with patch('agent.transport.requests.post', return_value=_ok_response()) as mock_post:
        result = transport.post('http://example/api', json={'i': 2}, headers={})

    assert result.success is True
    assert result.drained == 1
    assert transport.queue_size() == 0
    # Two requests went out: drained + new
    assert mock_post.call_count == 2


def test_queue_capacity_drops_oldest(tmp_path):
    db = tmp_path / "outbox.sqlite3"
    t = AgentTransport(
        db_path=str(db),
        max_queue=3,
        max_attempts_per_call=1,
        backoff_base_seconds=0.001,
    )
    import requests as _requests
    with patch('agent.transport.requests.post', side_effect=_requests.ConnectionError('down')):
        for i in range(5):
            t.post('http://example/api', json={'i': i}, headers={})

    assert t.queue_size() == 3
    queued_payloads = [item['payload']['i'] for item in collect_attempts(t)]
    # Oldest two (0, 1) should have been dropped; newest three remain.
    assert queued_payloads == [2, 3, 4]


def test_state_persists_across_instances(tmp_path):
    db = tmp_path / "outbox.sqlite3"
    import requests as _requests

    t1 = AgentTransport(db_path=str(db), max_attempts_per_call=1, backoff_base_seconds=0.001)
    with patch('agent.transport.requests.post', side_effect=_requests.ConnectionError('down')):
        t1.post('http://example/api', json={'persist': True}, headers={})
    assert t1.queue_size() == 1

    # New instance pointing at same file should see the queued payload.
    t2 = AgentTransport(db_path=str(db), max_attempts_per_call=1, backoff_base_seconds=0.001)
    assert t2.queue_size() == 1
    payloads = [item['payload'] for item in collect_attempts(t2)]
    assert payloads == [{'persist': True}]


def test_clear_queue(transport):
    import requests as _requests
    with patch('agent.transport.requests.post', side_effect=_requests.ConnectionError('down')):
        transport.post('http://example/api', json={}, headers={})
        transport.post('http://example/api', json={}, headers={})
    assert transport.queue_size() == 2
    cleared = transport.clear_queue()
    assert cleared == 2
    assert transport.queue_size() == 0


def test_default_state_path_uses_state_dir(tmp_path):
    sub = tmp_path / 'agent_state'
    path = default_state_path(str(sub))
    assert os.path.isdir(str(sub))
    assert path.endswith('outbox.sqlite3')


def test_default_state_path_uses_executable_dir_for_frozen(tmp_path):
    fake_exe = tmp_path / 'agent.exe'
    fake_exe.write_text('not really')
    path = default_state_path(None, frozen_executable=str(fake_exe))
    assert os.path.dirname(os.path.abspath(path)) == str(tmp_path)
