"""Tests for Phase 2 Week 11-12 automation workflow foundation."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from server.auth import get_api_key
from server.extensions import db
from server.models import AutomationWorkflow, Organization, WorkflowRun


def _headers(tenant_slug=None):
    headers = {'X-API-Key': get_api_key()}
    if tenant_slug:
        headers['X-Tenant-Slug'] = tenant_slug
    return headers


def test_create_and_list_automation_workflow(client):
    create = client.post(
        '/api/automation/workflows',
        headers=_headers(),
        json={
            'name': 'Restart Critical Service',
            'trigger_type': 'alert',
            'trigger_conditions': {
                'severity_in': ['critical'],
                'metric_in': ['cpu_usage'],
                'min_alert_count': 1,
            },
            'action_type': 'service_restart',
            'action_config': {'service_name': 'nginx'},
            'is_active': True,
        },
    )
    assert create.status_code == 201

    listed = client.get('/api/automation/workflows', headers=_headers())
    assert listed.status_code == 200
    payload = listed.get_json()

    assert payload['count'] >= 1
    assert any(item['name'] == 'Restart Critical Service' for item in payload['workflows'])


def test_automation_workflows_are_tenant_scoped(client, app_fixture):
    with app_fixture.app_context():
        beta = Organization(name='Auto Beta', slug='auto-beta', is_active=True)
        db.session.add(beta)
        db.session.commit()

    create_beta = client.post(
        '/api/automation/workflows',
        headers=_headers('auto-beta'),
        json={
            'name': 'Beta CPU Remedy',
            'trigger_type': 'alert',
            'trigger_conditions': {'metric_in': ['cpu_usage']},
            'action_type': 'service_restart',
            'action_config': {'service_name': 'app-beta'},
        },
    )
    assert create_beta.status_code == 201

    default_list = client.get('/api/automation/workflows', headers=_headers())
    assert default_list.status_code == 200
    default_names = {wf['name'] for wf in default_list.get_json()['workflows']}
    assert 'Beta CPU Remedy' not in default_names


def test_evaluate_automation_alert_triggers(client):
    create = client.post(
        '/api/automation/workflows',
        headers=_headers(),
        json={
            'name': 'Critical CPU Auto Action',
            'trigger_type': 'alert',
            'trigger_conditions': {
                'severity_in': ['critical'],
                'metric_in': ['cpu_usage'],
                'min_actual_value': 90,
                'min_alert_count': 1,
            },
            'action_type': 'script_execute',
            'action_config': {'script_path': '/opt/actions/remediate.sh'},
        },
    )
    assert create.status_code == 201

    evaluate = client.post(
        '/api/automation/evaluate',
        headers=_headers(),
        json={
            'alerts': [
                {'severity': 'warning', 'metric': 'cpu_usage', 'actual_value': 75},
                {'severity': 'critical', 'metric': 'cpu_usage', 'actual_value': 97},
                {'severity': 'critical', 'metric': 'ram_usage', 'actual_value': 95},
            ]
        },
    )
    assert evaluate.status_code == 200

    payload = evaluate.get_json()
    assert payload['matched_workflow_count'] >= 1
    target_match = next(
        (item for item in payload['matches'] if item['workflow']['name'] == 'Critical CPU Auto Action'),
        None,
    )
    assert target_match is not None
    assert target_match['matched_alert_count'] == 1


def test_execute_automation_workflow_updates_last_triggered(client, app_fixture):
    create = client.post(
        '/api/automation/workflows',
        headers=_headers(),
        json={
            'name': 'Execute Restart',
            'trigger_type': 'manual',
            'trigger_conditions': {},
            'action_type': 'service_restart',
            'action_config': {'service_name': 'redis'},
        },
    )
    assert create.status_code == 201
    workflow_id = create.get_json()['workflow']['id']

    class _CompletedProcessDouble:
        returncode = 0
        stdout = 'ok'
        stderr = ''

    with patch(
        'server.services.automation_service.AutomationService._run_service_restart_command',
        return_value=_CompletedProcessDouble(),
    ) as runner_double:
        execute = client.post(
            f'/api/automation/workflows/{workflow_id}/execute',
            headers=_headers(),
            json={
                'dry_run': False,
                'payload': {'source': 'test-suite'},
            },
        )

    assert runner_double.call_count == 1
    command_args, command_kwargs = runner_double.call_args
    assert command_args[0] == ['systemctl', 'restart', 'redis']
    assert command_args[1] == 8
    assert command_kwargs == {}
    assert execute.status_code == 202

    job = execute.get_json()['job']
    assert job['accepted'] is True
    assert job['job_name'] == 'execute_automation_workflow'
    assert job.get('inline') is True
    assert job['result']['status'] == 'success'

    with app_fixture.app_context():
        workflow = db.session.get(AutomationWorkflow, workflow_id)
        assert workflow is not None
        assert workflow.last_triggered_at is not None
        workflow_run = (
            WorkflowRun.query
            .filter_by(workflow_id=workflow_id)
            .order_by(WorkflowRun.id.desc())
            .first()
        )
        assert workflow_run is not None
        assert workflow_run.status == 'executed'
        assert workflow_run.trigger_source == 'manual'


def test_execute_automation_workflow_blocks_service_outside_allowlist(client, app_fixture):
    app_fixture.config['AUTOMATION_ALLOWED_SERVICES'] = 'nginx,postgresql'

    create = client.post(
        '/api/automation/workflows',
        headers=_headers(),
        json={
            'name': 'Disallowed Service Restart',
            'trigger_type': 'manual',
            'trigger_conditions': {},
            'action_type': 'service_restart',
            'action_config': {'service_name': 'redis'},
        },
    )
    assert create.status_code == 201
    workflow_id = create.get_json()['workflow']['id']

    with patch('server.services.automation_service.AutomationService._run_service_restart_command') as runner_double:
        execute = client.post(
            f'/api/automation/workflows/{workflow_id}/execute',
            headers=_headers(),
            json={'dry_run': False},
        )

    assert execute.status_code == 202
    job = execute.get_json()['job']
    assert job['result']['status'] == 'failed'
    assert job['result']['reason'] == 'execution_failed'
    assert runner_double.call_count == 0

    with app_fixture.app_context():
        workflow = db.session.get(AutomationWorkflow, workflow_id)
        assert workflow is not None
        assert workflow.last_triggered_at is None


def test_execute_script_workflow_runs_allowlisted_script(client, app_fixture):
    with TemporaryDirectory() as temp_dir:
        script_path = Path(temp_dir) / 'cleanup.cmd'
        script_path.write_text('@echo off\necho cleanup\n', encoding='utf-8')

        app_fixture.config['AUTOMATION_SCRIPT_EXECUTOR_ADAPTER'] = 'subprocess'
        app_fixture.config['AUTOMATION_ALLOWED_SCRIPT_ROOTS'] = temp_dir

        create = client.post(
            '/api/automation/workflows',
            headers=_headers(),
            json={
                'name': 'Execute Cleanup Script',
                'trigger_type': 'manual',
                'trigger_conditions': {},
                'action_type': 'script_execute',
                'action_config': {
                    'script_path': str(script_path),
                    'args': ['--tenant', 'default'],
                },
            },
        )
        assert create.status_code == 201
        workflow_id = create.get_json()['workflow']['id']

        class _CompletedProcessDouble:
            returncode = 0
            stdout = 'cleanup complete'
            stderr = ''

        with patch(
            'server.services.automation_service.AutomationService._run_script_command',
            return_value=_CompletedProcessDouble(),
        ) as runner_double:
            execute = client.post(
                f'/api/automation/workflows/{workflow_id}/execute',
                headers=_headers(),
                json={'dry_run': False},
            )

    assert execute.status_code == 202
    assert runner_double.call_count == 1
    command_args, command_kwargs = runner_double.call_args
    assert command_args[0] == [str(script_path.resolve()), '--tenant', 'default']
    assert command_args[1] == 8
    assert command_kwargs == {}

    payload = execute.get_json()['job']['result']
    assert payload['status'] == 'success'
    assert payload['result']['action_result']['status'] == 'success'
    assert payload['result']['action_result']['adapter'] == 'subprocess'


def test_execute_script_workflow_blocks_path_outside_allowlist(client, app_fixture):
    with TemporaryDirectory() as allowed_dir, TemporaryDirectory() as blocked_dir:
        script_path = Path(blocked_dir) / 'cleanup.cmd'
        script_path.write_text('@echo off\necho cleanup\n', encoding='utf-8')

        app_fixture.config['AUTOMATION_SCRIPT_EXECUTOR_ADAPTER'] = 'subprocess'
        app_fixture.config['AUTOMATION_ALLOWED_SCRIPT_ROOTS'] = allowed_dir

        create = client.post(
            '/api/automation/workflows',
            headers=_headers(),
            json={
                'name': 'Blocked Cleanup Script',
                'trigger_type': 'manual',
                'trigger_conditions': {},
                'action_type': 'script_execute',
                'action_config': {'script_path': str(script_path)},
            },
        )
        assert create.status_code == 201
        workflow_id = create.get_json()['workflow']['id']

        with patch('server.services.automation_service.AutomationService._run_script_command') as runner_double:
            execute = client.post(
                f'/api/automation/workflows/{workflow_id}/execute',
                headers=_headers(),
                json={'dry_run': False},
            )

    assert execute.status_code == 202
    assert runner_double.call_count == 0
    payload = execute.get_json()['job']['result']
    assert payload['status'] == 'failed'
    assert payload['reason'] == 'execution_failed'
    assert payload['result']['action_result']['reason'] == 'script_path_not_allowlisted'


def test_execute_webhook_workflow_calls_allowlisted_host(client, app_fixture):
    app_fixture.config['AUTOMATION_WEBHOOK_ADAPTER'] = 'urllib'
    app_fixture.config['AUTOMATION_ALLOWED_WEBHOOK_HOSTS'] = 'hooks.example.com'

    create = client.post(
        '/api/automation/workflows',
        headers=_headers(),
        json={
            'name': 'Notify Webhook',
            'trigger_type': 'manual',
            'trigger_conditions': {},
            'action_type': 'webhook_call',
            'action_config': {
                'url': 'https://hooks.example.com/automation',
                'method': 'POST',
                'headers': {'X-Test': '1'},
                'body': {'event': 'automation.executed'},
            },
        },
    )
    assert create.status_code == 201
    workflow_id = create.get_json()['workflow']['id']

    class _ResponseDouble:
        status = 202

        def read(self):
            return b'accepted'

    with patch(
        'server.services.automation_service.AutomationService._perform_webhook_request',
        return_value=_ResponseDouble(),
    ) as request_double:
        execute = client.post(
            f'/api/automation/workflows/{workflow_id}/execute',
            headers=_headers(),
            json={'dry_run': False},
        )

    assert execute.status_code == 202
    assert request_double.call_count == 1
    request_args, request_kwargs = request_double.call_args
    assert request_args[1] == 5
    assert request_kwargs == {}
    assert request_args[0].full_url == 'https://hooks.example.com/automation'
    assert request_args[0].method == 'POST'

    payload = execute.get_json()['job']['result']
    assert payload['status'] == 'success'
    assert payload['result']['action_result']['status'] == 'success'
    assert payload['result']['action_result']['host'] == 'hooks.example.com'


def test_execute_webhook_workflow_blocks_unallowlisted_host(client, app_fixture):
    app_fixture.config['AUTOMATION_WEBHOOK_ADAPTER'] = 'urllib'
    app_fixture.config['AUTOMATION_ALLOWED_WEBHOOK_HOSTS'] = 'hooks.example.com'

    create = client.post(
        '/api/automation/workflows',
        headers=_headers(),
        json={
            'name': 'Blocked Webhook',
            'trigger_type': 'manual',
            'trigger_conditions': {},
            'action_type': 'webhook_call',
            'action_config': {'url': 'https://evil.example.net/automation'},
        },
    )
    assert create.status_code == 201
    workflow_id = create.get_json()['workflow']['id']

    with patch('server.services.automation_service.AutomationService._perform_webhook_request') as request_double:
        execute = client.post(
            f'/api/automation/workflows/{workflow_id}/execute',
            headers=_headers(),
            json={'dry_run': False},
        )

    assert execute.status_code == 202
    assert request_double.call_count == 0
    payload = execute.get_json()['job']['result']
    assert payload['status'] == 'failed'
    assert payload['reason'] == 'execution_failed'
    assert payload['result']['action_result']['reason'] == 'webhook_host_not_allowlisted'


def test_get_service_status_uses_linux_test_double_path(client, app_fixture):
    app_fixture.config['AUTOMATION_ALLOWED_SERVICES'] = 'redis,nginx'
    app_fixture.config['AUTOMATION_SERVICE_STATUS_ADAPTER'] = 'linux_test_double'
    app_fixture.config['AUTOMATION_LINUX_SERVICE_STATUS_TEST_DOUBLE'] = 'redis=running,nginx=stopped'

    response = client.post(
        '/api/automation/services/status',
        headers=_headers(),
        json={'service_name': 'redis'},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['status'] == 'success'
    assert payload['service']['adapter'] == 'linux_test_double'
    assert payload['service']['service_state'] == 'running'


def test_get_service_status_uses_windows_adapter_boundary(client, app_fixture):
    app_fixture.config['AUTOMATION_ALLOWED_SERVICES'] = 'Spooler'
    app_fixture.config['AUTOMATION_SERVICE_STATUS_ADAPTER'] = 'windows'

    class _WindowsCompletedProcessDouble:
        returncode = 0
        stdout = 'SERVICE_NAME: Spooler\n        STATE              : 4  RUNNING'
        stderr = ''

    with patch(
        'server.services.automation_service.AutomationService._run_windows_service_query_command',
        return_value=_WindowsCompletedProcessDouble(),
    ) as runner_double:
        response = client.post(
            '/api/automation/services/status',
            headers=_headers(),
            json={'service_name': 'Spooler'},
        )

    assert runner_double.call_count == 1
    command_args, command_kwargs = runner_double.call_args
    assert command_args[0] == ['sc', 'query', 'Spooler']
    assert command_args[1] == 8
    assert command_kwargs == {}

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['service']['adapter'] == 'windows'
    assert payload['service']['service_state'] == 'running'


def test_get_service_dependencies_uses_linux_test_double_path(client, app_fixture):
    app_fixture.config['AUTOMATION_ALLOWED_SERVICES'] = 'redis,nginx'
    app_fixture.config['AUTOMATION_SERVICE_DEPENDENCY_ADAPTER'] = 'linux_test_double'
    app_fixture.config['AUTOMATION_LINUX_SERVICE_DEPENDENCY_TEST_DOUBLE'] = 'redis=network.target|syslog.socket;nginx=network.target'

    response = client.post(
        '/api/automation/services/dependencies',
        headers=_headers(),
        json={'service_name': 'redis'},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['status'] == 'success'
    assert payload['service']['adapter'] == 'linux_test_double'
    assert payload['service']['dependency_count'] == 2
    assert payload['service']['dependencies'] == ['network.target', 'syslog.socket']


def test_get_service_dependencies_uses_windows_adapter_boundary(client, app_fixture):
    app_fixture.config['AUTOMATION_ALLOWED_SERVICES'] = 'Spooler'
    app_fixture.config['AUTOMATION_SERVICE_DEPENDENCY_ADAPTER'] = 'windows'

    class _WindowsDependencyProcessDouble:
        returncode = 0
        stdout = 'SERVICE_NAME: Spooler\n        DEPENDENCIES       : RPCSS EventLog'
        stderr = ''

    with patch(
        'server.services.automation_service.AutomationService._run_windows_service_dependencies_command',
        return_value=_WindowsDependencyProcessDouble(),
    ) as runner_double:
        response = client.post(
            '/api/automation/services/dependencies',
            headers=_headers(),
            json={'service_name': 'Spooler'},
        )

    assert runner_double.call_count == 1
    command_args, command_kwargs = runner_double.call_args
    assert command_args[0] == ['sc', 'qc', 'Spooler']
    assert command_args[1] == 8
    assert command_kwargs == {}

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['service']['adapter'] == 'windows'
    assert payload['service']['dependency_count'] == 2
    assert payload['service']['dependencies'] == ['EventLog', 'RPCSS']


def test_get_service_failures_uses_linux_test_double_path(client, app_fixture):
    app_fixture.config['AUTOMATION_ALLOWED_SERVICES'] = 'redis,nginx'
    app_fixture.config['AUTOMATION_SERVICE_FAILURE_ADAPTER'] = 'linux_test_double'
    app_fixture.config['AUTOMATION_LINUX_SERVICE_FAILURE_TEST_DOUBLE'] = 'redis=failed|crash_loop;nginx=healthy'

    response = client.post(
        '/api/automation/services/failures',
        headers=_headers(),
        json={'service_name': 'redis'},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['service']['adapter'] == 'linux_test_double'
    assert payload['service']['failure_detected'] is True
    assert payload['service']['service_state'] == 'stopped'
    assert payload['service']['failure_reasons'] == ['crash_loop']


def test_get_service_failures_uses_windows_adapter_boundary(client, app_fixture):
    app_fixture.config['AUTOMATION_ALLOWED_SERVICES'] = 'Spooler'
    app_fixture.config['AUTOMATION_SERVICE_FAILURE_ADAPTER'] = 'windows'

    class _WindowsFailureProcessDouble:
        returncode = 0
        stdout = (
            'SERVICE_NAME: Spooler\n'
            '        STATE              : 1  STOPPED\n'
            '        WIN32_EXIT_CODE    : 1067\n'
        )
        stderr = ''

    with patch(
        'server.services.automation_service.AutomationService._run_windows_service_failures_command',
        return_value=_WindowsFailureProcessDouble(),
    ) as runner_double:
        response = client.post(
            '/api/automation/services/failures',
            headers=_headers(),
            json={'service_name': 'Spooler'},
        )

    assert runner_double.call_count == 1
    command_args, command_kwargs = runner_double.call_args
    assert command_args[0] == ['sc', 'queryex', 'Spooler']
    assert command_args[1] == 8
    assert command_kwargs == {}

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['service']['adapter'] == 'windows'
    assert payload['service']['failure_detected'] is True
    assert payload['service']['service_state'] == 'stopped'
    assert 'service_stopped' in payload['service']['failure_reasons']


def test_execute_service_command_uses_linux_test_double_path(client, app_fixture):
    app_fixture.config['AUTOMATION_ALLOWED_SERVICES'] = 'redis,nginx'
    app_fixture.config['AUTOMATION_COMMAND_EXECUTOR_ADAPTER'] = 'linux_test_double'
    app_fixture.config['AUTOMATION_LINUX_COMMAND_EXECUTOR_TEST_DOUBLE'] = 'redis:ping=0|PONG;nginx:status=0|OK'

    response = client.post(
        '/api/automation/services/execute',
        headers=_headers(),
        json={'service_name': 'redis', 'command_text': 'ping'},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['status'] == 'success'
    assert payload['service']['adapter'] == 'linux_test_double'
    assert payload['service']['returncode'] == 0
    assert payload['service']['stdout'] == 'PONG'


def test_execute_service_command_uses_windows_adapter_boundary(client, app_fixture):
    app_fixture.config['AUTOMATION_ALLOWED_SERVICES'] = 'WinService'
    app_fixture.config['AUTOMATION_COMMAND_EXECUTOR_ADAPTER'] = 'windows'

    class _WindowsCommandProcessDouble:
        returncode = 0
        stdout = 'Service is running'
        stderr = ''

    with patch(
        'server.services.automation_service.AutomationService._run_windows_service_command_executor',
        return_value=_WindowsCommandProcessDouble(),
    ) as runner_double:
        response = client.post(
            '/api/automation/services/execute',
            headers=_headers(),
            json={'service_name': 'WinService', 'command_text': 'Get-Service WinService'},
        )

    assert runner_double.call_count == 1
    command_args, command_kwargs = runner_double.call_args
    assert command_args[0] == ['powershell.exe', '-Command', 'Get-Service WinService']
    assert command_args[1] == 8
    assert command_kwargs == {}

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['service']['adapter'] == 'windows'
    assert payload['service']['returncode'] == 0
    assert payload['service']['stdout'] == 'Service is running'
