"""Tests for Phase 7 OIDC external-provider maturity."""

from __future__ import annotations

from urllib.parse import urlparse, parse_qs

import server.blueprints.api as api_module
from server.auth import get_api_key
from server.extensions import db
from server.models import Organization, TenantOidcProvider, User


def _headers(tenant_slug: str = "default") -> dict[str, str]:
    return {"X-API-Key": get_api_key(), "X-Tenant-Slug": tenant_slug}


class _Response:
    def __init__(self, payload: dict, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise api_module.requests.HTTPError(f"{self.status_code} error")


def test_oidc_provider_discovery_populates_metadata(client, app_fixture, monkeypatch):
    def fake_get(url, timeout=0, headers=None):  # noqa: ARG001
        assert url == "https://issuer.example.com/.well-known/openid-configuration"
        return _Response(
            {
                "authorization_endpoint": "https://issuer.example.com/oauth2/authorize",
                "token_endpoint": "https://issuer.example.com/oauth2/token",
                "userinfo_endpoint": "https://issuer.example.com/oauth2/userinfo",
                "jwks_uri": "https://issuer.example.com/.well-known/jwks.json",
                "end_session_endpoint": "https://issuer.example.com/logout",
            }
        )

    monkeypatch.setattr(api_module.requests, "get", fake_get)

    response = client.post(
        "/api/auth/oidc/providers",
        headers=_headers(),
        json={
            "name": "External OIDC",
            "issuer": "https://issuer.example.com",
            "client_id": "client-123",
            "client_secret": "super-secret",
            "discovery_endpoint": "https://issuer.example.com/.well-known/openid-configuration",
            "scopes": ["openid", "profile", "email"],
            "claim_mappings": {"email": "email", "full_name": "name", "groups": "groups"},
            "role_mappings": {"admins": ["admin"]},
            "test_mode": False,
            "is_enabled": True,
            "is_default": True,
        },
    )

    assert response.status_code == 201
    provider = response.get_json()["provider"]
    assert provider["token_endpoint"] == "https://issuer.example.com/oauth2/token"
    assert provider["userinfo_endpoint"] == "https://issuer.example.com/oauth2/userinfo"
    assert provider["last_discovery_status"] == "success"

    with app_fixture.app_context():
        tenant = Organization.query.filter_by(slug="default").first()
        persisted = TenantOidcProvider.query.filter_by(organization_id=tenant.id, name="External OIDC").first()
        assert persisted is not None
        assert persisted.jwks_uri == "https://issuer.example.com/.well-known/jwks.json"


def test_external_oidc_callback_exchanges_code_and_creates_user(client, app_fixture, monkeypatch):
    client.patch("/api/tenant-settings", headers=_headers(), json={"auth_policy": {"oidc_enabled": True}})

    def fake_get(url, timeout=0, headers=None):  # noqa: ARG001
        if url.endswith("/.well-known/openid-configuration"):
            return _Response(
                {
                    "authorization_endpoint": "https://issuer.example.com/oauth2/authorize",
                    "token_endpoint": "https://issuer.example.com/oauth2/token",
                    "userinfo_endpoint": "https://issuer.example.com/oauth2/userinfo",
                }
            )
        assert url == "https://issuer.example.com/oauth2/userinfo"
        assert headers == {"Authorization": "Bearer access-123"}
        return _Response({"email": "external-user@example.com", "name": "External User", "groups": ["admins"]})

    def fake_post(url, data=None, timeout=0):  # noqa: ARG001
        assert url == "https://issuer.example.com/oauth2/token"
        assert data["grant_type"] == "authorization_code"
        assert data["client_secret"] == "super-secret"
        return _Response({"access_token": "access-123", "token_type": "Bearer"})

    monkeypatch.setattr(api_module.requests, "get", fake_get)
    monkeypatch.setattr(api_module.requests, "post", fake_post)

    provider_response = client.post(
        "/api/auth/oidc/providers",
        headers=_headers(),
        json={
            "name": "External Login",
            "issuer": "https://issuer.example.com",
            "client_id": "client-123",
            "client_secret": "super-secret",
            "discovery_endpoint": "https://issuer.example.com/.well-known/openid-configuration",
            "claim_mappings": {"email": "email", "full_name": "name", "groups": "groups"},
            "role_mappings": {"admins": ["admin"]},
            "test_mode": False,
            "is_enabled": True,
            "is_default": True,
        },
    )
    assert provider_response.status_code == 201

    start = client.post("/api/auth/oidc/login", headers={"X-Tenant-Slug": "default"}, json={"tenant_slug": "default"})
    assert start.status_code == 200
    payload = start.get_json()
    assert payload["authorization"]["mode"] == "external"
    parsed = urlparse(payload["authorization"]["authorization_url"])
    assert parsed.netloc == "issuer.example.com"
    query = parse_qs(parsed.query)
    assert query["client_id"] == ["client-123"]

    callback = client.get(f"/api/auth/oidc/callback?state={query['state'][0]}&code=demo-code")
    assert callback.status_code == 200
    callback_payload = callback.get_json()
    assert callback_payload["user"]["email"] == "external-user@example.com"
    assert callback_payload["provider"]["last_auth_status"] == "success"

    with app_fixture.app_context():
        user = User.query.filter_by(email="external-user@example.com").first()
        assert user is not None
        assert any(role.name == "admin" for role in user.roles)


def test_external_oidc_callback_records_failure_state(client, app_fixture, monkeypatch):
    client.patch("/api/tenant-settings", headers=_headers(), json={"auth_policy": {"oidc_enabled": True}})

    def fake_get(url, timeout=0, headers=None):  # noqa: ARG001
        if url.endswith("/.well-known/openid-configuration"):
            return _Response(
                {
                    "authorization_endpoint": "https://issuer.example.com/oauth2/authorize",
                    "token_endpoint": "https://issuer.example.com/oauth2/token",
                    "userinfo_endpoint": "https://issuer.example.com/oauth2/userinfo",
                }
            )
        raise AssertionError(f"Unexpected GET {url}")

    def fake_post(url, data=None, timeout=0):  # noqa: ARG001
        raise api_module.requests.RequestException("upstream token failure")

    monkeypatch.setattr(api_module.requests, "get", fake_get)
    monkeypatch.setattr(api_module.requests, "post", fake_post)

    provider_response = client.post(
        "/api/auth/oidc/providers",
        headers=_headers(),
        json={
            "name": "Broken External Login",
            "issuer": "https://issuer.example.com",
            "client_id": "client-123",
            "client_secret": "super-secret",
            "discovery_endpoint": "https://issuer.example.com/.well-known/openid-configuration",
            "test_mode": False,
            "is_enabled": True,
            "is_default": True,
        },
    )
    assert provider_response.status_code == 201
    provider_id = provider_response.get_json()["provider"]["id"]

    start = client.post(
        "/api/auth/oidc/login",
        headers={"X-Tenant-Slug": "default"},
        json={"tenant_slug": "default", "provider_id": provider_id},
    )
    parsed = urlparse(start.get_json()["authorization"]["authorization_url"])
    state = parse_qs(parsed.query)["state"][0]

    callback = client.get(f"/api/auth/oidc/callback?state={state}&code=demo-code")
    assert callback.status_code == 502

    with app_fixture.app_context():
        provider = db.session.get(TenantOidcProvider, provider_id)
        assert provider is not None
        assert provider.last_auth_status == "error"
        assert "upstream token failure" in (provider.last_error or "")
