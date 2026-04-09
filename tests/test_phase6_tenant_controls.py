"""Tests for Phase 6 tenant entitlements and feature flags foundation."""

from __future__ import annotations

from server.auth import get_api_key
from server.extensions import db
from server.models import IncidentRecord, Organization, TenantEntitlement, TenantFeatureFlag
from server.tenant_context import get_or_create_default_tenant


def _headers(tenant_slug: str = 'default') -> dict[str, str]:
    return {'X-API-Key': get_api_key(), 'X-Tenant-Slug': tenant_slug}


def _default_tenant() -> Organization:
    return Organization.query.filter_by(slug='default').first() or get_or_create_default_tenant()


def test_tenant_controls_get_and_patch(client, app_fixture):
    response = client.get('/api/tenant-controls', headers=_headers())
    assert response.status_code == 200
    controls = response.get_json()['tenant_controls']
    assert controls['effective']['entitlements']['case_management_v1']['enabled'] is True
    assert controls['effective']['feature_flags']['incident_case_management_v1']['enabled'] is True

    updated = client.patch(
        '/api/tenant-controls',
        headers=_headers(),
        json={
            'entitlements': {
                'case_management_v1': {'enabled': False, 'limit_value': 0, 'metadata': {'reason': 'plan_restricted'}},
            },
            'feature_flags': {
                'incident_case_management_v1': {'enabled': False, 'description': 'Disabled for testing'},
            },
        },
    )
    assert updated.status_code == 200
    updated_controls = updated.get_json()['tenant_controls']
    assert updated_controls['effective']['entitlements']['case_management_v1']['enabled'] is False
    assert updated_controls['effective']['feature_flags']['incident_case_management_v1']['enabled'] is False

    with app_fixture.app_context():
        tenant = _default_tenant()
        entitlement = TenantEntitlement.query.filter_by(organization_id=tenant.id, entitlement_key='case_management_v1').first()
        feature_flag = TenantFeatureFlag.query.filter_by(organization_id=tenant.id, flag_key='incident_case_management_v1').first()

    assert entitlement is not None
    assert entitlement.is_enabled is False
    assert entitlement.limit_value == 0
    assert feature_flag is not None
    assert feature_flag.is_enabled is False


def test_incident_case_comments_are_gated_by_controls(client, db_session, app_fixture):
    with app_fixture.app_context():
        tenant = _default_tenant()
        incident = IncidentRecord(
            organization_id=tenant.id,
            fingerprint='tenant-controls-incident',
            hostname='srv-controls',
            title='Tenant Controls Incident',
            severity='warning',
            status='open',
        )
        db_session.add(incident)
        db_session.flush()

        db_session.add(TenantEntitlement(organization_id=tenant.id, entitlement_key='case_management_v1', is_enabled=False))
        db_session.add(TenantFeatureFlag(organization_id=tenant.id, flag_key='incident_case_management_v1', is_enabled=False))
        db_session.commit()
        incident_id = incident.id

    create_response = client.post(
        f'/api/incidents/{incident_id}/comments',
        headers=_headers(),
        json={'body': 'Should not be allowed while controls are disabled.'},
    )
    assert create_response.status_code == 403

    list_response = client.get(f'/api/incidents/{incident_id}/comments', headers=_headers())
    assert list_response.status_code == 403
