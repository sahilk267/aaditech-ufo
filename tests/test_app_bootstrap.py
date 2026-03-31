"""Regression tests for app factory and bootstrap wiring."""

import redis
from unittest.mock import patch

from werkzeug.middleware.proxy_fix import ProxyFix

from server.app import apply_database_migrations, create_app
from server.config import TestingConfig


class ProxyEnabledTestConfig(TestingConfig):
    ENABLE_PROXY_FIX = True


class ProxyDisabledTestConfig(TestingConfig):
    ENABLE_PROXY_FIX = False


def test_create_app_enables_proxy_fix_when_configured():
    app = create_app(ProxyEnabledTestConfig)

    assert isinstance(app.wsgi_app, ProxyFix)


def test_create_app_skips_proxy_fix_when_disabled():
    app = create_app(ProxyDisabledTestConfig)

    assert not isinstance(app.wsgi_app, ProxyFix)


def test_create_app_initializes_inline_queue_mode_for_testing():
    app = create_app(TestingConfig)

    assert app.extensions['celery'] is None
    assert app.extensions['queue_tasks']['dispatch_alert_notifications'] == 'alerts.dispatch_notifications'
    assert 'dispatch_alert_notifications' in app.extensions['queue_handlers']


def test_healthcheck_response_includes_gateway_headers(app_fixture):
    client = app_fixture.test_client()

    response = client.get('/health')

    assert response.status_code == 200
    assert response.headers['X-API-Gateway-Ready'] == 'true'
    assert response.headers['X-Request-ID']
    assert response.headers['X-Response-Time-Ms'].isdigit()


def test_healthcheck_echoes_incoming_request_id(app_fixture):
    client = app_fixture.test_client()

    response = client.get('/health', headers={'X-Request-ID': 'bootstrap-test-id'})

    assert response.status_code == 200
    assert response.headers['X-Request-ID'] == 'bootstrap-test-id'


def test_healthcheck_reports_degraded_redis_when_ping_fails(app_fixture):
    client = app_fixture.test_client()

    class _RedisFailureDouble:
        def ping(self):
            raise redis.exceptions.ConnectionError('redis unavailable')

    app_fixture.config['REDIS_URL'] = 'redis://:secret@redis:6379/0'

    with patch('redis.Redis.from_url', return_value=_RedisFailureDouble()):
        response = client.get('/health')

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['status'] == 'degraded'
    assert payload['database'] == 'connected'
    assert payload['redis'] == 'disconnected'


def test_apply_database_migrations_invokes_alembic_upgrade(app_fixture):
    with patch('server.app.run_db_upgrade') as upgrade_mock:
        apply_database_migrations(app_fixture)

    upgrade_mock.assert_called_once_with()
