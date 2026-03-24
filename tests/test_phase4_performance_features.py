"""Tests for Phase 4 optimization features.

Covers:
- Cache layer status and dashboard cache-hit behavior
- Database optimizer endpoint
- CDN static asset URL builder
"""

from server.auth import get_api_key
from server.services.performance_service import PerformanceService


def _headers():
    return {'X-API-Key': get_api_key()}


def test_cache_status_endpoint_returns_backend(client):
    response = client.get('/api/performance/cache/status', headers=_headers())
    assert response.status_code == 200
    payload = response.get_json()
    assert payload['status'] == 'success'
    assert payload['cache']['backend'] in ('memory', 'redis', 'disabled')


def test_database_optimize_endpoint_executes(client):
    response = client.post('/api/database/optimize', headers=_headers(), json={})
    assert response.status_code in (200, 202)
    payload = response.get_json()
    assert payload['status'] == 'success'
    assert 'optimization' in payload


def test_dashboard_status_uses_cache(client, app_fixture):
    app_fixture.config['CACHE_ENABLED'] = True
    app_fixture.config['CACHE_BACKEND'] = 'memory'
    app_fixture.config['CACHE_DASHBOARD_TTL_SECONDS'] = 120
    app_fixture.config['DASHBOARD_ALLOWED_HOSTS'] = 'host-01'

    # Ensure deterministic adapters for dashboard aggregate endpoint
    app_fixture.config['RELIABILITY_HISTORY_ADAPTER'] = 'linux_test_double'
    app_fixture.config['RELIABILITY_SCORER_ADAPTER'] = 'linux_test_double'
    app_fixture.config['RELIABILITY_TREND_ADAPTER'] = 'linux_test_double'
    app_fixture.config['RELIABILITY_PREDICTION_ADAPTER'] = 'linux_test_double'
    app_fixture.config['RELIABILITY_PATTERN_ADAPTER'] = 'linux_test_double'
    app_fixture.config['UPDATE_MONITOR_ADAPTER'] = 'linux_test_double'
    app_fixture.config['CONFIDENCE_ADAPTER'] = 'linux_test_double'

    app_fixture.config['RELIABILITY_ALLOWED_HOSTS'] = 'host-01'
    app_fixture.config['UPDATE_ALLOWED_HOSTS'] = 'host-01'
    app_fixture.config['CONFIDENCE_ALLOWED_HOSTS'] = 'host-01'

    app_fixture.config['RELIABILITY_LINUX_HISTORY_TEST_DOUBLE'] = (
        'host-01=2026-03-01T00:00:00Z|critical|service crash'
    )
    app_fixture.config['RELIABILITY_LINUX_SCORER_TEST_DOUBLE'] = 'host-01=0.72|good'
    app_fixture.config['RELIABILITY_LINUX_TREND_TEST_DOUBLE'] = 'host-01=stable|6'
    app_fixture.config['RELIABILITY_LINUX_PREDICTION_TEST_DOUBLE'] = 'host-01=improving|0.78'
    app_fixture.config['RELIABILITY_LINUX_PATTERN_TEST_DOUBLE'] = 'host-01=intermittent-crash|1'
    app_fixture.config['UPDATE_LINUX_MONITOR_TEST_DOUBLE'] = 'host-01=KB5030219|2026-03-01|Security'
    app_fixture.config['CONFIDENCE_LINUX_TEST_DOUBLE_SCORES'] = 'host-01=0.81|patching window stable|low reboot risk'

    PerformanceService.init_cache(app_fixture)

    first = client.get('/api/dashboard/status?host_name=host-01', headers=_headers())
    assert first.status_code == 200
    first_payload = first.get_json()
    assert first_payload['status'] == 'success'
    assert first_payload['cache_hit'] is False

    second = client.get('/api/dashboard/status?host_name=host-01', headers=_headers())
    assert second.status_code == 200
    second_payload = second.get_json()
    assert second_payload['status'] == 'success'
    assert second_payload['cache_hit'] is True


def test_asset_url_builder_supports_cdn():
    url = PerformanceService.build_static_asset_url(
        'app.css',
        {
            'CDN_ENABLED': True,
            'CDN_STATIC_BASE_URL': 'https://cdn.example.com/ufo-assets',
            'CDN_STATIC_VERSION': '20260324',
        },
    )
    assert url.startswith('https://cdn.example.com/ufo-assets/app.css')
    assert 'v=20260324' in url


def test_asset_url_builder_falls_back_to_local_static():
    url = PerformanceService.build_static_asset_url(
        'app.js',
        {
            'CDN_ENABLED': False,
            'CDN_STATIC_BASE_URL': '',
            'CDN_STATIC_VERSION': '',
        },
    )
    assert url == '/static/app.js'
