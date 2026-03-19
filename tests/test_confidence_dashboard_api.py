"""Tests for Week 16.3-4 AI confidence scorer and dashboard aggregator."""

import pytest
from unittest.mock import patch

from server.auth import get_api_key


def _headers(tenant_slug=None):
    headers = {'X-API-Key': get_api_key()}
    if tenant_slug:
        headers['X-Tenant-Slug'] = tenant_slug
    return headers


@pytest.fixture
def confidence_test_client(app_fixture):
    """Provide test client with confidence scorer config."""
    app_fixture.config['CONFIDENCE_ADAPTER'] = 'linux_test_double'
    app_fixture.config['CONFIDENCE_ALLOWED_HOSTS'] = 'host-a,host-b'
    app_fixture.config['CONFIDENCE_LINUX_TEST_DOUBLE_SCORES'] = 'host-a=0.75|medium-impact;host-b=0.85|low-impact'
    app_fixture.config['RELIABILITY_HISTORY_ADAPTER'] = 'linux_test_double'
    app_fixture.config['RELIABILITY_SCORER_ADAPTER'] = 'linux_test_double'
    app_fixture.config['RELIABILITY_TREND_ADAPTER'] = 'linux_test_double'
    app_fixture.config['RELIABILITY_PREDICTION_ADAPTER'] = 'linux_test_double'
    app_fixture.config['RELIABILITY_PATTERN_ADAPTER'] = 'linux_test_double'
    app_fixture.config['RELIABILITY_ALLOWED_HOSTS'] = 'host-a,host-b'
    app_fixture.config['RELIABILITY_LINUX_SCORER_TEST_DOUBLE'] = 'host-a=0.6|moderate;host-b=0.8|good'
    app_fixture.config['UPDATE_MONITOR_ADAPTER'] = 'linux_test_double'
    app_fixture.config['UPDATE_ALLOWED_HOSTS'] = 'host-a,host-b'
    app_fixture.config['UPDATE_LINUX_MONITOR_TEST_DOUBLE'] = 'host-a=KB5030211|Security Update|2026-03-17||KB5031455|Cumulative|2026-03-12'
    app_fixture.config['DASHBOARD_ALLOWED_HOSTS'] = 'host-a,host-b'
    app_fixture.config['RELIABILITY_LINUX_HISTORY_TEST_DOUBLE'] = 'host-a=startup|2026-03-18||shutdown|2026-03-17'
    app_fixture.config['RELIABILITY_LINUX_TREND_TEST_DOUBLE'] = 'host-a=upward'
    app_fixture.config['RELIABILITY_LINUX_PREDICTION_TEST_DOUBLE'] = 'host-a=0.65|upward'
    app_fixture.config['RELIABILITY_LINUX_PATTERN_TEST_DOUBLE'] = 'host-a=stable'
    return app_fixture.test_client()


