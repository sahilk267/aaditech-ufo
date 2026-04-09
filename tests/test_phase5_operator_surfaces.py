"""Tests for Phase 5 operator history and incident-management surfaces."""

from __future__ import annotations

from datetime import UTC, datetime

from server.auth import get_api_key, hash_password
from server.extensions import db
from server.models import (
    AuditEvent,
    AutomationWorkflow,
    IncidentRecord,
    NotificationDelivery,
    Organization,
    User,
    WorkflowRun,
)
from server.tenant_context import get_or_create_default_tenant


def _headers(tenant_slug: str = 'default') -> dict[str, str]:
    return {'X-API-Key': get_api_key(), 'X-Tenant-Slug': tenant_slug}


def _default_tenant() -> Organization:
    return Organization.query.filter_by(slug='default').first() or get_or_create_default_tenant()


def test_operations_timeline_merges_audit_workflow_delivery_and_incident(client, db_session, app_fixture):
    with app_fixture.app_context():
        tenant = _default_tenant()
        workflow = AutomationWorkflow(
            organization_id=tenant.id,
            name='Timeline Workflow',
            trigger_type='manual',
            trigger_conditions={},
            action_type='notify',
            action_config={'channel': 'email'},
        )
        db_session.add(workflow)
        db_session.flush()

        db_session.add(AuditEvent(action='tenant.settings.update', outcome='success', tenant_id=tenant.id, event_metadata={'source': 'test'}))
        db_session.add(WorkflowRun(organization_id=tenant.id, workflow_id=workflow.id, status='success', trigger_source='manual', dry_run=False))
        db_session.add(NotificationDelivery(organization_id=tenant.id, status='failed', channels_requested=['webhook'], delivered_channels=[]))
        db_session.add(IncidentRecord(organization_id=tenant.id, fingerprint='timeline-incident', title='Timeline incident', severity='warning', status='open'))
        db_session.commit()

    response = client.get('/api/operations/timeline?limit=10', headers=_headers())
    assert response.status_code == 200
    payload = response.get_json()
    kinds = {item['kind'] for item in payload['timeline']}
    assert {'audit_event', 'workflow_run', 'notification_delivery', 'incident'}.issubset(kinds)


def test_workflow_run_detail_and_delivery_redeliver(client, db_session, app_fixture):
    with app_fixture.app_context():
        tenant = _default_tenant()
        workflow = AutomationWorkflow(
            organization_id=tenant.id,
            name='Retry Workflow',
            trigger_type='manual',
            trigger_conditions={},
            action_type='notify',
            action_config={'channel': 'email'},
        )
        db_session.add(workflow)
        db_session.flush()

        run = WorkflowRun(
            organization_id=tenant.id,
            workflow_id=workflow.id,
            status='failed',
            trigger_source='manual',
            dry_run=True,
            error_reason='timeout',
        )
        delivery = NotificationDelivery(
            organization_id=tenant.id,
            status='failed',
            channels_requested=['email'],
            delivered_channels=[],
            failure_count=1,
            failures=[{'channel': 'email', 'reason': 'smtp timeout'}],
            alert_snapshot=[{'title': 'CPU high', 'severity': 'critical'}],
        )
        db_session.add_all([run, delivery])
        db_session.commit()
        run_id = run.id
        delivery_id = delivery.id

    run_response = client.get(f'/api/automation/workflow-runs/{run_id}', headers=_headers())
    assert run_response.status_code == 200
    assert run_response.get_json()['workflow_run']['error_reason'] == 'timeout'

    detail_response = client.get(f'/api/alerts/delivery-history/{delivery_id}', headers=_headers())
    assert detail_response.status_code == 200
    assert detail_response.get_json()['delivery']['failure_count'] == 1

    redeliver_response = client.post(f'/api/alerts/delivery-history/{delivery_id}/redeliver', headers=_headers())
    assert redeliver_response.status_code == 202
    assert redeliver_response.get_json()['source_delivery_id'] == delivery_id

    with app_fixture.app_context():
        tenant = _default_tenant()
        assert NotificationDelivery.query.filter_by(organization_id=tenant.id).count() == 2


def test_incident_detail_and_operator_update(client, db_session, app_fixture):
    with app_fixture.app_context():
        tenant = _default_tenant()
        user = User(
            organization_id=tenant.id,
            email='operator@example.com',
            full_name='Operator',
            password_hash=hash_password('StrongPass123'),
            is_active=True,
        )
        db_session.add(user)
        db_session.flush()

        incident = IncidentRecord(
            organization_id=tenant.id,
            fingerprint='operator-incident',
            hostname='srv-operator',
            title='Operator incident',
            severity='critical',
            status='open',
            alert_count=2,
            metric_count=1,
        )
        db_session.add(incident)
        db_session.commit()
        incident_id = incident.id
        user_id = user.id

    detail_response = client.get(f'/api/incidents/{incident_id}', headers=_headers())
    assert detail_response.status_code == 200
    assert detail_response.get_json()['incident']['status'] == 'open'

    update_response = client.patch(
        f'/api/incidents/{incident_id}',
        headers=_headers(),
        json={
            'status': 'resolved',
            'assigned_to_user_id': user_id,
            'resolution_summary': 'Resolved after confirming the alert was transient.',
        },
    )
    assert update_response.status_code == 200
    incident_payload = update_response.get_json()['incident']
    assert incident_payload['status'] == 'resolved'
    assert incident_payload['assigned_to_user_id'] == user_id
    assert incident_payload['resolution_summary'] == 'Resolved after confirming the alert was transient.'
    assert incident_payload['acknowledged_at'] is not None
