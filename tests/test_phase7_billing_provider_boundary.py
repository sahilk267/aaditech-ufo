"""Tests for Phase 7 billing provider boundary prep."""

from __future__ import annotations

from server.auth import get_api_key


def _headers(tenant_slug: str = "default") -> dict[str, str]:
    return {"X-API-Key": get_api_key(), "X-Tenant-Slug": tenant_slug}


def test_tenant_commercial_provider_boundary_defaults(client):
    response = client.get("/api/tenant-commercial/provider-boundary", headers=_headers())
    assert response.status_code == 200
    payload = response.get_json()["provider_boundary"]
    assert payload["current_provider"] == "manual"
    assert payload["supported_providers"]["stripe"]["supports_subscription_sync"] is True
    assert payload["sync_readiness"]["can_sync_customer"] is False


def test_tenant_commercial_patch_validates_provider_fields(client):
    response = client.patch(
        "/api/tenant-commercial",
        headers=_headers(),
        json={
            "plan": {
                "plan_key": "growth",
                "status": "active",
                "billing_cycle": "monthly",
            },
            "billing_profile": {
                "provider_name": "unknown_provider",
                "billing_email": "billing@example.com",
            },
            "license": {
                "license_status": "nonsense",
                "enforcement_mode": "soft_block",
            },
        },
    )

    assert response.status_code == 400
    details = response.get_json()["details"]
    assert "billing_profile.provider_name" in details
    assert "license.license_status" in details


def test_tenant_commercial_provider_boundary_reports_ready_state(client):
    updated = client.patch(
        "/api/tenant-commercial",
        headers=_headers(),
        json={
            "plan": {
                "plan_key": "growth",
                "display_name": "Growth",
                "status": "active",
                "billing_cycle": "annual",
                "external_customer_ref": "cus_demo_123",
                "external_subscription_ref": "sub_demo_123",
                "effective_from": "2026-04-11T00:00:00",
            },
            "billing_profile": {
                "billing_email": "billing@example.com",
                "provider_name": "stripe",
                "provider_customer_ref": "cus_demo_123",
            },
            "license": {
                "license_status": "active",
                "seat_limit": 25,
                "enforcement_mode": "soft_block",
                "expires_at": "2027-04-11T00:00:00",
            },
        },
    )
    assert updated.status_code == 200
    commercial = updated.get_json()["tenant_commercial"]
    assert commercial["provider_boundary"]["sync_readiness"]["can_sync_customer"] is True
    assert commercial["provider_boundary"]["sync_readiness"]["can_sync_subscription"] is True
    assert commercial["lifecycle_semantics"]["allowed_enforcement_modes"] == ["advisory", "soft_block", "hard_block"]

    boundary = client.get("/api/tenant-commercial/provider-boundary", headers=_headers())
    assert boundary.status_code == 200
    provider_boundary = boundary.get_json()["provider_boundary"]
    assert provider_boundary["outbound_contract_preview"]["subscription"]["external_subscription_ref"] == "sub_demo_123"
    assert provider_boundary["provider_capabilities"]["supports_customer_sync"] is True
