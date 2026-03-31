"""Tests for Phase 5 tenant settings, history APIs, and supportability surfaces."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

from server.auth import get_api_key
from server.extensions import db
from server.models import (
    AutomationWorkflow,
    IncidentRecord,
    LogEntry,
    NotificationDelivery,
    Organization,
    TenantSetting,
    WorkflowRun,
)
from server.services.backup_service import BackupService
from server.tenant_context import get_or_create_default_tenant


def _headers(tenant_slug: str = 'default') -> dict[str, str]:
    return {'X-API-Key': get_api_key(), 'X-Tenant-Slug': tenant_slug}


def _default_tenant() -> Organization:
    return Organization.query.filter_by(slug='default').first() or get_or_create_default_tenant()


def test_tenant_settings_get_and_patch(client, app_fixture):
    response = client.get('/api/tenant-settings', headers=_headers())
    assert response.status_code == 200
    payload = response.get_json()
    assert payload['tenant_settings']['retention_settings']['audit_events_days'] == app_fixture.config['AUDIT_RETENTION_DAYS']

    updated = client.patch(
        '/api/tenant-settings',
        headers=_headers(),
        json={
            'notification_settings': {'email_enabled': True, 'digest_frequency': 'hourly'},
            'branding_settings': {'product_name': 'AADITECH UFO'},
            'feature_flags': {'new_incident_timeline': True},
        },
    )
    assert updated.status_code == 200
    updated_payload = updated.get_json()['tenant_settings']
    assert updated_payload['notification_settings']['digest_frequency'] == 'hourly'
    assert updated_payload['branding_settings']['product_name'] == 'AADITECH UFO'
    assert updated_payload['feature_flags']['new_incident_timeline'] is True

    with app_fixture.app_context():
        tenant = _default_tenant()
        settings = TenantSetting.query.filter_by(organization_id=tenant.id).first()

    assert settings is not None
    assert settings.branding_settings['product_name'] == 'AADITECH UFO'


def test_history_read_apis_return_tenant_scoped_records(client, db_session, app_fixture):
    with app_fixture.app_context():
        tenant = _default_tenant()
        workflow = AutomationWorkflow(
            organization_id=tenant.id,
            name='Phase 5 Workflow',
            trigger_type='manual',
            trigger_conditions={'severity': 'critical'},
            action_type='notify',
            action_config={'channel': 'email'},
        )
        db_session.add(workflow)
        db_session.flush()

        successful_run = WorkflowRun(
            organization_id=tenant.id,
            workflow_id=workflow.id,
            trigger_source='manual',
            dry_run=False,
            status='success',
            input_payload={'source': 'test'},
            action_result={'sent': True},
            execution_metadata={'duration_ms': 12},
            executed_at=datetime.now(UTC).replace(tzinfo=None),
        )
        failed_run = WorkflowRun(
            organization_id=tenant.id,
            workflow_id=workflow.id,
            trigger_source='schedule',
            dry_run=True,
            status='failed',
            error_reason='timeout',
            input_payload={'source': 'schedule'},
            execution_metadata={'duration_ms': 999},
            executed_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=5),
        )
        delivered = NotificationDelivery(
            organization_id=tenant.id,
            task_id='task-1',
            delivery_scope='alerts.dispatch',
            status='delivered',
            channels_requested=['email'],
            delivered_channels=['email'],
            alerts_count=1,
            raw_alerts_count=1,
            deduplicated_count=0,
            escalated_count=0,
            failure_count=0,
            alert_snapshot=[{'title': 'CPU high'}],
        )
        failed_delivery = NotificationDelivery(
            organization_id=tenant.id,
            task_id='task-2',
            delivery_scope='alerts.dispatch',
            status='failed',
            channels_requested=['webhook'],
            delivered_channels=[],
            alerts_count=1,
            raw_alerts_count=1,
            deduplicated_count=0,
            escalated_count=0,
            failure_count=1,
            failures=[{'channel': 'webhook', 'reason': 'timeout'}],
            alert_snapshot=[{'title': 'Disk full'}],
        )
        open_incident = IncidentRecord(
            organization_id=tenant.id,
            fingerprint='incident-open',
            hostname='srv-1',
            severity='critical',
            status='open',
            title='CPU saturation',
            alert_count=2,
            metric_count=1,
            occurrence_count=1,
            metrics=['cpu_usage'],
            sample_alerts=[{'title': 'CPU 99%'}],
        )
        resolved_incident = IncidentRecord(
            organization_id=tenant.id,
            fingerprint='incident-resolved',
            hostname='srv-2',
            severity='warning',
            status='resolved',
            title='Memory spike',
            alert_count=1,
            metric_count=1,
            occurrence_count=2,
            metrics=['ram_usage'],
            sample_alerts=[{'title': 'RAM 91%'}],
            resolved_at=datetime.now(UTC).replace(tzinfo=None),
        )
        db_session.add_all([successful_run, failed_run, delivered, failed_delivery, open_incident, resolved_incident])
        db_session.commit()

    workflow_runs = client.get('/api/automation/workflow-runs?status=success', headers=_headers())
    assert workflow_runs.status_code == 200
    workflow_payload = workflow_runs.get_json()
    assert workflow_payload['total'] == 1
    assert workflow_payload['workflow_runs'][0]['status'] == 'success'
    assert workflow_payload['workflow_runs'][0]['action_result']['sent'] is True

    deliveries = client.get('/api/alerts/delivery-history?status=failed', headers=_headers())
    assert deliveries.status_code == 200
    delivery_payload = deliveries.get_json()
    assert delivery_payload['total'] == 1
    assert delivery_payload['deliveries'][0]['status'] == 'failed'
    assert delivery_payload['deliveries'][0]['failure_count'] == 1

    incidents = client.get('/api/incidents?status=open', headers=_headers())
    assert incidents.status_code == 200
    incident_payload = incidents.get_json()
    assert incident_payload['total'] == 1
    assert incident_payload['incidents'][0]['fingerprint'] == 'incident-open'
    assert incident_payload['incidents'][0]['severity'] == 'critical'


def test_supportability_metrics_surface_counts(client, db_session, app_fixture):
    with app_fixture.app_context():
        tenant = _default_tenant()
        workflow = AutomationWorkflow(
            organization_id=tenant.id,
            name='Metrics Workflow',
            trigger_type='manual',
            trigger_conditions={},
            action_type='notify',
            action_config={'channel': 'email'},
        )
        db_session.add(workflow)
        db_session.flush()
        db_session.add(
            WorkflowRun(
                organization_id=tenant.id,
                workflow_id=workflow.id,
                trigger_source='manual',
                dry_run=False,
                status='success',
                input_payload={'source': 'metrics'},
            )
        )
        db_session.add(
            NotificationDelivery(
                organization_id=tenant.id,
                status='delivered',
                channels_requested=['email'],
                delivered_channels=['email'],
            )
        )
        db_session.add(
            IncidentRecord(
                organization_id=tenant.id,
                fingerprint='incident-metrics',
                hostname='srv-metrics',
                severity='warning',
                status='open',
                title='Metrics incident',
            )
        )
        db_session.add(
            LogEntry(
                organization_id=tenant.id,
                source_name='system',
                adapter='linux_test_double',
                capture_kind='search',
                severity='info',
                message='hello',
                raw_entry='hello',
            )
        )
        db_session.commit()

    response = client.get('/api/supportability/metrics', headers=_headers())
    assert response.status_code == 200
    metrics = response.get_json()['metrics']
    assert metrics['counts']['workflow_runs'] == 1
    assert metrics['counts']['notification_deliveries'] == 1
    assert metrics['counts']['incidents_total'] == 1
    assert metrics['counts']['incidents_open'] == 1
    assert metrics['counts']['log_entries'] == 1
    assert metrics['retention_defaults']['workflow_runs_days'] == app_fixture.config['WORKFLOW_RUN_RETENTION_DAYS']
    assert 'inline' in metrics['queue']['mode']


def test_restore_drill_endpoint_returns_checklist(client, tmp_path):
    backup_dir = tmp_path / 'backups'
    backup_dir.mkdir(parents=True)
    backup_path = backup_dir / 'backup_20260331_220000.db'

    with sqlite3.connect(backup_path) as connection:
        connection.execute('CREATE TABLE sample (id INTEGER PRIMARY KEY, value TEXT)')
        connection.execute("INSERT INTO sample(value) VALUES ('restore-drill')")
        connection.commit()

    old_backup_dir = BackupService.BACKUP_DIR
    BackupService.BACKUP_DIR = str(backup_dir)
    try:
        response = client.post('/api/backups/backup_20260331_220000.db/restore-drill', headers=_headers())
    finally:
        BackupService.BACKUP_DIR = old_backup_dir

    assert response.status_code == 200
    payload = response.get_json()['restore_drill']
    assert payload['success'] is True
    assert payload['verification']['verified'] is True
    checklist_status = {item['id']: item['status'] for item in payload['checklist']}
    assert checklist_status['backup_exists'] == 'passed'
    assert checklist_status['integrity_check'] == 'passed'
    assert checklist_status['restore_copy_readable'] == 'passed'
    assert checklist_status['app_smoke_after_restore'] == 'manual_followup_required'
