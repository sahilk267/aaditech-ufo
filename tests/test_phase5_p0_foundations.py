"""Tests for Phase 5 P0 implementation slice."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

from server.auth import get_api_key
from server.extensions import db
from server.models import Agent, AgentCredential, AgentEnrollmentToken, NotificationDelivery, Organization, TenantSecret
from server.services.backup_service import BackupService
from server.services.tenant_secret_service import TenantSecretService
from server.tenant_context import get_or_create_default_tenant


def _headers(tenant_slug: str = 'default') -> dict[str, str]:
    return {'X-API-Key': get_api_key(), 'X-Tenant-Slug': tenant_slug}


def test_agent_enrollment_token_and_enroll_flow(client, app_fixture):
    create_token = client.post(
        '/api/agents/enrollment-tokens',
        headers=_headers(),
        json={'ttl_hours': 12, 'intended_hostname_pattern': r'phase5-host-[0-9]+'},
    )
    assert create_token.status_code == 201
    payload = create_token.get_json()
    raw_token = payload['enrollment_token']
    token_id = payload['token_metadata']['id']

    enroll = client.post(
        '/api/agents/enroll',
        json={
            'enrollment_token': raw_token,
            'hostname': 'phase5-host-1',
            'serial_number': 'PHASE5-SN-001',
            'platform': 'windows',
            'agent_version': '1.2.3',
            'display_name': 'Phase 5 Host',
        },
    )
    assert enroll.status_code == 201
    enroll_payload = enroll.get_json()
    assert enroll_payload['agent']['serial_number'] == 'PHASE5-SN-001'
    assert enroll_payload['credential']['token']
    assert enroll_payload['credential']['fingerprint']

    listed = client.get('/api/agents', headers=_headers())
    assert listed.status_code == 200
    assert listed.get_json()['count'] == 1

    with app_fixture.app_context():
        agent = Agent.query.filter_by(serial_number='PHASE5-SN-001').first()
        credential = AgentCredential.query.filter_by(agent_id=agent.id, status='active').first()
        token = db.session.get(AgentEnrollmentToken, token_id)

    assert agent is not None
    assert agent.enrollment_state == 'active'
    assert credential is not None
    assert token is not None
    assert token.status == 'used'


def test_tenant_secret_create_rotate_revoke_uses_encrypted_storage(client, app_fixture):
    app_fixture.config['TENANT_SECRET_ENCRYPTION_KEY'] = 'X3KtR9x45Jz0C0e7eY7l5h8uhI7uEsT9wQW7D8BEx4k='

    created = client.post(
        '/api/tenant-secrets',
        headers=_headers(),
        json={'secret_type': 'webhook_endpoint', 'name': 'Primary Hook', 'secret_value': 'https://example.com/hook'},
    )
    assert created.status_code == 201
    secret_id = created.get_json()['secret']['id']

    listed = client.get('/api/tenant-secrets', headers=_headers())
    assert listed.status_code == 200
    assert listed.get_json()['count'] == 1
    assert 'ciphertext' not in listed.get_json()['secrets'][0]

    with app_fixture.app_context():
        secret = db.session.get(TenantSecret, secret_id)
        decrypted = TenantSecretService.decrypt_value(secret.ciphertext, app_fixture.config)

    assert secret is not None
    assert secret.ciphertext != 'https://example.com/hook'
    assert decrypted == 'https://example.com/hook'

    rotated = client.post(
        f'/api/tenant-secrets/{secret_id}/rotate',
        headers=_headers(),
        json={'secret_value': 'https://example.com/hook-v2'},
    )
    assert rotated.status_code == 200

    with app_fixture.app_context():
        secret = db.session.get(TenantSecret, secret_id)
        rotated_value = TenantSecretService.decrypt_value(secret.ciphertext, app_fixture.config)

    assert rotated_value == 'https://example.com/hook-v2'

    revoked = client.post(f'/api/tenant-secrets/{secret_id}/revoke', headers=_headers())
    assert revoked.status_code == 200

    with app_fixture.app_context():
        secret = db.session.get(TenantSecret, secret_id)
        assert secret.status == 'revoked'


def test_backup_verify_and_supportability_retention_defaults(client, app_fixture, tmp_path):
    backup_dir = tmp_path / 'backups'
    backup_dir.mkdir(parents=True)
    backup_path = backup_dir / 'backup_20260331_120000.db'

    with sqlite3.connect(backup_path) as connection:
        connection.execute('CREATE TABLE sample (id INTEGER PRIMARY KEY, name TEXT)')
        connection.execute("INSERT INTO sample(name) VALUES ('ok')")
        connection.commit()

    old_service_backup_dir = BackupService.BACKUP_DIR
    BackupService.BACKUP_DIR = str(backup_dir)
    try:
        verify = client.post('/api/backups/backup_20260331_120000.db/verify', headers=_headers())
        assert verify.status_code == 200
        verification = verify.get_json()['verification']
        assert verification['verified'] is True
        assert verification['integrity_check'] == 'ok'

        policy = client.get('/api/supportability/policy', headers=_headers())
        assert policy.status_code == 200
        retention_defaults = policy.get_json()['retention_defaults']
        assert retention_defaults['audit_events_days'] == app_fixture.config['AUDIT_RETENTION_DAYS']
        assert retention_defaults['notification_deliveries_days'] == app_fixture.config['NOTIFICATION_DELIVERY_RETENTION_DAYS']
    finally:
        BackupService.BACKUP_DIR = old_service_backup_dir


def test_enqueue_notification_delivery_purge_uses_retention_defaults(client, db_session, app_fixture):
    app_fixture.config['NOTIFICATION_DELIVERY_RETENTION_DAYS'] = 30
    with app_fixture.app_context():
        tenant = Organization.query.filter_by(slug='default').first() or get_or_create_default_tenant()
        old_delivery = NotificationDelivery(
            organization_id=tenant.id,
            status='delivered',
            channels_requested=['webhook'],
            delivered_channels=['webhook'],
            created_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(days=45),
        )
        recent_delivery = NotificationDelivery(
            organization_id=tenant.id,
            status='delivered',
            channels_requested=['webhook'],
            delivered_channels=['webhook'],
            created_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(days=5),
        )
        db_session.add_all([old_delivery, recent_delivery])
        db_session.commit()
        old_id = old_delivery.id
        recent_id = recent_delivery.id

    response = client.post(
        '/api/jobs/maintenance',
        headers=_headers(),
        json={'job': 'purge_notification_deliveries'},
    )
    assert response.status_code == 202
    assert response.get_json()['job']['job_name'] == 'purge_notification_deliveries'

    with app_fixture.app_context():
        remaining_ids = {row.id for row in NotificationDelivery.query.all()}

    assert old_id not in remaining_ids
    assert recent_id in remaining_ids
