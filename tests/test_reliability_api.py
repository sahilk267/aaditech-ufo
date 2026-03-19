"""Tests for Phase 2 Week 15 reliability history foundation."""

from unittest.mock import patch

from server.auth import get_api_key


def _headers(tenant_slug=None):
    headers = {'X-API-Key': get_api_key()}
    if tenant_slug:
        headers['X-Tenant-Slug'] = tenant_slug
    return headers


def test_reliability_history_uses_linux_test_double_path(client, app_fixture):
    app_fixture.config['RELIABILITY_HISTORY_ADAPTER'] = 'linux_test_double'
    app_fixture.config['RELIABILITY_ALLOWED_HOSTS'] = 'host-a,host-b'
    app_fixture.config['RELIABILITY_LINUX_HISTORY_TEST_DOUBLE'] = (
        'host-a=2026-03-18T11:00:00Z|Application Error|sample.exe|1000|Crash detected'
        '||2026-03-18T11:02:00Z|Windows Error Reporting|sample.exe|1001|Recovery completed'
    )
    app_fixture.config['RELIABILITY_HISTORY_MAX_RECORDS'] = 10

    response = client.post(
        '/api/reliability/history',
        headers=_headers(),
        json={'host_name': 'host-a'},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['status'] == 'success'
    assert payload['history']['adapter'] == 'linux_test_double'
    assert payload['history']['record_count'] == 2
    assert payload['history']['records'][0]['source'] == 'Application Error'


def test_reliability_history_uses_windows_boundary(client, app_fixture):
    app_fixture.config['RELIABILITY_HISTORY_ADAPTER'] = 'windows'
    app_fixture.config['RELIABILITY_ALLOWED_HOSTS'] = 'host-a'
    app_fixture.config['RELIABILITY_HISTORY_MAX_RECORDS'] = 2

    class _WindowsReliabilityHistoryDouble:
        returncode = 0
        stdout = (
            '2026-03-18T11:00:00Z|Application Error|sample.exe|1000|Crash detected\n'
            '2026-03-18T11:02:00Z|Windows Error Reporting|sample.exe|1001|Recovery completed\n'
        )
        stderr = ''

    with patch(
        'server.services.reliability_service.ReliabilityService._run_windows_reliability_history_command',
        return_value=_WindowsReliabilityHistoryDouble(),
    ) as runner_double:
        response = client.post(
            '/api/reliability/history',
            headers=_headers(),
            json={'host_name': 'host-a'},
        )

    assert runner_double.call_count == 1
    command_args, command_kwargs = runner_double.call_args
    assert command_args[0][0:2] == ['powershell.exe', '-Command']
    assert 'Win32_ReliabilityRecords' in command_args[0][2]
    assert "-ComputerName 'host-a'" in command_args[0][2]
    assert command_args[1] == 8
    assert command_kwargs == {}

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['status'] == 'success'
    assert payload['history']['adapter'] == 'windows'
    assert payload['history']['record_count'] == 2


def test_parse_crash_dump_uses_linux_test_double_path(client, app_fixture):
    app_fixture.config['RELIABILITY_CRASH_DUMP_ADAPTER'] = 'linux_test_double'
    app_fixture.config['RELIABILITY_ALLOWED_HOSTS'] = 'host-a,host-b'
    app_fixture.config['RELIABILITY_ALLOWED_DUMP_ROOTS'] = r'C:\CrashDumps'
    app_fixture.config['RELIABILITY_CRASH_DUMP_ROOT'] = r'C:\CrashDumps'
    app_fixture.config['RELIABILITY_LINUX_CRASH_DUMP_TEST_DOUBLE'] = (
        'host-a:app-crash-001.dmp=app-crash-001.dmp|4096|2026-03-18T11:30:00Z|.dmp|C:\\CrashDumps'
    )

    response = client.post(
        '/api/reliability/crash-dumps/parse',
        headers=_headers(),
        json={'host_name': 'host-a', 'dump_name': 'app-crash-001.dmp'},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['status'] == 'success'
    assert payload['crash_dump']['adapter'] == 'linux_test_double'
    assert payload['crash_dump']['parsed_dump']['dump_type'] == 'full_dump'
    assert payload['crash_dump']['parsed_dump']['size_bytes'] == 4096
    assert payload['crash_dump']['parsed_dump']['fault_bucket'] == 'app-crash-001'


def test_parse_crash_dump_uses_windows_boundary(client, app_fixture):
    app_fixture.config['RELIABILITY_CRASH_DUMP_ADAPTER'] = 'windows'
    app_fixture.config['RELIABILITY_ALLOWED_HOSTS'] = 'host-a'
    app_fixture.config['RELIABILITY_ALLOWED_DUMP_ROOTS'] = r'C:\CrashDumps'
    app_fixture.config['RELIABILITY_CRASH_DUMP_ROOT'] = r'C:\CrashDumps'

    class _WindowsCrashDumpParseDouble:
        returncode = 0
        stdout = 'app-crash-001.dmp|4096|2026-03-18T11:30:00Z|.dmp|C:\\CrashDumps\n'
        stderr = ''

    with patch(
        'server.services.reliability_service.ReliabilityService._run_windows_crash_dump_parse_command',
        return_value=_WindowsCrashDumpParseDouble(),
    ) as runner_double:
        response = client.post(
            '/api/reliability/crash-dumps/parse',
            headers=_headers(),
            json={'host_name': 'host-a', 'dump_name': 'app-crash-001.dmp'},
        )

    assert runner_double.call_count == 1
    command_args, command_kwargs = runner_double.call_args
    assert command_args[0][0:2] == ['powershell.exe', '-Command']
    assert "Get-Item -Path 'C:\\CrashDumps\\app-crash-001.dmp'" in command_args[0][2]
    assert command_args[1] == 8
    assert command_kwargs == {}

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['status'] == 'success'
    assert payload['crash_dump']['adapter'] == 'windows'
    assert payload['crash_dump']['parsed_dump']['primary_module'] == 'app'
    assert payload['crash_dump']['parsed_dump']['dump_type'] == 'full_dump'


def test_identify_exception_uses_linux_test_double_path(client, app_fixture):
    app_fixture.config['RELIABILITY_EXCEPTION_IDENTIFIER_ADAPTER'] = 'linux_test_double'
    app_fixture.config['RELIABILITY_ALLOWED_HOSTS'] = 'host-a,host-b'
    app_fixture.config['RELIABILITY_ALLOWED_DUMP_ROOTS'] = r'C:\CrashDumps'
    app_fixture.config['RELIABILITY_CRASH_DUMP_ROOT'] = r'C:\CrashDumps'
    app_fixture.config['RELIABILITY_LINUX_EXCEPTION_TEST_DOUBLE'] = (
        'host-a:access-violation-app.dmp=0xc0000005|access_violation|high|test_double_signature'
    )

    response = client.post(
        '/api/reliability/exceptions/identify',
        headers=_headers(),
        json={'host_name': 'host-a', 'dump_name': 'access-violation-app.dmp'},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['status'] == 'success'
    assert payload['exception']['adapter'] == 'linux_test_double'
    assert payload['exception']['identified_exception']['exception_code'] == '0xc0000005'
    assert payload['exception']['identified_exception']['exception_name'] == 'access_violation'
    assert payload['exception']['identified_exception']['confidence'] == 'high'


def test_identify_exception_uses_windows_boundary(client, app_fixture):
    app_fixture.config['RELIABILITY_EXCEPTION_IDENTIFIER_ADAPTER'] = 'windows'
    app_fixture.config['RELIABILITY_ALLOWED_HOSTS'] = 'host-a'
    app_fixture.config['RELIABILITY_ALLOWED_DUMP_ROOTS'] = r'C:\CrashDumps'
    app_fixture.config['RELIABILITY_CRASH_DUMP_ROOT'] = r'C:\CrashDumps'

    class _WindowsExceptionIdentifierDouble:
        returncode = 0
        stdout = 'access-violation-app.dmp\n'
        stderr = ''

    with patch(
        'server.services.reliability_service.ReliabilityService._run_windows_exception_identifier_command',
        return_value=_WindowsExceptionIdentifierDouble(),
    ) as runner_double:
        response = client.post(
            '/api/reliability/exceptions/identify',
            headers=_headers(),
            json={'host_name': 'host-a', 'dump_name': 'access-violation-app.dmp'},
        )

    assert runner_double.call_count == 1
    command_args, command_kwargs = runner_double.call_args
    assert command_args[0][0:2] == ['powershell.exe', '-Command']
    assert "Get-Item -Path 'C:\\CrashDumps\\access-violation-app.dmp'" in command_args[0][2]
    assert command_args[1] == 8
    assert command_kwargs == {}

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['status'] == 'success'
    assert payload['exception']['adapter'] == 'windows'
    assert payload['exception']['identified_exception']['exception_code'] == '0xc0000005'
    assert payload['exception']['identified_exception']['exception_name'] == 'access_violation'


def test_analyze_stack_trace_uses_linux_test_double_path(client, app_fixture):
    app_fixture.config['RELIABILITY_STACK_TRACE_ADAPTER'] = 'linux_test_double'
    app_fixture.config['RELIABILITY_ALLOWED_HOSTS'] = 'host-a,host-b'
    app_fixture.config['RELIABILITY_ALLOWED_DUMP_ROOTS'] = r'C:\CrashDumps'
    app_fixture.config['RELIABILITY_CRASH_DUMP_ROOT'] = r'C:\CrashDumps'
    app_fixture.config['RELIABILITY_LINUX_STACK_TRACE_TEST_DOUBLE'] = (
        'host-a:access-violation-app.dmp=ntdll!KiUserExceptionDispatch>app!CrashHandler>kernel32!BaseThreadInitThunk'
    )

    response = client.post(
        '/api/reliability/stack-traces/analyze',
        headers=_headers(),
        json={'host_name': 'host-a', 'dump_name': 'access-violation-app.dmp'},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['status'] == 'success'
    assert payload['stack_trace']['adapter'] == 'linux_test_double'
    assert payload['stack_trace']['stack_trace']['frame_count'] == 3
    assert payload['stack_trace']['stack_trace']['top_frame'] == 'ntdll!KiUserExceptionDispatch'
    assert 'app!CrashHandler' in payload['stack_trace']['stack_trace']['normalized_signature']


def test_analyze_stack_trace_uses_windows_boundary(client, app_fixture):
    app_fixture.config['RELIABILITY_STACK_TRACE_ADAPTER'] = 'windows'
    app_fixture.config['RELIABILITY_ALLOWED_HOSTS'] = 'host-a'
    app_fixture.config['RELIABILITY_ALLOWED_DUMP_ROOTS'] = r'C:\CrashDumps'
    app_fixture.config['RELIABILITY_CRASH_DUMP_ROOT'] = r'C:\CrashDumps'

    class _WindowsStackTraceDouble:
        returncode = 0
        stdout = 'access-violation-app.dmp\n'
        stderr = ''

    with patch(
        'server.services.reliability_service.ReliabilityService._run_windows_stack_trace_command',
        return_value=_WindowsStackTraceDouble(),
    ) as runner_double:
        response = client.post(
            '/api/reliability/stack-traces/analyze',
            headers=_headers(),
            json={'host_name': 'host-a', 'dump_name': 'access-violation-app.dmp'},
        )

    assert runner_double.call_count == 1
    command_args, command_kwargs = runner_double.call_args
    assert command_args[0][0:2] == ['powershell.exe', '-Command']
    assert "Get-Item -Path 'C:\\CrashDumps\\access-violation-app.dmp'" in command_args[0][2]
    assert command_args[1] == 8
    assert command_kwargs == {}

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['status'] == 'success'
    assert payload['stack_trace']['adapter'] == 'windows'
    assert payload['stack_trace']['stack_trace']['frame_count'] == 3
    assert payload['stack_trace']['stack_trace']['top_frame'] == 'ntdll!KiUserExceptionDispatch'


def test_score_reliability_uses_linux_test_double_path(client, app_fixture):
    app_fixture.config['RELIABILITY_SCORER_ADAPTER'] = 'linux_test_double'
    app_fixture.config['RELIABILITY_ALLOWED_HOSTS'] = 'host-a,host-b'
    app_fixture.config['RELIABILITY_LINUX_SCORER_TEST_DOUBLE'] = 'host-a=2026-03-18T12:00:00Z|8.7'

    response = client.post(
        '/api/reliability/score',
        headers=_headers(),
        json={'host_name': 'host-a'},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['status'] == 'success'
    assert payload['reliability']['adapter'] == 'linux_test_double'
    assert payload['reliability']['reliability_score']['current_score'] == 8.7
    assert payload['reliability']['reliability_score']['health_band'] == 'excellent'


def test_score_reliability_uses_windows_boundary(client, app_fixture):
    app_fixture.config['RELIABILITY_SCORER_ADAPTER'] = 'windows'
    app_fixture.config['RELIABILITY_ALLOWED_HOSTS'] = 'host-a'

    class _WindowsReliabilityScoreDouble:
        returncode = 0
        stdout = '2026-03-18T12:00:00Z|7.4\n'
        stderr = ''

    with patch(
        'server.services.reliability_service.ReliabilityService._run_windows_reliability_score_command',
        return_value=_WindowsReliabilityScoreDouble(),
    ) as runner_double:
        response = client.post(
            '/api/reliability/score',
            headers=_headers(),
            json={'host_name': 'host-a'},
        )

    assert runner_double.call_count == 1
    command_args, command_kwargs = runner_double.call_args
    assert command_args[0][0:2] == ['powershell.exe', '-Command']
    assert 'Win32_ReliabilityStabilityMetrics' in command_args[0][2]
    assert "-ComputerName 'host-a'" in command_args[0][2]
    assert command_args[1] == 8
    assert command_kwargs == {}

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['status'] == 'success'
    assert payload['reliability']['adapter'] == 'windows'
    assert payload['reliability']['reliability_score']['current_score'] == 7.4
    assert payload['reliability']['reliability_score']['health_band'] == 'good'


def test_analyze_reliability_trend_uses_linux_test_double_path(client, app_fixture):
    app_fixture.config['RELIABILITY_TREND_ADAPTER'] = 'linux_test_double'
    app_fixture.config['RELIABILITY_ALLOWED_HOSTS'] = 'host-a,host-b'
    app_fixture.config['RELIABILITY_TREND_WINDOW_SIZE'] = 4
    app_fixture.config['RELIABILITY_LINUX_TREND_TEST_DOUBLE'] = (
        'host-a=2026-03-18T12:00:00Z|6.2\n'
        '2026-03-18T12:10:00Z|6.5\n'
        '2026-03-18T12:20:00Z|6.8\n'
        '2026-03-18T12:30:00Z|7.1'
    )

    response = client.post(
        '/api/reliability/trends/analyze',
        headers=_headers(),
        json={'host_name': 'host-a'},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['status'] == 'success'
    assert payload['trend']['adapter'] == 'linux_test_double'
    assert payload['trend']['trend']['point_count'] == 4
    assert payload['trend']['trend']['direction'] == 'improving'
    assert payload['trend']['trend']['latest_score'] == 7.1


def test_analyze_reliability_trend_uses_windows_boundary(client, app_fixture):
    app_fixture.config['RELIABILITY_TREND_ADAPTER'] = 'windows'
    app_fixture.config['RELIABILITY_ALLOWED_HOSTS'] = 'host-a'
    app_fixture.config['RELIABILITY_TREND_WINDOW_SIZE'] = 3

    class _WindowsReliabilityTrendDouble:
        returncode = 0
        stdout = '2026-03-18T12:00:00Z|7.1\n2026-03-18T12:10:00Z|7.0\n2026-03-18T12:20:00Z|6.8\n'
        stderr = ''

    with patch(
        'server.services.reliability_service.ReliabilityService._run_windows_reliability_trend_command',
        return_value=_WindowsReliabilityTrendDouble(),
    ) as runner_double:
        response = client.post(
            '/api/reliability/trends/analyze',
            headers=_headers(),
            json={'host_name': 'host-a'},
        )

    assert runner_double.call_count == 1
    command_args, command_kwargs = runner_double.call_args
    assert command_args[0][0:2] == ['powershell.exe', '-Command']
    assert 'Win32_ReliabilityStabilityMetrics' in command_args[0][2]
    assert "-ComputerName 'host-a'" in command_args[0][2]
    assert command_args[1] == 8
    assert command_kwargs == {}

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['status'] == 'success'
    assert payload['trend']['adapter'] == 'windows'
    assert payload['trend']['trend']['point_count'] == 3
    assert payload['trend']['trend']['direction'] == 'declining'


def test_analyze_reliability_prediction_uses_linux_test_double_path(client, app_fixture):
    app_fixture.config['RELIABILITY_PREDICTION_ADAPTER'] = 'linux_test_double'
    app_fixture.config['RELIABILITY_ALLOWED_HOSTS'] = 'host-a,host-b'
    app_fixture.config['RELIABILITY_PREDICTION_WINDOW_SIZE'] = 4
    app_fixture.config['RELIABILITY_PREDICTION_HORIZON'] = 2
    app_fixture.config['RELIABILITY_LINUX_PREDICTION_TEST_DOUBLE'] = (
        'host-a=2026-03-18T12:00:00Z|6.0\n'
        '2026-03-18T12:10:00Z|6.2\n'
        '2026-03-18T12:20:00Z|6.4\n'
        '2026-03-18T12:30:00Z|6.6'
    )

    response = client.post(
        '/api/reliability/predictions/analyze',
        headers=_headers(),
        json={'host_name': 'host-a'},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['status'] == 'success'
    assert payload['prediction']['adapter'] == 'linux_test_double'
    assert payload['prediction']['prediction']['point_count'] == 4
    assert payload['prediction']['prediction']['direction'] == 'improving'
    assert payload['prediction']['prediction']['predicted_score'] == 7.0


def test_analyze_reliability_prediction_uses_windows_boundary(client, app_fixture):
    app_fixture.config['RELIABILITY_PREDICTION_ADAPTER'] = 'windows'
    app_fixture.config['RELIABILITY_ALLOWED_HOSTS'] = 'host-a'
    app_fixture.config['RELIABILITY_PREDICTION_WINDOW_SIZE'] = 3
    app_fixture.config['RELIABILITY_PREDICTION_HORIZON'] = 2

    class _WindowsReliabilityPredictionDouble:
        returncode = 0
        stdout = '2026-03-18T12:00:00Z|7.1\n2026-03-18T12:10:00Z|7.0\n2026-03-18T12:20:00Z|6.8\n'
        stderr = ''

    with patch(
        'server.services.reliability_service.ReliabilityService._run_windows_reliability_prediction_command',
        return_value=_WindowsReliabilityPredictionDouble(),
    ) as runner_double:
        response = client.post(
            '/api/reliability/predictions/analyze',
            headers=_headers(),
            json={'host_name': 'host-a'},
        )

    assert runner_double.call_count == 1
    command_args, command_kwargs = runner_double.call_args
    assert command_args[0][0:2] == ['powershell.exe', '-Command']
    assert 'Win32_ReliabilityStabilityMetrics' in command_args[0][2]
    assert "-ComputerName 'host-a'" in command_args[0][2]
    assert command_args[1] == 8
    assert command_kwargs == {}

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['status'] == 'success'
    assert payload['prediction']['adapter'] == 'windows'
    assert payload['prediction']['prediction']['point_count'] == 3
    assert payload['prediction']['prediction']['direction'] == 'declining'
    assert payload['prediction']['prediction']['predicted_score'] == 6.5


def test_detect_reliability_patterns_uses_linux_test_double_path(client, app_fixture):
    app_fixture.config['RELIABILITY_PATTERN_ADAPTER'] = 'linux_test_double'
    app_fixture.config['RELIABILITY_ALLOWED_HOSTS'] = 'host-a,host-b'
    app_fixture.config['RELIABILITY_PATTERN_WINDOW_SIZE'] = 6
    app_fixture.config['RELIABILITY_LINUX_PATTERN_TEST_DOUBLE'] = (
        'host-a=2026-03-18T12:00:00Z|7.5\n'
        '2026-03-18T12:10:00Z|7.2\n'
        '2026-03-18T12:20:00Z|6.9\n'
        '2026-03-18T12:30:00Z|6.6\n'
        '2026-03-18T12:40:00Z|6.4'
    )

    response = client.post(
        '/api/reliability/patterns/detect',
        headers=_headers(),
        json={'host_name': 'host-a'},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['status'] == 'success'
    assert payload['patterns']['adapter'] == 'linux_test_double'
    assert payload['patterns']['patterns']['primary_pattern'] == 'recurring_degradation'
    assert payload['patterns']['patterns']['pattern_count'] >= 1


def test_detect_reliability_patterns_uses_windows_boundary(client, app_fixture):
    app_fixture.config['RELIABILITY_PATTERN_ADAPTER'] = 'windows'
    app_fixture.config['RELIABILITY_ALLOWED_HOSTS'] = 'host-a'
    app_fixture.config['RELIABILITY_PATTERN_WINDOW_SIZE'] = 5

    class _WindowsReliabilityPatternDouble:
        returncode = 0
        stdout = (
            '2026-03-18T12:00:00Z|7.0\n'
            '2026-03-18T12:10:00Z|7.3\n'
            '2026-03-18T12:20:00Z|6.9\n'
            '2026-03-18T12:30:00Z|7.2\n'
            '2026-03-18T12:40:00Z|6.8\n'
        )
        stderr = ''

    with patch(
        'server.services.reliability_service.ReliabilityService._run_windows_reliability_pattern_command',
        return_value=_WindowsReliabilityPatternDouble(),
    ) as runner_double:
        response = client.post(
            '/api/reliability/patterns/detect',
            headers=_headers(),
            json={'host_name': 'host-a'},
        )

    assert runner_double.call_count == 1
    command_args, command_kwargs = runner_double.call_args
    assert command_args[0][0:2] == ['powershell.exe', '-Command']
    assert 'Win32_ReliabilityStabilityMetrics' in command_args[0][2]
    assert "-ComputerName 'host-a'" in command_args[0][2]
    assert command_args[1] == 8
    assert command_kwargs == {}

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['status'] == 'success'
    assert payload['patterns']['adapter'] == 'windows'
    assert payload['patterns']['patterns']['primary_pattern'] == 'oscillation'
    assert payload['patterns']['patterns']['pattern_count'] >= 1
