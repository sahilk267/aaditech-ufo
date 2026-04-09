"""Tests for Phase 6 billing/licensing preparation surfaces."""

from __future__ import annotations

from server.auth import get_api_key
from server.extensions import db
from server.models import Organization, TenantBillingProfile, TenantLicense, TenantPlan
from server.tenant_context import get_or_create_default_tenant


def _headers(tenant_slug: str = 'default') -> dict[str, str]:
    return {'X-API-Key': get_api_key(), 'X-Tenant-Slug': tenant_slug}


def _default_tenant() -> Organization:
    return Organization.query.filter_by(slug='default').first() or get_or_create_default_tenant()


def test_tenant_commercial_defaults_and_patch(client, app_fixture):
    response = client.get('/api/tenant-commercial', headers=_headers())
    assert response.status_code == 200
    payload = response.get_json()['tenant_commercial']
    assert payload['plan']['plan_key'] == 'starter'
    assert payload['billing_profile']['provider_name'] == 'manual'
    assert payload['license']['license_status'] == 'draft'
    assert payload['contract_boundaries']['entitlements_source'] == 'tenant_entitlements'

    updated = client.patch(
        '/api/tenant-commercial',
        headers=_headers(),
        json={
            'plan': {
                'plan_key': 'growth',
                'display_name': 'Growth',
                'status': 'active',
                'billing_cycle': 'monthly',
                'external_customer_ref': 'cus_demo_123',
            },
            'billing_profile': {
                'billing_email': 'billing@example.com',
                'provider_name': 'stripe',
                'provider_customer_ref': 'cus_demo_123',
            },
            'license': {
                'license_status': 'trial',
                'seat_limit': 25,
                'enforcement_mode': 'advisory',
                'license_key_hint': 'lic_***1234',
            },
        },
    )
    assert updated.status_code == 200
    commercial = updated.get_json()['tenant_commercial']
    assert commercial['plan']['plan_key'] == 'growth'
    assert commercial['billing_profile']['provider_name'] == 'stripe'
    assert commercial['license']['seat_limit'] == 25

    with app_fixture.app_context():
        tenant = _default_tenant()
        plan = TenantPlan.query.filter_by(organization_id=tenant.id).first()
        billing = TenantBillingProfile.query.filter_by(organization_id=tenant.id).first()
        license_row = TenantLicense.query.filter_by(organization_id=tenant.id).first()
        assert plan is not None
        assert billing is not None
        assert license_row is not None
        assert plan.plan_key == 'growth'
        assert billing.provider_name == 'stripe'
        assert license_row.license_status == 'trial'
