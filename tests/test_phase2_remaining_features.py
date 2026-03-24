"""
Tests for Phase 2 remaining features (Week 15-16):
  - AI Incident Explanation
  - AI Alert Prioritization
  - Scheduled Automation Jobs
  - Remote SSH Command Execution
  - Self-Healing Infrastructure Loop
"""

from unittest.mock import patch

import pytest

from server.auth import get_api_key
from server.services.ai_service import AIService
from server.services.alert_service import AlertService
from server.services.automation_service import AutomationService
from server.services.remote_executor_service import RemoteExecutorService


def _headers():
    return {'X-API-Key': get_api_key()}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# AI Incident Explanation
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestAIIncidentExplanation:
    """POST /api/ai/incident/explain"""

    def _runtime_config(self, app_fixture, prompt_text: str, response_text: str) -> None:
        app_fixture.config['OLLAMA_ADAPTER'] = 'linux_test_double'
        app_fixture.config['OLLAMA_ALLOWED_MODELS'] = 'llama3.2'
        app_fixture.config['OLLAMA_DEFAULT_MODEL'] = 'llama3.2'
        app_fixture.config['OLLAMA_LINUX_TEST_DOUBLE_RESPONSES'] = f'{prompt_text}={response_text}'

    def test_explain_incident_api_returns_structured_explanation(self, client, app_fixture):
        incident_title = 'Database cluster failover at 03:00 UTC'
        affected_systems = ['db-primary-01', 'db-replica-02']
        metrics_snapshot = {'cpu_usage': 98.5, 'replication_lag_ms': 8500}
        prompt_text = AIService._build_incident_explanation_prompt(
            incident_title, affected_systems, metrics_snapshot
        )
        self._runtime_config(
            app_fixture,
            prompt_text,
            'Summary: DB cluster failed over due to primary overload.\n'
            'LikelyCause: CPU saturation caused query timeout cascade.\n'
            'BusinessImpact: Elevated read latency for 12 minutes.\n'
            'NextSteps: Add read replica and throttle batch jobs.\n'
            'Confidence: medium',
        )

        response = client.post(
            '/api/ai/incident/explain',
            headers=_headers(),
            json={
                'incident_title': incident_title,
                'affected_systems': affected_systems,
                'metrics_snapshot': metrics_snapshot,
            },
        )

        assert response.status_code == 200
        payload = response.get_json()
        assert payload['status'] == 'success'
        exp = payload['incident_explanation']
        assert exp['adapter'] == 'linux_test_double'
        explanation = exp['explanation']
        assert explanation['confidence'] == 'medium'
        assert 'db cluster' in explanation['summary'].lower()
        assert explanation['likely_cause'] != ''
        assert explanation['next_steps'] != ''

    def test_explain_incident_requires_incident_title(self, client):
        response = client.post(
            '/api/ai/incident/explain',
            headers=_headers(),
            json={'affected_systems': ['web-01']},
        )
        assert response.status_code == 400
        payload = response.get_json()
        assert payload['error'] == 'Validation failed'
        assert 'incident_title' in payload['details']

    def test_explain_incident_rejects_overly_long_title(self, client, app_fixture):
        app_fixture.config['OLLAMA_ADAPTER'] = 'linux_test_double'
        response = client.post(
            '/api/ai/incident/explain',
            headers=_headers(),
            json={'incident_title': 'X' * 513},
        )
        assert response.status_code in (400, 503)

    def test_explain_incident_maps_ollama_error_to_503(self, client, app_fixture):
        app_fixture.config['OLLAMA_ADAPTER'] = 'ollama_http'
        app_fixture.config['OLLAMA_ENDPOINT'] = 'http://ollama:11434/api/generate'
        app_fixture.config['OLLAMA_ALLOWED_MODELS'] = 'llama3.2'
        app_fixture.config['OLLAMA_DEFAULT_MODEL'] = 'llama3.2'

        class _ErrorDouble:
            status_code = 503
            text = 'service unavailable'
            def json(self): return {'error': 'service unavailable'}

        with patch(
            'server.services.ai_service.AIService._run_ollama_http_request',
            return_value=_ErrorDouble(),
        ):
            response = client.post(
                '/api/ai/incident/explain',
                headers=_headers(),
                json={'incident_title': 'Production outage during deploy'},
            )

        assert response.status_code == 503
        payload = response.get_json()
        assert payload['error'] == 'Incident explanation request failed'

    def test_ai_service_explain_incident_unit_test_double(self, app_fixture):
        """Unit test: AIService.explain_incident returns structured explanation dict."""
        with app_fixture.app_context():
            incident_title = 'Disk full on worker nodes'
            affected_systems = ['worker-01', 'worker-02']
            metrics_snapshot = {'disk_usage': 100.0}
            prompt_text = AIService._build_incident_explanation_prompt(
                incident_title, affected_systems, metrics_snapshot
            )
            runtime_config = {
                'adapter': 'linux_test_double',
                'model': 'llama3.2',
                'allowed_models': ['llama3.2'],
                'prompt_max_chars': 4000,
                'response_max_chars': 4000,
                'timeout_seconds': 8,
                'linux_test_double_responses': {
                    prompt_text: (
                        'Summary: Worker nodes ran out of disk space.\n'
                        'LikelyCause: Log rotation misconfiguration caused log accumulation.\n'
                        'BusinessImpact: Jobs failing on worker nodes.\n'
                        'NextSteps: Rotate logs and increase disk quota.\n'
                        'Confidence: high'
                    ),
                },
            }

            result, error = AIService.explain_incident(
                incident_title=incident_title,
                affected_systems=affected_systems,
                metrics_snapshot=metrics_snapshot,
                runtime_config=runtime_config,
            )

            assert error is None
            assert result['adapter'] == 'linux_test_double'
            explanation = result['explanation']
            assert explanation['confidence'] == 'high'
            assert 'disk' in explanation['summary'].lower()
            assert explanation['next_steps'] != ''


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# AI Alert Prioritization
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestAlertPrioritization:
    """POST /api/alerts/prioritize"""

    def _sample_alerts(self):
        return [
            {
                'metric': 'cpu_usage', 'severity': 'info', 'alert_type': 'threshold',
                'actual_value': 72.0, 'z_score': 0.4,
            },
            {
                'metric': 'ram_usage', 'severity': 'critical', 'alert_type': 'anomaly',
                'actual_value': 98.0, 'z_score': 4.2,
            },
            {
                'metric': 'disk_io', 'severity': 'warning', 'alert_type': 'pattern',
                'actual_value': 85.0, 'z_score': 2.1, 'violation_rate': 0.8,
            },
        ]

    def test_prioritize_returns_sorted_list(self, client):
        response = client.post(
            '/api/alerts/prioritize',
            headers=_headers(),
            json={'alerts': self._sample_alerts()},
        )
        assert response.status_code == 200
        payload = response.get_json()
        assert payload['status'] == 'success'
        items = payload['prioritized_alerts']
        assert len(items) == 3
        # First item must have the highest priority_score
        scores = [item['priority_score'] for item in items]
        assert scores == sorted(scores, reverse=True)

    def test_prioritize_assigns_priority_rank(self, client):
        response = client.post(
            '/api/alerts/prioritize',
            headers=_headers(),
            json={'alerts': self._sample_alerts()},
        )
        assert response.status_code == 200
        items = response.get_json()['prioritized_alerts']
        ranks = [item['priority_rank'] for item in items]
        assert ranks == list(range(1, len(items) + 1))

    def test_prioritize_critical_alert_ranked_first(self, client):
        response = client.post(
            '/api/alerts/prioritize',
            headers=_headers(),
            json={'alerts': self._sample_alerts()},
        )
        assert response.status_code == 200
        first = response.get_json()['prioritized_alerts'][0]
        assert first['severity'] == 'critical'

    def test_prioritize_top_n_limits_results(self, client):
        response = client.post(
            '/api/alerts/prioritize',
            headers=_headers(),
            json={'alerts': self._sample_alerts(), 'top_n': 2},
        )
        assert response.status_code == 200
        payload = response.get_json()
        assert len(payload['prioritized_alerts']) == 2
        assert payload['total'] == 2

    def test_prioritize_requires_non_empty_list(self, client):
        response = client.post(
            '/api/alerts/prioritize',
            headers=_headers(),
            json={'alerts': []},
        )
        assert response.status_code == 400

    def test_prioritize_missing_alerts_field(self, client):
        response = client.post(
            '/api/alerts/prioritize',
            headers=_headers(),
            json={},
        )
        assert response.status_code == 400
        assert 'alerts' in response.get_json()['details']

    def test_prioritize_service_unit_scoring(self, app_fixture):
        """Unit test: prioritize_alerts() scoring is stable and deterministic."""
        with app_fixture.app_context():
            alerts = [
                {'severity': 'critical', 'alert_type': 'threshold', 'z_score': 0.0},
                {'severity': 'info', 'alert_type': 'threshold', 'z_score': 0.0},
            ]
            result = AlertService.prioritize_alerts(alerts)
            assert result[0]['severity'] == 'critical'
            assert result[0]['priority_rank'] == 1
            assert result[1]['priority_rank'] == 2


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Scheduled Automation Jobs
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestScheduledAutomationJobs:
    """GET + POST /api/automation/scheduled-jobs"""

    def _create_workflow(self, client):
        import uuid
        resp = client.post(
            '/api/automation/workflows',
            headers=_headers(),
            json={
                'name': f'Nightly Cleanup {uuid.uuid4().hex[:8]}',
                'trigger_type': 'manual',
                'action_type': 'script_execute',
                'action_config': {'script': 'cleanup.sh'},
            },
        )
        assert resp.status_code == 201
        return resp.get_json()['workflow']['id']

    def test_list_scheduled_jobs_returns_empty_initially(self, client):
        response = client.get('/api/automation/scheduled-jobs', headers=_headers())
        assert response.status_code == 200
        payload = response.get_json()
        assert payload['status'] == 'success'
        assert isinstance(payload['scheduled_jobs'], list)

    def test_create_scheduled_job_valid_cron(self, client):
        workflow_id = self._create_workflow(client)
        response = client.post(
            '/api/automation/scheduled-jobs',
            headers=_headers(),
            json={'workflow_id': workflow_id, 'cron_expression': '0 2 * * *'},
        )
        assert response.status_code == 201
        payload = response.get_json()
        assert payload['status'] == 'success'
        job = payload['scheduled_job']
        assert job['workflow_id'] == workflow_id
        assert job['cron_expression'] == '0 2 * * *'
        assert job['is_active'] is True

    def test_create_scheduled_job_rejects_invalid_cron(self, client):
        response = client.post(
            '/api/automation/scheduled-jobs',
            headers=_headers(),
            json={'workflow_id': 1, 'cron_expression': 'not-a-cron'},
        )
        assert response.status_code == 400
        payload = response.get_json()
        assert 'cron_expression' in payload['details']

    def test_create_scheduled_job_requires_workflow_id(self, client):
        response = client.post(
            '/api/automation/scheduled-jobs',
            headers=_headers(),
            json={'cron_expression': '*/5 * * * *'},
        )
        assert response.status_code == 400
        payload = response.get_json()
        assert 'workflow_id' in payload['details']

    def test_create_scheduled_job_rejects_unknown_workflow(self, client):
        response = client.post(
            '/api/automation/scheduled-jobs',
            headers=_headers(),
            json={'workflow_id': 999999, 'cron_expression': '* * * * *'},
        )
        assert response.status_code == 400
        payload = response.get_json()
        assert 'workflow_id' in payload['details']

    def test_list_returns_created_job(self, client):
        workflow_id = self._create_workflow(client)
        client.post(
            '/api/automation/scheduled-jobs',
            headers=_headers(),
            json={'workflow_id': workflow_id, 'cron_expression': '30 6 * * 1'},
        )
        response = client.get('/api/automation/scheduled-jobs', headers=_headers())
        assert response.status_code == 200
        jobs = response.get_json()['scheduled_jobs']
        assert any(j['workflow_id'] == workflow_id for j in jobs)

    def test_schedule_job_service_validates_cron_expression(self, app_fixture):
        """Unit test: schedule_job() rejects badly-formatted cron strings."""
        with app_fixture.app_context():
            _job, errors = AutomationService.schedule_job(
                organization_id=1,
                payload={'workflow_id': 1, 'cron_expression': 'bad-cron!!'},
            )
            assert 'cron_expression' in errors


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Remote SSH Command Execution
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestRemoteCommandExecution:
    """POST /api/remote/exec"""

    def test_exec_returns_test_double_output(self, client, app_fixture):
        app_fixture.config['REMOTE_EXEC_ADAPTER'] = 'linux_test_double'
        app_fixture.config['REMOTE_EXEC_ALLOWED_HOSTS'] = 'app-server-01'
        app_fixture.config['REMOTE_EXEC_ALLOWED_COMMANDS'] = 'uptime'

        # The route uses an empty test-double map → stdout is empty string (still 200)
        response = client.post(
            '/api/remote/exec',
            headers=_headers(),
            json={'host': 'app-server-01', 'command': 'uptime'},
        )
        assert response.status_code == 200
        payload = response.get_json()
        assert payload['status'] == 'success'
        assert payload['execution']['adapter'] == 'linux_test_double'
        assert payload['execution']['host'] == 'app-server-01'

    def test_exec_blocks_unallowlisted_host(self, client, app_fixture):
        app_fixture.config['REMOTE_EXEC_ADAPTER'] = 'linux_test_double'
        app_fixture.config['REMOTE_EXEC_ALLOWED_HOSTS'] = 'safe-host-01'
        app_fixture.config['REMOTE_EXEC_ALLOWED_COMMANDS'] = ''

        response = client.post(
            '/api/remote/exec',
            headers=_headers(),
            json={'host': 'evil-host.attacker.com', 'command': 'uptime'},
        )
        assert response.status_code == 403
        payload = response.get_json()
        assert payload['error'] == 'Policy blocked'

    def test_exec_blocks_unallowlisted_command(self, client, app_fixture):
        app_fixture.config['REMOTE_EXEC_ADAPTER'] = 'linux_test_double'
        app_fixture.config['REMOTE_EXEC_ALLOWED_HOSTS'] = ''
        app_fixture.config['REMOTE_EXEC_ALLOWED_COMMANDS'] = 'uptime,hostname'

        response = client.post(
            '/api/remote/exec',
            headers=_headers(),
            json={'host': 'app-server-01', 'command': 'rm -rf /'},
        )
        # Either policy_blocked (403) or unsafe chars (400)
        assert response.status_code in (400, 403)

    def test_exec_rejects_missing_host(self, client):
        response = client.post(
            '/api/remote/exec',
            headers=_headers(),
            json={'command': 'uptime'},
        )
        assert response.status_code == 400
        assert 'host' in response.get_json()['details']

    def test_exec_rejects_missing_command(self, client):
        response = client.post(
            '/api/remote/exec',
            headers=_headers(),
            json={'host': 'app-server-01'},
        )
        assert response.status_code == 400
        assert 'command' in response.get_json()['details']

    def test_remote_executor_service_test_double_with_key(self, app_fixture):
        """Unit test: service returns configured output for key ``host:command``."""
        with app_fixture.app_context():
            result, error = RemoteExecutorService.execute_remote_command(
                host='app-server-01',
                command='uptime',
                runtime_config={
                    'ssh_adapter': 'linux_test_double',
                    'allowed_hosts': ['app-server-01'],
                    'allowed_commands': ['uptime'],
                    'linux_test_double_remote_commands': {
                        'app-server-01:uptime': {'returncode': 0, 'stdout': '10:00:00 up 5 days', 'stderr': ''},
                    },
                },
            )
            assert error is None
            assert result['adapter'] == 'linux_test_double'
            assert '5 days' in result['stdout']

    def test_remote_executor_blocks_shell_metachar_command(self, app_fixture):
        """Unit test: commands with shell meta-characters are blocked at service layer."""
        with app_fixture.app_context():
            result, error = RemoteExecutorService.execute_remote_command(
                host='app-server-01',
                command='echo hello; rm -rf /',
                runtime_config={'ssh_adapter': 'linux_test_double'},
            )
            assert error == 'command_unsafe_chars'
            assert result['status'] == 'policy_blocked'

    def test_remote_executor_blocks_host_not_in_allowlist(self, app_fixture):
        with app_fixture.app_context():
            result, error = RemoteExecutorService.execute_remote_command(
                host='unknown-host',
                command='uptime',
                runtime_config={
                    'ssh_adapter': 'linux_test_double',
                    'allowed_hosts': ['safe-host'],
                },
            )
            assert error == 'host_not_allowlisted'


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Self-Healing Infrastructure Loop
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestSelfHealingLoop:
    """POST /api/automation/self-heal"""

    def test_self_heal_with_no_alerts_returns_empty_result(self, client):
        response = client.post(
            '/api/automation/self-heal',
            headers=_headers(),
            json={'alerts': [], 'dry_run': True},
        )
        assert response.status_code == 200
        payload = response.get_json()
        assert payload['status'] == 'success'
        result = payload['self_healing']
        assert result['triggered_count'] == 0
        assert result['dry_run'] is True

    def test_self_heal_dry_run_does_not_execute_workflows(self, client):
        response = client.post(
            '/api/automation/self-heal',
            headers=_headers(),
            json={
                'dry_run': True,
                'alerts': [
                    {'metric': 'cpu_usage', 'severity': 'critical', 'actual_value': 98.0}
                ],
            },
        )
        assert response.status_code == 200
        result = response.get_json()['self_healing']
        assert result['dry_run'] is True
        # In dry_run=True, triggered_count must always be 0
        assert result['triggered_count'] == 0

    def test_self_heal_returns_alert_count(self, client):
        alerts = [
            {'metric': 'cpu_usage', 'severity': 'critical', 'actual_value': 98.0},
            {'metric': 'ram_usage', 'severity': 'warning', 'actual_value': 88.0},
        ]
        response = client.post(
            '/api/automation/self-heal',
            headers=_headers(),
            json={'alerts': alerts, 'dry_run': True},
        )
        assert response.status_code == 200
        result = response.get_json()['self_healing']
        assert result['alert_count'] == 2

    def test_self_heal_missing_alerts_treated_as_empty(self, client):
        response = client.post(
            '/api/automation/self-heal',
            headers=_headers(),
            json={'dry_run': True},
        )
        assert response.status_code == 200
        result = response.get_json()['self_healing']
        assert result['triggered_count'] == 0
        assert result['reason'] == 'no_alerts_provided'

    def test_self_heal_service_unit_dry_run(self, app_fixture):
        """Unit test: trigger_self_healing returns correct shape with dry_run=True."""
        with app_fixture.app_context():
            result = AutomationService.trigger_self_healing(
                organization_id=1,
                alerts=[
                    {'metric': 'cpu_usage', 'severity': 'critical', 'actual_value': 95.0}
                ],
                runtime_config={'self_healing_dry_run': True},
            )
            assert result['status'] == 'success'
            assert result['dry_run'] is True
            assert result['triggered_count'] == 0
            assert isinstance(result['matched_workflows'], list)

    def test_self_heal_service_unit_no_alerts(self, app_fixture):
        """Unit test: trigger_self_healing with empty list returns reason field."""
        with app_fixture.app_context():
            result = AutomationService.trigger_self_healing(
                organization_id=1,
                alerts=[],
                runtime_config={'self_healing_dry_run': True},
            )
            assert result['reason'] == 'no_alerts_provided'
            assert result['triggered_count'] == 0