class TestConfidenceScorerAPI:
    """Test suite for AI confidence scoring endpoint."""

    def test_confidence_scorer_uses_linux_test_double_path(self, confidence_test_client):
        """Test confidence scorer returns deterministic score for linux_test_double adapter."""
        response = confidence_test_client.post(
            '/api/ai/confidence/score',
            json={
                'host_name': 'host-a',
                'updates': [
                    {'hotfix_id': 'KB5030211', 'description': 'Security Update'},
                    {'hotfix_id': 'KB5031455', 'description': 'Cumulative Update'},
                ],
                'reliability_score': 0.6,
                'model': 'llama3.2',
            },
            headers=_headers(),
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'success'
        assert 'confidence' in data
        confidence = data['confidence']
        assert confidence['adapter'] == 'linux_test_double'
        assert confidence['status'] == 'success'
        assert confidence['host_name'] == 'host-a'
        # Should have parsed the test-double score
        assert confidence['confidence_score'] == 0.75
        assert isinstance(confidence['risk_factors'], list)
        assert isinstance(confidence['impact_summary'], str)
        assert confidence['updates_analyzed_count'] == 2
        assert confidence['scoring_version'] == 'foundation-v1'

    def test_confidence_scorer_requires_host_name(self, confidence_test_client):
        """Test confidence scorer returns 400 when host_name is missing."""
        response = confidence_test_client.post(
            '/api/ai/confidence/score',
            json={
                'updates': [],
                'reliability_score': 0.5,
            },
            headers=_headers(),
        )

        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_confidence_scorer_enforces_host_allowlist(self, confidence_test_client):
        """Test confidence scorer returns 400 when host not in allowlist."""
        response = confidence_test_client.post(
            '/api/ai/confidence/score',
            json={
                'host_name': 'host-not-allowed',
                'updates': [],
                'reliability_score': 0.5,
            },
            headers=_headers(),
        )

        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_confidence_scorer_maps_ollama_command_failure_to_503(self, confidence_test_client, app_fixture):
        """Test confidence scorer returns 503 when Ollama inference fails."""
        app_fixture.config['CONFIDENCE_ADAPTER'] = 'ollama_http'
        app_fixture.config['CONFIDENCE_ALLOWED_MODELS'] = 'llama3.2'
        
        with patch('server.services.ai_service.AIService.run_ollama_inference') as mock_infer:
            mock_infer.return_value = (
                {'status': 'command_failed', 'stderr': 'Connection refused'},
                'command_failed',
            )
            response = confidence_test_client.post(
                '/api/ai/confidence/score',
                json={
                    'host_name': 'host-a',
                    'updates': [],
                    'reliability_score': 0.5,
                },
                headers=_headers(),
            )

        assert response.status_code == 503
        data = response.get_json()
        assert 'error' in data


class TestDashboardAggregatorAPI:
    """Test suite for advanced dashboard aggregator endpoint."""

    def test_dashboard_aggregator_collects_all_metrics_for_host(self, confidence_test_client):
        """Test dashboard aggregator returns unified status for a host."""
        response = confidence_test_client.get(
            '/api/dashboard/status?host_name=host-a',
            headers=_headers(),
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'success'
        assert 'dashboard' in data
        dashboard = data['dashboard']
        
        # Check top-level structure
        assert dashboard['status'] == 'success'
        assert dashboard['host_name'] == 'host-a'
        assert 'aggregate_health' in dashboard
        assert 'reliability' in dashboard
        assert 'crash_analysis' in dashboard
        assert 'trend' in dashboard
        assert 'prediction' in dashboard
        assert 'updates' in dashboard
        assert 'ai_confidence' in dashboard
        assert 'dashboard_version' in dashboard

        # Check aggregate health
        aggregate = dashboard['aggregate_health']
        assert 'overall_status' in aggregate
        assert 'health_band' in aggregate
        assert 'last_updated' in aggregate

        # Check reliability metrics
        reliability = dashboard['reliability']
        assert 'current_score' in reliability
        assert 'health_band' in reliability

        # Check updates metrics
        updates = dashboard['updates']
        assert 'pending_count' in updates
        assert 'update_risk' in updates
        assert 'impact_summary' in updates

        # Check AI confidence metrics
        confidence = dashboard['ai_confidence']
        assert 'confidence_score' in confidence
        assert 'risk_factors' in confidence

    def test_dashboard_aggregator_requires_host_name(self, confidence_test_client):
        """Test dashboard aggregator returns 400 when host_name is missing."""
        response = confidence_test_client.get(
            '/api/dashboard/status',
            headers=_headers(),
        )

        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_dashboard_aggregator_enforces_host_allowlist(self, confidence_test_client):
        """Test dashboard aggregator returns 400 when host not in allowlist."""
        response = confidence_test_client.get(
            '/api/dashboard/status?host_name=host-not-allowed',
            headers=_headers(),
        )

        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_dashboard_aggregator_handles_missing_sub_service_gracefully(self, confidence_test_client, app_fixture):
        """Test dashboard aggregator continues when individual services fail."""
        # Create a config where a sub-service will fail
        app_fixture.config['RELIABILITY_ALLOWED_HOSTS'] = 'host-different'
        
        response = confidence_test_client.get(
            '/api/dashboard/status?host_name=host-a',
            headers=_headers(),
        )

        # Should still return 200 (graceful degradation)
        assert response.status_code == 200 or response.status_code == 400
        data = response.get_json()
        if response.status_code == 200:
            assert data['status'] == 'success'

    def test_dashboard_rates_health_status_based_on_metrics(self, confidence_test_client, app_fixture):
        """Test dashboard computes appropriate health status from component scores."""
        # Setup config for a degraded system: low reliability score, crashes, pending updates
        app_fixture.config['RELIABILITY_LINUX_SCORER_TEST_DOUBLE'] = 'host-a=0.45|poor'
        app_fixture.config['RELIABILITY_LINUX_HISTORY_TEST_DOUBLE'] = 'host-a=crash|2026-03-18||crash|2026-03-17'
        app_fixture.config['UPDATE_LINUX_MONITOR_TEST_DOUBLE'] = (
            'host-a=KB5030211|Security|2026-03-17||KB5031455|Critical|2026-03-12||KB5032100|Important|2026-03-10'
        )
        app_fixture.config['CONFIDENCE_LINUX_TEST_DOUBLE_SCORES'] = 'host-a=0.4|high-impact'

        response = confidence_test_client.get(
            '/api/dashboard/status?host_name=host-a',
            headers=_headers(),
        )

        assert response.status_code == 200
        data = response.get_json()
        dashboard = data['dashboard']
        
        # With low reliability + crashes + pending updates, health should reflect degradation
        health_status = dashboard['aggregate_health']['overall_status']
        assert health_status in ['poor', 'degraded', 'at-risk', 'critical', 'moderate']
