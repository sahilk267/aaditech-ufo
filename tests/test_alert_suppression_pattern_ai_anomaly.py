"""
Tests for Phase 2 remaining items:
  - Alert Suppression (silence windows)
  - Pattern-Based Alerts
  - AI Anomaly Detection (Ollama-backed analysis)
"""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from server.auth import get_api_key
from server.extensions import db
from server.models import Organization
from server.services.ai_service import AIService
from server.services.alert_service import AlertService


def _headers(tenant_slug=None):
    headers = {'X-API-Key': get_api_key()}
    if tenant_slug:
        headers['X-Tenant-Slug'] = tenant_slug
    return headers


def _future_iso(hours=2):
    """Return an ISO datetime string N hours in the future."""
    return (datetime.utcnow() + timedelta(hours=hours)).isoformat()


# ─────────────────────────────────────────────
# Alert Silence API tests
# ─────────────────────────────────────────────

class TestAlertSilenceAPI:
    def test_list_silences_returns_empty_for_new_tenant(self, client):
        response = client.get('/api/alerts/silences', headers=_headers())
        assert response.status_code == 200
        payload = response.get_json()
        assert payload['status'] == 'success'
        assert isinstance(payload['silences'], list)

    def test_create_silence_by_metric(self, client):
        response = client.post(
            '/api/alerts/silences',
            headers=_headers(),
            json={
                'metric': 'cpu_usage',
                'reason': 'Planned OS patching window',
                'ends_at': _future_iso(hours=4),
            },
        )
        assert response.status_code == 201
        payload = response.get_json()
        assert payload['status'] == 'success'
        assert payload['silence']['metric'] == 'cpu_usage'
        assert payload['silence']['reason'] == 'Planned OS patching window'

    def test_create_silence_requires_ends_at(self, client):
        response = client.post(
            '/api/alerts/silences',
            headers=_headers(),
            json={'metric': 'ram_usage'},
        )
        assert response.status_code == 400
        payload = response.get_json()
        assert payload['error'] == 'Validation failed'
        assert 'ends_at' in payload['details']

    def test_create_silence_requires_rule_id_or_metric(self, client):
        response = client.post(
            '/api/alerts/silences',
            headers=_headers(),
            json={'reason': 'No rule or metric', 'ends_at': _future_iso()},
        )
        assert response.status_code == 400
        payload = response.get_json()
        assert payload['error'] == 'Validation failed'

    def test_create_silence_rejects_past_ends_at(self, client):
        past_dt = (datetime.utcnow() - timedelta(hours=1)).isoformat()
        response = client.post(
            '/api/alerts/silences',
            headers=_headers(),
            json={'metric': 'cpu_usage', 'ends_at': past_dt},
        )
        assert response.status_code == 400
        payload = response.get_json()
        assert 'ends_at' in payload['details']

    def test_create_silence_rejects_invalid_metric(self, client):
        response = client.post(
            '/api/alerts/silences',
            headers=_headers(),
            json={'metric': 'invalid_metric_xyz', 'ends_at': _future_iso()},
        )
        assert response.status_code == 400
        payload = response.get_json()
        assert 'metric' in payload['details']

    def test_delete_silence_not_found(self, client):
        response = client.delete('/api/alerts/silences/99999', headers=_headers())
        assert response.status_code == 404

    def test_create_and_delete_silence_lifecycle(self, client):
        # Create
        create_resp = client.post(
            '/api/alerts/silences',
            headers=_headers(),
            json={'metric': 'storage_usage', 'ends_at': _future_iso(hours=1)},
        )
        assert create_resp.status_code == 201
        silence_id = create_resp.get_json()['silence']['id']

        # List → should contain the new silence
        list_resp = client.get('/api/alerts/silences', headers=_headers())
        assert list_resp.status_code == 200
        ids = [s['id'] for s in list_resp.get_json()['silences']]
        assert silence_id in ids

        # Delete
        del_resp = client.delete(f'/api/alerts/silences/{silence_id}', headers=_headers())
        assert del_resp.status_code == 200
        assert del_resp.get_json()['deleted_id'] == silence_id


# ─────────────────────────────────────────────
# Pattern-Based Alert evaluate tests
# ─────────────────────────────────────────────

