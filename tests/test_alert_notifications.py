"""Tests for alert notification queue dispatch with retry and audit coverage."""

from datetime import datetime
from unittest.mock import patch

from server.auth import get_api_key
from server.models import AuditEvent, Organization, SystemData
from server.extensions import db


def _headers(tenant_slug=None):
    headers = {'X-API-Key': get_api_key()}
    if tenant_slug:
        headers['X-Tenant-Slug'] = tenant_slug
    return headers


def _seed_triggered_alert(client, app_fixture):
    unique_suffix = datetime.utcnow().strftime('%H%M%S%f')
    created = client.post(
        '/api/alerts/rules',
        headers=_headers(),
        json={
            'name': f'Dispatch CPU High {unique_suffix}',
            'metric': 'cpu_usage',
            'operator': '>',
            'threshold': 80,
            'severity': 'critical',
        },
    )
    assert created.status_code == 201

    with app_fixture.app_context():
        tenant = Organization.query.filter_by(slug='default').first()
        row = SystemData(
            organization_id=tenant.id,
            serial_number='DISPATCH-SN-1',
            hostname='dispatch-host',
            cpu_usage=96.7,
            last_update=datetime.utcnow(),
            status='active',
            deleted=False,
        )
        db.session.add(row)
        db.session.commit()


def test_dispatch_notifications_retries_email_then_succeeds(client, app_fixture):
    _seed_triggered_alert(client, app_fixture)

    app_fixture.config['ALERT_EMAIL_ENABLED'] = True
    app_fixture.config['ALERT_EMAIL_TO'] = 'ops@example.com'

    with patch('server.services.notification_service.NotificationService.send_email_notification') as email_mock:
        email_mock.side_effect = [RuntimeError('smtp temporary failure'), None]

        response = client.post(
            '/api/alerts/dispatch',
            headers=_headers(),
            json={'channels': ['email'], 'email_retries': 2},
        )

    assert response.status_code == 202
    payload = response.get_json()
    assert payload['status'] == 'accepted'
    assert payload['job']['inline'] is True

    result = payload['job']['result']
    assert result['failure_count'] == 0
    assert 'email' in result['delivered_channels']
    assert email_mock.call_count == 2


def test_dispatch_notifications_webhook_failure_records_audit(client, app_fixture):
    _seed_triggered_alert(client, app_fixture)

    app_fixture.config['ALERT_WEBHOOK_ENABLED'] = True
    app_fixture.config['ALERT_WEBHOOK_URL'] = 'http://example.local/hook'

    with patch('server.services.notification_service.NotificationService.send_webhook_notification') as webhook_mock:
        webhook_mock.side_effect = RuntimeError('webhook down')

        response = client.post(
            '/api/alerts/dispatch',
            headers=_headers(),
            json={'channels': ['webhook'], 'webhook_retries': 1},
        )

    assert response.status_code == 202
    payload = response.get_json()
    assert payload['status'] == 'accepted'

    result = payload['job']['result']
    assert result['failure_count'] == 1
    assert result['failures'][0]['channel'] == 'webhook'
    assert result['failures'][0]['attempts'] == 2

    with app_fixture.app_context():
        audit_row = (
            AuditEvent.query
            .filter_by(action='alerts.dispatch.delivery')
            .order_by(AuditEvent.id.desc())
            .first()
        )

    assert audit_row is not None
    assert audit_row.outcome == 'failure'


def test_dispatch_notifications_deduplicates_repeated_alerts(client, app_fixture):
    app_fixture.config['ALERT_WEBHOOK_ENABLED'] = True
    app_fixture.config['ALERT_WEBHOOK_URL'] = 'http://example.local/hook'

    duplicated_alerts = [
        {
            'rule_id': 101,
            'rule_name': 'CPU Spike',
            'severity': 'warning',
            'metric': 'cpu_usage',
            'operator': '>',
            'threshold': 90,
            'actual_value': 97,
            'system_id': 10,
            'hostname': 'alpha',
            'serial_number': 'A-1',
            'triggered_at': '2026-03-17T08:00:00+00:00',
        },
        {
            'rule_id': 101,
            'rule_name': 'CPU Spike',
            'severity': 'warning',
            'metric': 'cpu_usage',
            'operator': '>',
            'threshold': 90,
            'actual_value': 98,
            'system_id': 10,
            'hostname': 'alpha',
            'serial_number': 'A-1',
            'triggered_at': '2026-03-17T08:01:00+00:00',
        },
    ]

    with patch('server.services.notification_service.NotificationService.send_webhook_notification') as webhook_mock:
        webhook_mock.return_value = None

        response = client.post(
            '/api/alerts/dispatch',
            headers=_headers(),
            json={
                'channels': ['webhook'],
                'alerts': duplicated_alerts,
                'deduplicate': True,
            },
        )

    assert response.status_code == 202
    payload = response.get_json()['job']['result']
    assert payload['raw_alerts_count'] == 2
    assert payload['alerts_count'] == 1
    assert payload['deduplicated_count'] == 1

    sent_alerts = webhook_mock.call_args[0][0]
    assert len(sent_alerts) == 1
    assert sent_alerts[0]['occurrence_count'] == 2


def test_dispatch_notifications_escalates_severity_on_repeat_threshold(client, app_fixture):
    app_fixture.config['ALERT_WEBHOOK_ENABLED'] = True
    app_fixture.config['ALERT_WEBHOOK_URL'] = 'http://example.local/hook'

    repeated_alerts = [
        {
            'rule_id': 202,
            'rule_name': 'RAM Pressure',
            'severity': 'warning',
            'metric': 'ram_usage',
            'operator': '>',
            'threshold': 85,
            'actual_value': 92,
            'system_id': 11,
            'hostname': 'beta',
            'serial_number': 'B-1',
            'triggered_at': '2026-03-17T09:00:00+00:00',
        },
        {
            'rule_id': 202,
            'rule_name': 'RAM Pressure',
            'severity': 'warning',
            'metric': 'ram_usage',
            'operator': '>',
            'threshold': 85,
            'actual_value': 93,
            'system_id': 11,
            'hostname': 'beta',
            'serial_number': 'B-1',
            'triggered_at': '2026-03-17T09:01:00+00:00',
        },
    ]

    with patch('server.services.notification_service.NotificationService.send_webhook_notification') as webhook_mock:
        webhook_mock.return_value = None

        response = client.post(
            '/api/alerts/dispatch',
            headers=_headers(),
            json={
                'channels': ['webhook'],
                'alerts': repeated_alerts,
                'deduplicate': True,
                'escalation_threshold': 2,
            },
        )

    assert response.status_code == 202
    result = response.get_json()['job']['result']
    assert result['escalated_count'] == 1

    sent_alerts = webhook_mock.call_args[0][0]
    assert sent_alerts[0]['severity'] == 'critical'
    assert sent_alerts[0]['escalated'] is True
