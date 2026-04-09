"""Tests for Phase 6 quotas and usage metrics foundation."""

from __future__ import annotations

from datetime import datetime

from server.auth import get_api_key
from server.extensions import db
from server.models import (
    AutomationWorkflow,
    Organization,
    SystemData,
    TenantQuotaPolicy,
    TenantUsageMetric,
)
from server.tenant_context import get_or_create_default_tenant


def _headers(tenant_slug: str = 'default') -> dict[str, str]:
    return {'X-API-Key': get_api_key(), 'X-Tenant-Slug': tenant_slug}


def _default_tenant() -> Organization:
    return Organization.query.filter_by(slug='default').first() or get_or_create_default_tenant()


def test_tenant_quotas_get_patch_and_usage_snapshot(client, app_fixture):
    response = client.get('/api/tenant-quotas', headers=_headers())
    assert response.status_code == 200
    quotas = response.get_json()['tenant_quotas']
    assert quotas['effective']['monitored_systems']['is_enforced'] is False

    updated = client.patch(
        '/api/tenant-quotas',
        headers=_headers(),
        json={
            'quotas': {
                'monitored_systems': {'limit_value': 2, 'is_enforced': True, 'metadata': {'plan': 'starter'}},
                'automation_workflows': {'limit_value': 1, 'is_enforced': True},
            }
        },
    )
    assert updated.status_code == 200
    effective = updated.get_json()['tenant_quotas']['effective']
    assert effective['monitored_systems']['limit_value'] == 2
    assert effective['monitored_systems']['is_enforced'] is True

    usage = client.get('/api/tenant-usage', headers=_headers())
    assert usage.status_code == 200
    usage_payload = usage.get_json()['tenant_usage']
    assert 'monitored_systems' in usage_payload['current']
    assert 'automation_workflows' in usage_payload['current']

    with app_fixture.app_context():
        tenant = _default_tenant()
        policy = TenantQuotaPolicy.query.filter_by(organization_id=tenant.id, quota_key='monitored_systems').first()
        metric = TenantUsageMetric.query.filter_by(organization_id=tenant.id, metric_key='monitored_systems').first()
        assert policy is not None
        assert policy.limit_value == 2
        assert metric is not None


def test_monitored_systems_quota_is_enforced(client):
    quota = client.patch(
        '/api/tenant-quotas',
        headers=_headers(),
        json={'quotas': {'monitored_systems': {'limit_value': 1, 'is_enforced': True}}},
    )
    assert quota.status_code == 200

    first = client.post(
        '/api/submit_data',
        headers=_headers(),
        json={
            'serial_number': 'QSYS-001',
            'hostname': 'quota-host-1',
            'last_update': datetime.utcnow().isoformat(),
            'status': 'active',
            'cpu_usage': 10.0,
        },
    )
    assert first.status_code == 200

    second = client.post(
        '/api/submit_data',
        headers=_headers(),
        json={
            'serial_number': 'QSYS-002',
            'hostname': 'quota-host-2',
            'last_update': datetime.utcnow().isoformat(),
            'status': 'active',
            'cpu_usage': 15.0,
        },
    )
    assert second.status_code == 403
    assert second.get_json()['details']['quota']['quota_key'] == 'monitored_systems'


def test_automation_workflow_quota_is_enforced(client, app_fixture):
    quota = client.patch(
        '/api/tenant-quotas',
        headers=_headers(),
        json={'quotas': {'automation_workflows': {'limit_value': 1, 'is_enforced': True}}},
    )
    assert quota.status_code == 200

    first = client.post(
        '/api/automation/workflows',
        headers=_headers(),
        json={
            'name': 'Workflow One',
            'trigger_type': 'manual',
            'trigger_conditions': {},
            'action_type': 'service_restart',
            'action_config': {'service_name': 'svc-a'},
        },
    )
    assert first.status_code == 201

    second = client.post(
        '/api/automation/workflows',
        headers=_headers(),
        json={
            'name': 'Workflow Two',
            'trigger_type': 'manual',
            'trigger_conditions': {},
            'action_type': 'service_restart',
            'action_config': {'service_name': 'svc-b'},
        },
    )
    assert second.status_code == 403
    assert second.get_json()['details']['quota']['quota_key'] == 'automation_workflows'

    with app_fixture.app_context():
        tenant = _default_tenant()
        assert AutomationWorkflow.query.filter_by(organization_id=tenant.id).count() == 1


def test_tenant_secret_quota_is_enforced(client, app_fixture):
    quota = client.patch(
        '/api/tenant-quotas',
        headers=_headers(),
        json={'quotas': {'tenant_secrets': {'limit_value': 1, 'is_enforced': True}}},
    )
    assert quota.status_code == 200

    first = client.post(
        '/api/tenant-secrets',
        headers=_headers(),
        json={'secret_type': 'webhook', 'name': 'primary', 'secret_value': 'value-1'},
    )
    assert first.status_code == 201

    second = client.post(
        '/api/tenant-secrets',
        headers=_headers(),
        json={'secret_type': 'webhook', 'name': 'secondary', 'secret_value': 'value-2'},
    )
    assert second.status_code == 403
    assert second.get_json()['details']['quota']['quota_key'] == 'tenant_secrets'

    usage = client.get('/api/tenant-usage', headers=_headers())
    assert usage.status_code == 200
    assert usage.get_json()['tenant_usage']['current']['tenant_secrets']['current_value'] == 1