class TestPatternAlerts:
    def test_evaluate_with_pattern_alerts_included_returns_pattern_count(self, client):
        """Evaluate endpoint includes pattern_count in response regardless of data volume."""
        response = client.post(
            '/api/alerts/evaluate',
            headers=_headers(),
            json={
                'include_threshold_alerts': False,
                'include_anomaly_alerts': False,
                'include_pattern_alerts': True,
                'apply_silences': False,
            },
        )
        assert response.status_code == 200
        payload = response.get_json()
        assert payload['status'] == 'success'
        assert 'pattern_count' in payload
        assert isinstance(payload['pattern_count'], int)

    def test_evaluate_with_pattern_alerts_disabled_returns_zero_pattern_count(self, client):
        response = client.post(
            '/api/alerts/evaluate',
            headers=_headers(),
            json={
                'include_threshold_alerts': False,
                'include_anomaly_alerts': False,
                'include_pattern_alerts': False,
                'apply_silences': False,
            },
        )
        assert response.status_code == 200
        payload = response.get_json()
        assert payload['pattern_count'] == 0

    def test_evaluate_includes_silence_suppression_fields(self, client):
        response = client.post(
            '/api/alerts/evaluate',
            headers=_headers(),
            json={'apply_silences': True},
        )
        assert response.status_code == 200
        payload = response.get_json()
        assert 'silenced_count' in payload
        assert 'silenced_alerts' in payload

    def test_evaluate_pattern_alerts_result_has_expected_structure(self, app_fixture):
        """Unit-test evaluate_patterns_for_tenant returns correct shape on empty DB."""
        with app_fixture.app_context():
            from server.models import Organization
            from server.extensions import db
            org = Organization.query.filter_by(slug='default').first()
            if org:
                results = AlertService.evaluate_patterns_for_tenant(org.id)
                # Empty DB → no patterns, correct return type
                assert isinstance(results, list)
    def test_create_rule_duplicate_rolls_back_and_allows_followup_write(self, app_fixture):
        with app_fixture.app_context():
            org = Organization(name='Alert Tenant', slug='alert-tenant', is_active=True)
            db.session.add(org)
            db.session.commit()

            rule, errors = AlertService.create_rule(
                org.id,
                {
                    'name': 'CPU High',
                    'metric': 'cpu_usage',
                    'operator': '>',
                    'threshold': 80,
                    'severity': 'warning',
                },
            )
            assert rule is not None
            assert errors == {}

            duplicate_rule, duplicate_errors = AlertService.create_rule(
                org.id,
                {
                    'name': 'CPU High',
                    'metric': 'cpu_usage',
                    'operator': '>',
                    'threshold': 90,
                    'severity': 'critical',
                },
            )
            assert duplicate_rule is None
            assert 'name' in duplicate_errors

            followup_rule, followup_errors = AlertService.create_rule(
                org.id,
                {
                    'name': 'RAM High',
                    'metric': 'ram_usage',
                    'operator': '>',
                    'threshold': 85,
                    'severity': 'warning',
                },
            )
            assert followup_rule is not None
            assert followup_errors == {}


# ─────────────────────────────────────────────
# AI Anomaly Detection API tests
# ─────────────────────────────────────────────

