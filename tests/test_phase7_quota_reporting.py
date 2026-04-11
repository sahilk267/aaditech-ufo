"""Tests for Phase 7 quota expansion and reporting."""

from __future__ import annotations

from server.auth import get_api_key


def _headers(tenant_slug: str = "default") -> dict[str, str]:
    return {"X-API-Key": get_api_key(), "X-Tenant-Slug": tenant_slug}


def test_tenant_usage_report_includes_expanded_quota_domains(client):
    response = client.get("/api/tenant-usage/report", headers=_headers())

    assert response.status_code == 200
    payload = response.get_json()["tenant_usage_report"]
    quota_keys = {item["quota_key"] for item in payload["quotas"]}
    assert "alert_rules" in quota_keys
    assert "oidc_providers" in quota_keys
    assert payload["summary"]["quota_count"] >= 6


def test_alert_rule_quota_is_enforced_and_reported(client):
    quota = client.patch(
        "/api/tenant-quotas",
        headers=_headers(),
        json={"quotas": {"alert_rules": {"limit_value": 1, "is_enforced": True}}},
    )
    assert quota.status_code == 200

    first = client.post(
        "/api/alerts/rules",
        headers=_headers(),
        json={
            "name": "CPU Critical",
            "metric": "cpu_usage",
            "operator": ">",
            "threshold": 90,
            "severity": "critical",
        },
    )
    assert first.status_code == 201

    second = client.post(
        "/api/alerts/rules",
        headers=_headers(),
        json={
            "name": "RAM Critical",
            "metric": "ram_usage",
            "operator": ">",
            "threshold": 95,
            "severity": "critical",
        },
    )
    assert second.status_code == 403
    assert second.get_json()["details"]["quota"]["quota_key"] == "alert_rules"

    report = client.get("/api/tenant-usage/report", headers=_headers())
    assert report.status_code == 200
    payload = report.get_json()["tenant_usage_report"]
    alert_rules_row = next(item for item in payload["quotas"] if item["quota_key"] == "alert_rules")
    assert alert_rules_row["current_value"] == 1
    assert alert_rules_row["is_enforced"] is True
    assert payload["recent_enforcement_events"][0]["quota_key"] == "alert_rules"


def test_oidc_provider_quota_is_enforced_and_reported(client):
    quota = client.patch(
        "/api/tenant-quotas",
        headers=_headers(),
        json={"quotas": {"oidc_providers": {"limit_value": 1, "is_enforced": True}}},
    )
    assert quota.status_code == 200

    first = client.post(
        "/api/auth/oidc/providers",
        headers=_headers(),
        json={
            "name": "Primary OIDC",
            "issuer": "https://issuer-one.example.com",
            "client_id": "client-1",
            "authorization_endpoint": "https://issuer-one.example.com/auth",
            "test_mode": True,
            "test_claims": {"default": {"email": "oidc1@example.com", "name": "OIDC One"}},
            "is_enabled": True,
        },
    )
    assert first.status_code == 201

    second = client.post(
        "/api/auth/oidc/providers",
        headers=_headers(),
        json={
            "name": "Secondary OIDC",
            "issuer": "https://issuer-two.example.com",
            "client_id": "client-2",
            "authorization_endpoint": "https://issuer-two.example.com/auth",
            "test_mode": True,
            "test_claims": {"default": {"email": "oidc2@example.com", "name": "OIDC Two"}},
            "is_enabled": True,
        },
    )
    assert second.status_code == 403
    assert second.get_json()["details"]["quota"]["quota_key"] == "oidc_providers"

    usage = client.get("/api/tenant-usage", headers=_headers())
    assert usage.status_code == 200
    assert usage.get_json()["tenant_usage"]["current"]["oidc_providers"]["current_value"] == 1
