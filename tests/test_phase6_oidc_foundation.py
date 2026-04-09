"""Tests for Phase 6 OIDC foundation and tenant-scoped provider admin APIs."""

from __future__ import annotations

from urllib.parse import urlparse

from server.auth import (
    WEB_SESSION_AUTH_VERSION_KEY,
    WEB_SESSION_TENANT_SLUG_KEY,
    WEB_SESSION_USER_ID_KEY,
    get_api_key,
)
from server.models import Organization, TenantSecret, User
from server.services.tenant_secret_service import TenantSecretService


def _headers(tenant_slug: str = "default") -> dict[str, str]:
    return {"X-API-Key": get_api_key(), "X-Tenant-Slug": tenant_slug}


def _create_provider(client, email: str = "oidc-user@example.com"):
    response = client.post(
        "/api/auth/oidc/providers",
        headers=_headers(),
        json={
            "name": "Example OIDC",
            "issuer": "https://issuer.example.com",
            "client_id": "client-123",
            "client_secret": "super-secret",
            "authorization_endpoint": "https://issuer.example.com/oauth2/authorize",
            "scopes": ["openid", "profile", "email"],
            "claim_mappings": {
                "email": "email",
                "full_name": "name",
                "groups": "groups",
            },
            "role_mappings": {
                "admins": ["admin"],
            },
            "test_mode": True,
            "test_claims": {
                "default": {
                    "email": email,
                    "name": "OIDC Operator",
                    "groups": ["admins"],
                },
            },
            "is_enabled": True,
            "is_default": True,
        },
    )
    assert response.status_code == 201
    return response.get_json()["provider"]


def test_tenant_settings_accept_oidc_policy_flags(client):
    response = client.patch(
        "/api/tenant-settings",
        headers=_headers(),
        json={"auth_policy": {"oidc_enabled": True, "local_admin_fallback_enabled": False}},
    )
    assert response.status_code == 200
    auth_policy = response.get_json()["tenant_settings"]["auth_policy"]
    assert auth_policy["oidc_enabled"] is True
    assert auth_policy["local_admin_fallback_enabled"] is False


def test_oidc_provider_create_persists_secret(client, app_fixture):
    provider = _create_provider(client)
    assert provider["has_client_secret"] is True
    assert provider["client_secret_secret_name"] == "oidc-example-oidc-client-secret"

    with app_fixture.app_context():
        tenant = Organization.query.filter_by(slug="default").first()
        secret = TenantSecret.query.filter_by(
            organization_id=tenant.id,
            secret_type="oidc_client",
            name="oidc-example-oidc-client-secret",
        ).first()
        assert secret is not None
        assert TenantSecretService.decrypt_value(secret.ciphertext, app_fixture.config) == "super-secret"


def test_test_mode_oidc_login_callback_creates_user_and_tokens(client, app_fixture):
    settings = client.patch("/api/tenant-settings", headers=_headers(), json={"auth_policy": {"oidc_enabled": True}})
    assert settings.status_code == 200
    _create_provider(client, email="sso-user@example.com")

    start = client.post(
        "/api/auth/oidc/login",
        headers={"X-Tenant-Slug": "default"},
        json={"tenant_slug": "default"},
    )
    assert start.status_code == 200
    payload = start.get_json()
    assert payload["authorization"]["mode"] == "test"
    callback_path = urlparse(payload["authorization"]["authorization_url"]).path
    callback_query = urlparse(payload["authorization"]["authorization_url"]).query

    callback = client.get(f"{callback_path}?{callback_query}")
    assert callback.status_code == 200
    callback_payload = callback.get_json()
    assert callback_payload["created_user"] is True
    assert callback_payload["user"]["email"] == "sso-user@example.com"
    role_names = {role["name"] for role in callback_payload["user"]["roles"]}
    assert "admin" in role_names

    me = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {callback_payload['tokens']['access_token']}"},
    )
    assert me.status_code == 200

    with app_fixture.app_context():
        user = User.query.filter_by(email="sso-user@example.com").first()
        assert user is not None
        assert any(role.name == "admin" for role in user.roles)


def test_test_mode_oidc_login_can_start_web_session(client, app_fixture):
    settings = client.patch("/api/tenant-settings", headers=_headers(), json={"auth_policy": {"oidc_enabled": True}})
    assert settings.status_code == 200
    provider = _create_provider(client, email="browser-sso@example.com")

    start = client.post(
        "/api/auth/oidc/login",
        headers={"X-Tenant-Slug": "default"},
        json={"tenant_slug": "default", "provider_id": provider["id"], "web_session": True, "redirect_uri": "/app"},
    )
    assert start.status_code == 200
    auth_url = start.get_json()["authorization"]["authorization_url"]
    parsed = urlparse(auth_url)

    callback = client.get(f"{parsed.path}?{parsed.query}", follow_redirects=False)
    assert callback.status_code == 302
    assert callback.headers["Location"] == "/app"

    with client.session_transaction() as sess:
        assert sess[WEB_SESSION_TENANT_SLUG_KEY] == "default"
        assert sess[WEB_SESSION_USER_ID_KEY] > 0
        assert sess[WEB_SESSION_AUTH_VERSION_KEY] >= 1

    with app_fixture.app_context():
        tenant = Organization.query.filter_by(slug="default").first()
        user = User.query.filter_by(organization_id=tenant.id, email="browser-sso@example.com").first()
        assert user is not None
        assert any(role.name == "admin" for role in user.roles)
