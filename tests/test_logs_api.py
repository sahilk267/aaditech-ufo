"""Tests for Phase 2 Week 13-14 log ingestion foundation."""

from unittest.mock import patch

from server.auth import get_api_key
from server.models import LogEntry, LogSource


def _headers(tenant_slug=None):
    headers = {'X-API-Key': get_api_key()}
    if tenant_slug:
        headers['X-Tenant-Slug'] = tenant_slug
    return headers


def test_ingest_logs_uses_linux_test_double_path(client, app_fixture):
    app_fixture.config['LOG_INGESTION_ADAPTER'] = 'linux_test_double'
    app_fixture.config['LOG_INGESTION_ALLOWED_SOURCES'] = 'system,application'
    app_fixture.config['LOG_LINUX_INGESTION_TEST_DOUBLE'] = 'system=event_a|event_b;application=event_x'
    app_fixture.config['LOG_INGESTION_MAX_ENTRIES'] = 25

    response = client.post(
        '/api/logs/ingest',
        headers=_headers(),
        json={'source_name': 'system'},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['status'] == 'success'
    assert payload['logs']['adapter'] == 'linux_test_double'
    assert payload['logs']['entry_count'] == 2
    assert payload['logs']['entries'] == ['event_a', 'event_b']


def test_ingest_logs_uses_windows_adapter_boundary(client, app_fixture):
    app_fixture.config['LOG_INGESTION_ADAPTER'] = 'windows'
    app_fixture.config['LOG_INGESTION_ALLOWED_SOURCES'] = 'System'
    app_fixture.config['LOG_INGESTION_MAX_ENTRIES'] = 5

    class _WindowsLogProcessDouble:
        returncode = 0
        stdout = 'Event 1\nEvent 2\nEvent 3\n'
        stderr = ''

    with patch(
        'server.services.log_service.LogService._run_windows_log_ingestion_command',
        return_value=_WindowsLogProcessDouble(),
    ) as runner_double:
        response = client.post(
            '/api/logs/ingest',
            headers=_headers(),
            json={'source_name': 'System'},
        )

    assert runner_double.call_count == 1
    command_args, command_kwargs = runner_double.call_args
    assert command_args[0] == ['wevtutil', 'qe', 'System', '/c:5', '/f:text']
    assert command_args[1] == 8
    assert command_kwargs == {}

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['logs']['adapter'] == 'windows'
    assert payload['logs']['entry_count'] == 3
    assert payload['logs']['entries'] == ['Event 1', 'Event 2', 'Event 3']


def test_ingest_logs_persists_entries_and_source(client, app_fixture):
    app_fixture.config['LOG_PERSISTENT_STORE_ENABLED'] = True
    app_fixture.config['LOG_INGESTION_ADAPTER'] = 'linux_test_double'
    app_fixture.config['LOG_INGESTION_ALLOWED_SOURCES'] = 'system'
    app_fixture.config['LOG_LINUX_INGESTION_TEST_DOUBLE'] = 'system=event_a|event_b'

    response = client.post(
        '/api/logs/ingest',
        headers=_headers(),
        json={'source_name': 'system'},
    )

    assert response.status_code == 200
    payload = response.get_json()['logs']
    assert payload['persisted_count'] == 2
    assert payload['log_source_id'] is not None

    with app_fixture.app_context():
        source = LogSource.query.filter_by(name='system').first()
        entries = LogEntry.query.filter_by(source_name='system', capture_kind='ingest').order_by(LogEntry.id.asc()).all()

    assert source is not None
    assert source.adapter == 'linux_test_double'
    assert len(entries) == 2
    assert entries[0].message == 'event_a'
    assert entries[1].raw_entry == 'event_b'


def test_query_event_entries_uses_linux_test_double_path(client, app_fixture):
    app_fixture.config['LOG_EVENT_QUERY_ADAPTER'] = 'linux_test_double'
    app_fixture.config['LOG_INGESTION_ALLOWED_SOURCES'] = 'System,Application'
    app_fixture.config['LOG_LINUX_EVENT_QUERY_TEST_DOUBLE'] = (
        'System=2026-03-18T10:00:00Z|error|1001|System|Disk failure'
        '||2026-03-18T10:01:00Z|warning|1002|System|Retry started'
    )

    response = client.post(
        '/api/logs/events/query',
        headers=_headers(),
        json={'source_name': 'System'},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['status'] == 'success'
    assert payload['events']['adapter'] == 'linux_test_double'
    assert payload['events']['entry_count'] == 2


def test_query_event_entries_uses_windows_wrapper_boundary(client, app_fixture):
    app_fixture.config['LOG_EVENT_QUERY_ADAPTER'] = 'windows'
    app_fixture.config['LOG_INGESTION_ALLOWED_SOURCES'] = 'System'
    app_fixture.config['LOG_INGESTION_MAX_ENTRIES'] = 3

    class _WindowsEventQueryProcessDouble:
        returncode = 0
        stdout = (
            '2026-03-18T10:00:00Z|Error|1001|System|Disk failure\n'
            '2026-03-18T10:01:00Z|Warning|1002|System|Retry started\n'
        )
        stderr = ''

    with patch(
        'server.services.log_service.LogService._run_windows_event_query_command',
        return_value=_WindowsEventQueryProcessDouble(),
    ) as runner_double:
        response = client.post(
            '/api/logs/events/query',
            headers=_headers(),
            json={'source_name': 'System'},
        )

    assert runner_double.call_count == 1
    command_args, command_kwargs = runner_double.call_args
    assert command_args[0][0:2] == ['powershell.exe', '-Command']
    assert "Get-WinEvent -LogName 'System'" in command_args[0][2]
    assert command_args[1] == 8
    assert command_kwargs == {}

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['events']['adapter'] == 'windows'
    assert payload['events']['entry_count'] == 2


def test_search_logs_can_use_persistent_store_after_query(client, app_fixture):
    app_fixture.config['LOG_PERSISTENT_STORE_ENABLED'] = True
    app_fixture.config['LOG_EVENT_QUERY_ADAPTER'] = 'linux_test_double'
    app_fixture.config['LOG_INGESTION_ALLOWED_SOURCES'] = 'System'
    app_fixture.config['LOG_LINUX_EVENT_QUERY_TEST_DOUBLE'] = (
        'System=2026-03-18T10:00:00Z|Error|1001|System|Disk failure'
        '||2026-03-18T10:01:00Z|Warning|1002|System|Retry started'
    )
    app_fixture.config['LOG_SEARCH_ADAPTER'] = 'linux_test_double'
    app_fixture.config['LOG_LINUX_SEARCH_TEST_DOUBLE'] = ''

    query_response = client.post(
        '/api/logs/events/query',
        headers=_headers(),
        json={'source_name': 'System'},
    )
    assert query_response.status_code == 200
    assert query_response.get_json()['events']['persisted_count'] == 2

    search_response = client.post(
        '/api/logs/search',
        headers=_headers(),
        json={'source_name': 'System', 'query_text': 'Disk'},
    )

    assert search_response.status_code == 200
    payload = search_response.get_json()['search']
    assert payload['adapter'] == 'persistent_store'
    assert payload['result_count'] == 1
    assert payload['results'][0]['message'] == 'Disk failure'

    with app_fixture.app_context():
        stored_entry = LogEntry.query.filter_by(source_name='System', capture_kind='event_query', event_id='1001').first()

    assert stored_entry is not None
    assert stored_entry.severity == 'error'


def test_parse_logs_structures_entries(client, app_fixture):
    app_fixture.config['LOG_INGESTION_MAX_ENTRIES'] = 50

    response = client.post(
        '/api/logs/parse',
        headers=_headers(),
        json={
            'entries': [
                '2026-03-18T10:00:00Z|ERROR|1001|System|Disk failure',
                '2026-03-18T10:01:00Z|WARNING|1002|System|Retry started',
            ]
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['parsed']['structured_count'] == 2
    assert payload['parsed']['events'][0]['severity'] == 'error'
    assert payload['parsed']['events'][0]['event_id'] == '1001'


def test_correlate_events_filters_and_groups(client, app_fixture):
    app_fixture.config['LOG_CORRELATION_MIN_GROUP_SIZE'] = 2

    response = client.post(
        '/api/logs/events/correlate',
        headers=_headers(),
        json={
            'allowed_severities': ['error', 'critical'],
            'min_group_size': 2,
            'events': [
                {'source': 'System', 'event_id': '1001', 'severity': 'error', 'message': 'Disk failure'},
                {'source': 'System', 'event_id': '1001', 'severity': 'critical', 'message': 'Disk failure repeated'},
                {'source': 'System', 'event_id': '1002', 'severity': 'warning', 'message': 'Ignored warning'},
            ],
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['correlation']['filtered_count'] == 2
    assert payload['correlation']['group_count'] == 1
    assert payload['correlation']['groups'][0]['source'] == 'System'
    assert payload['correlation']['groups'][0]['event_id'] == '1001'


def test_monitor_drivers_uses_linux_test_double_path(client, app_fixture):
    app_fixture.config['LOG_DRIVER_MONITOR_ADAPTER'] = 'linux_test_double'
    app_fixture.config['LOG_DRIVER_ALLOWED_HOSTS'] = 'host-a,host-b'
    app_fixture.config['LOG_LINUX_DRIVER_MONITOR_TEST_DOUBLE'] = (
        'host-a=Audio Driver|1.0|VendorA|true||Display Driver|2.1|VendorB|false'
    )

    response = client.post(
        '/api/logs/drivers/monitor',
        headers=_headers(),
        json={'host_name': 'host-a'},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['drivers']['adapter'] == 'linux_test_double'
    assert payload['drivers']['driver_count'] == 2
    assert payload['drivers']['drivers'][1]['is_signed'] is False


def test_monitor_drivers_uses_windows_boundary(client, app_fixture):
    app_fixture.config['LOG_DRIVER_MONITOR_ADAPTER'] = 'windows'
    app_fixture.config['LOG_DRIVER_ALLOWED_HOSTS'] = 'host-a'
    app_fixture.config['LOG_INGESTION_MAX_ENTRIES'] = 2

    class _WindowsDriverMonitorDouble:
        returncode = 0
        stdout = 'Audio Driver|1.0|VendorA|True\nDisplay Driver|2.1|VendorB|False\n'
        stderr = ''

    with patch(
        'server.services.log_service.LogService._run_windows_driver_monitor_command',
        return_value=_WindowsDriverMonitorDouble(),
    ) as runner_double:
        response = client.post(
            '/api/logs/drivers/monitor',
            headers=_headers(),
            json={'host_name': 'host-a'},
        )

    assert runner_double.call_count == 1
    command_args, command_kwargs = runner_double.call_args
    assert command_args[0][0:2] == ['powershell.exe', '-Command']
    assert 'Win32_PnPSignedDriver' in command_args[0][2]
    assert command_args[1] == 8
    assert command_kwargs == {}

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['drivers']['adapter'] == 'windows'
    assert payload['drivers']['driver_count'] == 2


def test_detect_driver_errors_uses_linux_test_double_path(client, app_fixture):
    app_fixture.config['LOG_DRIVER_ERROR_ADAPTER'] = 'linux_test_double'
    app_fixture.config['LOG_DRIVER_ALLOWED_HOSTS'] = 'host-a'
    app_fixture.config['LOG_LINUX_DRIVER_ERROR_TEST_DOUBLE'] = 'host-a=Display Driver|2.1|VendorB|false|unsigned'

    response = client.post(
        '/api/logs/drivers/errors',
        headers=_headers(),
        json={'host_name': 'host-a'},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['driver_errors']['adapter'] == 'linux_test_double'
    assert payload['driver_errors']['error_count'] == 1
    assert payload['driver_errors']['errors'][0]['reason'] == 'unsigned'


def test_detect_driver_errors_uses_windows_boundary(client, app_fixture):
    app_fixture.config['LOG_DRIVER_ERROR_ADAPTER'] = 'windows'
    app_fixture.config['LOG_DRIVER_ALLOWED_HOSTS'] = 'host-a'

    class _WindowsDriverErrorDouble:
        returncode = 0
        stdout = 'Display Driver|2.1|VendorB|False|unsigned\n'
        stderr = ''

    with patch(
        'server.services.log_service.LogService._run_windows_driver_error_command',
        return_value=_WindowsDriverErrorDouble(),
    ) as runner_double:
        response = client.post(
            '/api/logs/drivers/errors',
            headers=_headers(),
            json={'host_name': 'host-a'},
        )

    assert runner_double.call_count == 1
    command_args, command_kwargs = runner_double.call_args
    assert command_args[0][0:2] == ['powershell.exe', '-Command']
    assert 'IsSigned -eq $false' in command_args[0][2]
    assert command_args[1] == 8
    assert command_kwargs == {}

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['driver_errors']['adapter'] == 'windows'
    assert payload['driver_errors']['error_count'] == 1


def test_stream_events_uses_linux_test_double_path(client, app_fixture):
    app_fixture.config['LOG_EVENT_STREAM_ADAPTER'] = 'linux_test_double'
    app_fixture.config['LOG_INGESTION_ALLOWED_SOURCES'] = 'System'
    app_fixture.config['LOG_LINUX_EVENT_STREAM_TEST_DOUBLE'] = 'System=1|evtA||2|evtB||3|evtC'
    app_fixture.config['LOG_EVENT_STREAM_BATCH_SIZE'] = 2

    response = client.post(
        '/api/logs/events/stream',
        headers=_headers(),
        json={'source_name': 'System'},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['stream']['adapter'] == 'linux_test_double'
    assert payload['stream']['event_count'] == 2
    assert payload['stream']['next_cursor'] == '2'


def test_stream_events_uses_windows_boundary(client, app_fixture):
    app_fixture.config['LOG_EVENT_STREAM_ADAPTER'] = 'windows'
    app_fixture.config['LOG_INGESTION_ALLOWED_SOURCES'] = 'System'
    app_fixture.config['LOG_EVENT_STREAM_BATCH_SIZE'] = 2

    class _WindowsEventStreamDouble:
        returncode = 0
        stdout = (
            '101|2026-03-18T10:00:00Z|Error|1001|System|Disk failure\n'
            '102|2026-03-18T10:01:00Z|Warning|1002|System|Retry started\n'
        )
        stderr = ''

    with patch(
        'server.services.log_service.LogService._run_windows_event_stream_command',
        return_value=_WindowsEventStreamDouble(),
    ) as runner_double:
        response = client.post(
            '/api/logs/events/stream',
            headers=_headers(),
            json={'source_name': 'System'},
        )

    assert runner_double.call_count == 1
    command_args, command_kwargs = runner_double.call_args
    assert command_args[0][0:2] == ['powershell.exe', '-Command']
    assert "Get-WinEvent -LogName 'System'" in command_args[0][2]
    assert command_args[1] == 8
    assert command_kwargs == {}

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['stream']['adapter'] == 'windows'
    assert payload['stream']['event_count'] == 2
    assert payload['stream']['next_cursor'] == '102'


def test_search_logs_uses_linux_test_double_path(client, app_fixture):
    app_fixture.config['LOG_SEARCH_ADAPTER'] = 'linux_test_double'
    app_fixture.config['LOG_INGESTION_ALLOWED_SOURCES'] = 'System'
    app_fixture.config['LOG_LINUX_SEARCH_TEST_DOUBLE'] = (
        'System=2026-03-18T10:00:00Z|error|1001|System|Disk failure detected'
        '||2026-03-18T10:01:00Z|warning|1002|System|Disk retry started'
        '||2026-03-18T10:02:00Z|info|1003|System|Network stable'
    )
    app_fixture.config['LOG_SEARCH_MAX_RESULTS'] = 10

    response = client.post(
        '/api/logs/search',
        headers=_headers(),
        json={
            'source_name': 'System',
            'query_text': 'Disk',
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['status'] == 'success'
    assert payload['search']['adapter'] == 'linux_test_double'
    assert payload['search']['result_count'] == 2
    assert payload['search']['index']['document_count'] == 2
    assert 'disk' in payload['search']['index']['tokens']


def test_search_logs_uses_windows_boundary(client, app_fixture):
    app_fixture.config['LOG_SEARCH_ADAPTER'] = 'windows'
    app_fixture.config['LOG_INGESTION_ALLOWED_SOURCES'] = 'System'
    app_fixture.config['LOG_SEARCH_MAX_RESULTS'] = 3

    class _WindowsLogSearchDouble:
        returncode = 0
        stdout = (
            '2026-03-18T10:00:00Z|Error|1001|System|Disk failure detected\n'
            '2026-03-18T10:01:00Z|Warning|1002|System|Disk retry started\n'
        )
        stderr = ''

    with patch(
        'server.services.log_service.LogService._run_windows_log_search_command',
        return_value=_WindowsLogSearchDouble(),
    ) as runner_double:
        response = client.post(
            '/api/logs/search',
            headers=_headers(),
            json={
                'source_name': 'System',
                'query_text': 'Disk',
            },
        )

    assert runner_double.call_count == 1
    command_args, command_kwargs = runner_double.call_args
    assert command_args[0][0:2] == ['powershell.exe', '-Command']
    assert "Get-WinEvent -LogName 'System'" in command_args[0][2]
    assert "Where-Object { $_.Message -like '*Disk*' }" in command_args[0][2]
    assert command_args[1] == 8
    assert command_kwargs == {}

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['status'] == 'success'
    assert payload['search']['adapter'] == 'windows'
    assert payload['search']['result_count'] == 2
    assert payload['search']['index']['token_count'] >= 1
