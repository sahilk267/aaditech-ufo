"""Tests for Phase 2 Week 16 Windows Update monitor foundation."""

from unittest.mock import patch

from server.auth import get_api_key


def _headers(tenant_slug=None):
    headers = {'X-API-Key': get_api_key()}
    if tenant_slug:
        headers['X-Tenant-Slug'] = tenant_slug
    return headers


def test_update_monitor_uses_linux_test_double_path(client, app_fixture):
    app_fixture.config['UPDATE_MONITOR_ADAPTER'] = 'linux_test_double'
    app_fixture.config['UPDATE_ALLOWED_HOSTS'] = 'host-a,host-b'
    app_fixture.config['UPDATE_MONITOR_MAX_ENTRIES'] = 3
    app_fixture.config['UPDATE_LINUX_MONITOR_TEST_DOUBLE'] = (
        'host-a=KB5030211|Security Update|2026-03-17'
        '||KB5031455|Cumulative Update|2026-03-12'
    )

    response = client.post(
        '/api/updates/monitor',
        headers=_headers(),
        json={'host_name': 'host-a'},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['status'] == 'success'
    assert payload['updates']['adapter'] == 'linux_test_double'
    assert payload['updates']['update_count'] == 2
    assert payload['updates']['latest_installed_on'] == '2026-03-17'
    assert payload['updates']['updates'][0]['hotfix_id'] == 'KB5030211'
    assert payload['updates']['updates'][0]['classification'] == 'security'


def test_update_monitor_uses_windows_boundary(client, app_fixture):
    app_fixture.config['UPDATE_MONITOR_ADAPTER'] = 'windows'
    app_fixture.config['UPDATE_ALLOWED_HOSTS'] = 'host-a'
    app_fixture.config['UPDATE_MONITOR_MAX_ENTRIES'] = 2

    class _WindowsUpdateMonitorDouble:
        returncode = 0
        stdout = (
            'KB5030211|Security Update|2026-03-17\n'
            'KB5031455|Cumulative Update|2026-03-12\n'
        )
        stderr = ''

    with patch(
        'server.services.update_service.UpdateService._run_windows_update_monitor_command',
        return_value=_WindowsUpdateMonitorDouble(),
    ) as runner_double:
        response = client.post(
            '/api/updates/monitor',
            headers=_headers(),
            json={'host_name': 'host-a'},
        )

    assert runner_double.call_count == 1
    command_args, command_kwargs = runner_double.call_args
    assert command_args[0][0:2] == ['powershell.exe', '-Command']
    assert "Get-HotFix -ComputerName 'host-a'" in command_args[0][2]
    assert 'Select-Object -First 2 HotFixID,Description,InstalledOn' in command_args[0][2]
    assert command_args[1] == 8
    assert command_kwargs == {}

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['status'] == 'success'
    assert payload['updates']['adapter'] == 'windows'
    assert payload['updates']['update_count'] == 2
    assert payload['updates']['status_summary'] == 'updates_detected'


def test_update_monitor_maps_windows_command_failure_to_503(client, app_fixture):
    app_fixture.config['UPDATE_MONITOR_ADAPTER'] = 'windows'
    app_fixture.config['UPDATE_ALLOWED_HOSTS'] = 'host-a'

    class _WindowsUpdateMonitorFailureDouble:
        returncode = 1
        stdout = ''
        stderr = 'Access is denied.'

    with patch(
        'server.services.update_service.UpdateService._run_windows_update_monitor_command',
        return_value=_WindowsUpdateMonitorFailureDouble(),
    ) as runner_double:
        response = client.post(
            '/api/updates/monitor',
            headers=_headers(),
            json={'host_name': 'host-a'},
        )

    assert runner_double.call_count == 1
    assert response.status_code == 503

    payload = response.get_json()
    assert payload['error'] == 'Windows Update monitor command failed'
    assert payload['details']['status'] == 'command_failed'
    assert payload['details']['adapter'] == 'windows'
    assert payload['details']['returncode'] == 1