class TestAIAnomalyAnalysis:
    def _minimal_anomalies(self):
        return [
            {
                'metric': 'cpu_usage',
                'actual_value': 98.5,
                'baseline_mean': 45.0,
                'z_score': 3.8,
                'severity': 'critical',
                'hostname': 'web-prod-01',
            },
            {
                'metric': 'ram_usage',
                'actual_value': 95.0,
                'baseline_mean': 62.0,
                'z_score': 2.9,
                'severity': 'warning',
                'hostname': 'web-prod-01',
            },
        ]

    def test_ai_anomaly_analyze_uses_linux_test_double_path(self, client, app_fixture):
        anomalies = self._minimal_anomalies()
        prompt_text = AIService._build_anomaly_analysis_prompt([
            {
                'metric': a['metric'],
                'actual_value': a['actual_value'],
                'baseline_mean': a['baseline_mean'],
                'z_score': a['z_score'],
                'severity': a['severity'],
                'hostname': a['hostname'],
            }
            for a in anomalies
        ])

        app_fixture.config['OLLAMA_ADAPTER'] = 'linux_test_double'
        app_fixture.config['OLLAMA_ALLOWED_MODELS'] = 'llama3.2,phi3'
        app_fixture.config['OLLAMA_DEFAULT_MODEL'] = 'llama3.2'
        app_fixture.config['OLLAMA_LINUX_TEST_DOUBLE_RESPONSES'] = (
            f'{prompt_text}=InterpretedCause: Resource exhaustion from runaway process batch.\n'
            'SeverityRationale: Both CPU and RAM critically elevated on same host.\n'
            'RecommendedAction: Terminate the runaway process and investigate cron jobs.\n'
            'Confidence: high'
        )

        response = client.post(
            '/api/ai/anomaly/analyze',
            headers=_headers(),
            json={'anomalies': anomalies},
        )

        assert response.status_code == 200
        payload = response.get_json()
        assert payload['status'] == 'success'
        assert payload['anomaly_analysis']['adapter'] == 'linux_test_double'
        assert payload['anomaly_analysis']['anomaly_count'] == 2
        analysis = payload['anomaly_analysis']['analysis']
        assert analysis['confidence'] == 'high'
        assert 'runaway process' in analysis['interpreted_cause'].lower()
        assert analysis['recommended_action'] != ''

    def test_ai_anomaly_analyze_requires_anomalies_field(self, client):
        response = client.post(
            '/api/ai/anomaly/analyze',
            headers=_headers(),
            json={},
        )
        assert response.status_code == 400
        payload = response.get_json()
        assert payload['error'] == 'Validation failed'
        assert 'anomalies' in payload['details']

    def test_ai_anomaly_analyze_requires_non_empty_anomalies_list(self, client):
        response = client.post(
            '/api/ai/anomaly/analyze',
            headers=_headers(),
            json={'anomalies': []},
        )
        assert response.status_code == 400
        payload = response.get_json()
        assert payload['error'] == 'Validation failed'

    def test_ai_anomaly_analyze_maps_http_error_to_503(self, client, app_fixture):
        app_fixture.config['OLLAMA_ADAPTER'] = 'ollama_http'
        app_fixture.config['OLLAMA_ENDPOINT'] = 'http://ollama:11434/api/generate'
        app_fixture.config['OLLAMA_ALLOWED_MODELS'] = 'llama3.2'
        app_fixture.config['OLLAMA_DEFAULT_MODEL'] = 'llama3.2'

        class _HttpErrorDouble:
            status_code = 502
            text = 'bad gateway'

            @staticmethod
            def json():
                return {'error': 'bad gateway'}

        with patch(
            'server.services.ai_service.AIService._run_ollama_http_request',
            return_value=_HttpErrorDouble(),
        ):
            response = client.post(
                '/api/ai/anomaly/analyze',
                headers=_headers(),
                json={'anomalies': self._minimal_anomalies()},
            )

        assert response.status_code == 503
        payload = response.get_json()
        assert payload['error'] == 'Anomaly analysis request failed'

    def test_analyze_anomalies_service_unit_test_double_path(self, app_fixture):
        """Unit test: AIService.analyze_anomalies returns structured dict via test-double."""
        with app_fixture.app_context():
            anomalies = self._minimal_anomalies()
            prompt_text = AIService._build_anomaly_analysis_prompt([
                {
                    'metric': a['metric'],
                    'actual_value': a['actual_value'],
                    'baseline_mean': a['baseline_mean'],
                    'z_score': a['z_score'],
                    'severity': a['severity'],
                    'hostname': a['hostname'],
                }
                for a in anomalies
            ])
            runtime_config = {
                'adapter': 'linux_test_double',
                'model': 'llama3.2',
                'allowed_models': ['llama3.2'],
                'prompt_max_chars': 4000,
                'response_max_chars': 4000,
                'timeout_seconds': 8,
                'linux_test_double_responses': {
                    prompt_text: (
                        'InterpretedCause: CPU and RAM both critically high.\n'
                        'SeverityRationale: Multi-metric anomaly on same host.\n'
                        'RecommendedAction: Check for fork-bomb or batch job.\n'
                        'Confidence: medium'
                    ),
                },
                'ai_anomaly_max_items': 10,
            }
            result, error = AIService.analyze_anomalies(anomalies, runtime_config=runtime_config)
            assert error is None
            assert result['status'] == 'success'
            assert result['analysis']['confidence'] == 'medium'
            assert result['analysis']['interpreted_cause'] != ''

    def test_analyze_anomalies_service_returns_error_when_empty(self, app_fixture):
        with app_fixture.app_context():
            result, error = AIService.analyze_anomalies([], runtime_config={})
            assert error == 'anomalies_missing_or_invalid'

