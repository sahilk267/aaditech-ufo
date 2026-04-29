"""Unit tests for the agent-side remote command client."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from agent import commands as cmd_mod


class _FakeResponse:
    def __init__(self, *, status_code=200, payload=None, text=''):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError('no payload')
        return self._payload


def test_default_api_key_is_no_op():
    stats = cmd_mod.poll_and_execute(
        server_base_url='http://example.com',
        api_key='default-key-change-this',
        tenant_header='X-Tenant-Slug',
        tenant_slug='default',
        serial_number='SN1',
    )
    assert stats == {'fetched': 0, 'executed': 0, 'reported': 0, 'failures': 0}


def test_unknown_command_type_is_reported_failure():
    fetched = _FakeResponse(payload={'commands': [{'id': 1, 'command_type': 'shutdown_world', 'payload': {}}]})
    posted = _FakeResponse(status_code=200)
    with patch('agent.commands.requests.get', return_value=fetched), \
         patch('agent.commands.requests.post', return_value=posted) as post_mock:
        stats = cmd_mod.poll_and_execute(
            server_base_url='http://example.com',
            api_key='real-key',
            tenant_header='X-Tenant-Slug',
            tenant_slug='default',
            serial_number='SN1',
        )
    assert stats['fetched'] == 1
    assert stats['executed'] == 0
    assert stats['failures'] == 1
    assert post_mock.call_count == 1
    body = post_mock.call_args.kwargs['json']
    assert body['status'] == 'failure'


def test_ping_command_executes_successfully():
    fetched = _FakeResponse(payload={'commands': [{'id': 7, 'command_type': 'ping', 'payload': {}}]})
    posted = _FakeResponse(status_code=200)
    with patch('agent.commands.requests.get', return_value=fetched), \
         patch('agent.commands.requests.post', return_value=posted) as post_mock:
        stats = cmd_mod.poll_and_execute(
            server_base_url='http://example.com',
            api_key='real-key',
            tenant_header='X-Tenant-Slug',
            tenant_slug='default',
            serial_number='SN1',
        )
    assert stats['executed'] == 1
    assert stats['reported'] == 1
    body = post_mock.call_args.kwargs['json']
    assert body['status'] == 'success'
    assert body['result']['pong'] is True


def test_run_powershell_rejects_non_allowlisted_script():
    outcome = cmd_mod._execute('run_powershell', {'script': 'Remove-Item C:\\ -Recurse'})
    assert outcome['status'] == 'failure'
    assert 'allow-list' in outcome['error']


def test_restart_service_rejects_shell_metacharacters():
    outcome = cmd_mod._execute('restart_service', {'service_name': 'foo; rm -rf /'})
    assert outcome['status'] == 'failure'
    assert 'invalid service_name' in outcome['error']


def test_restart_service_rejects_blank_name():
    outcome = cmd_mod._execute('restart_service', {'service_name': ''})
    assert outcome['status'] == 'failure'


def test_rotate_logs_requires_existing_file(tmp_path):
    missing = tmp_path / 'nope.log'
    outcome = cmd_mod._execute('rotate_logs', {'path': str(missing)})
    assert outcome['status'] == 'failure'
    assert 'file not found' in outcome['error']


def test_rotate_logs_renames_and_truncates(tmp_path):
    log_file = tmp_path / 'app.log'
    log_file.write_text('hello world\n', encoding='utf-8')
    outcome = cmd_mod._execute('rotate_logs', {'path': str(log_file)})
    assert outcome['status'] == 'success'
    assert log_file.exists()
    assert log_file.read_text(encoding='utf-8') == ''
    rotated_path = outcome['result']['rotated_to']
    assert rotated_path.endswith('.bak') or '.bak' in rotated_path


def test_collect_diagnostics_returns_stats():
    outcome = cmd_mod._execute('collect_diagnostics', {})
    assert outcome['status'] == 'success'
    assert 'cpu_percent' in outcome['result']
    assert 'ram_percent' in outcome['result']


def test_unhandled_command_type_in_executor_returns_failure():
    outcome = cmd_mod._execute('teleport', {})
    assert outcome['status'] == 'failure'
    assert 'unhandled' in outcome['error']


def test_poll_swallows_network_errors():
    import requests
    with patch('agent.commands.requests.get', side_effect=requests.ConnectionError('boom')):
        stats = cmd_mod.poll_and_execute(
            server_base_url='http://example.com',
            api_key='real-key',
            tenant_header='X-Tenant-Slug',
            tenant_slug='default',
            serial_number='SN1',
        )
    assert stats == {'fetched': 0, 'executed': 0, 'reported': 0, 'failures': 1}


def test_poll_handles_http_error_response():
    bad = _FakeResponse(status_code=500, text='internal error')
    with patch('agent.commands.requests.get', return_value=bad):
        stats = cmd_mod.poll_and_execute(
            server_base_url='http://example.com',
            api_key='real-key',
            tenant_header='X-Tenant-Slug',
            tenant_slug='default',
            serial_number='SN1',
        )
    assert stats['failures'] == 1
    assert stats['fetched'] == 0
