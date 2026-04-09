"""Tests for Phase 6 enterprise-auth local hardening kickoff."""

from __future__ import annotations

from datetime import UTC, datetime
import uuid

from server.auth import (
    WEB_SESSION_AUTH_VERSION_KEY,
    WEB_SESSION_STARTED_AT_KEY,
    WEB_SESSION_TENANT_SLUG_KEY,
    WEB_SESSION_USER_ID_KEY,
    get_api_key,
    hash_password,
)
from server.extensions import db
from server.models import Organization, User
from server.tenant_context import get_or_create_default_tenant


def _headers(tenant_slug: str = "default") -> dict[str, str]:
    return {"X-API-Key": get_api_key(), "X-Tenant-Slug": tenant_slug}


def _default_tenant() -> Organization:
    return Organization.query.filter_by(slug="default").first() or get_or_create_default_tenant()


def _register_user(client, email: str, password: str = "StrongPass123") -> int:
    response = client.post(
        "/api/auth/register",
        headers=_headers(),
        json={"email": email, "full_name": "Tenant Owner", "password": password},
    )
    assert response.status_code == 201
    return response.get_json()["user"]["id"]


def _login(client, email: str, password: str):
    return client.post(
        "/api/auth/login",
        headers={"X-Tenant-Slug": "default"},
        json={"email": email, "password": password},
    )


def test_tenant_settings_auth_policy_defaults_and_validation(client):
    response = client.get("/api/tenant-settings", headers=_headers())
    assert response.status_code == 200
    auth_policy = response.get_json()["tenant_settings"]["auth_policy"]
    assert auth_policy["min_password_length"] == 8
    assert auth_policy["lockout_threshold"] == 5
    assert auth_policy["session_max_age_minutes"] == 10080

    invalid = client.patch(
        "/api/tenant-settings",
        headers=_headers(),
        json={"auth_policy": {"min_password_length": 4, "unknown_key": True}},
    )
    assert invalid.status_code == 400
    details = invalid.get_json()["details"]
    assert "auth_policy.min_password_length" in details
    assert "auth_policy.unknown_key" in details


def test_password_policy_is_enforced_on_registration(client):
    policy_update = client.patch(
        "/api/tenant-settings",
        headers=_headers(),
        json={
            "auth_policy": {
                "min_password_length": 12,
                "require_uppercase": True,
                "require_number": True,
            }
        },
    )
    assert policy_update.status_code == 200

    weak = client.post(
        "/api/auth/register",
        headers=_headers(),
        json={"email": "weak@example.com", "full_name": "Weak User", "password": "lowercaseonly"},
    )
    assert weak.status_code == 400
    assert "Must include an uppercase letter" in weak.get_json()["details"]["password"]

    strong = client.post(
        "/api/auth/register",
        headers=_headers(),
        json={"email": "strong@example.com", "full_name": "Strong User", "password": "StrongPass123"},
    )
    assert strong.status_code == 201


def test_login_lockout_and_session_revoke_flow(client, app_fixture):
    tenant_settings = client.patch(
        "/api/tenant-settings",
        headers=_headers(),
        json={"auth_policy": {"lockout_threshold": 2, "lockout_minutes": 30}},
    )
    assert tenant_settings.status_code == 200

    email = f"lockout-{uuid.uuid4().hex[:8]}@example.com"
    user_id = _register_user(client, email)

    first = _login(client, email, "WrongPass123")
    second = _login(client, email, "WrongPass123")
    locked = _login(client, email, "StrongPass123")

    assert first.status_code == 401
    assert second.status_code == 401
    assert locked.status_code == 401
    assert locked.get_json()["message"] == "Account temporarily locked"

    with app_fixture.app_context():
        user = db.session.get(User, user_id)
        assert user.failed_login_attempts == 2
        assert user.locked_until is not None
        user.locked_until = datetime.now(UTC).replace(tzinfo=None)
        db.session.commit()

    success = _login(client, email, "StrongPass123")
    assert success.status_code == 200
    tokens = success.get_json()["tokens"]

    revoke = client.post(f"/api/users/{user_id}/revoke-sessions", headers=_headers())
    assert revoke.status_code == 200
    assert revoke.get_json()["revoked_user_id"] == user_id

    denied_access = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert denied_access.status_code == 401

    denied_refresh = client.post("/api/auth/refresh", headers={"Authorization": f"Bearer {tokens['refresh_token']}"})
    assert denied_refresh.status_code == 401


def test_browser_session_is_invalidated_after_admin_revoke(client, app_fixture):
    email = f"browser-revoke-{uuid.uuid4().hex[:8]}@example.com"
    user_id = _register_user(client, email)

    with app_fixture.app_context():
        tenant = _default_tenant()
        user = User.query.filter_by(organization_id=tenant.id, id=user_id).first()
        assert user is not None
        auth_version = int(user.auth_token_version or 1)

    with client.session_transaction() as sess:
        sess[WEB_SESSION_USER_ID_KEY] = user_id
        sess[WEB_SESSION_TENANT_SLUG_KEY] = "default"
        sess[WEB_SESSION_AUTH_VERSION_KEY] = auth_version
        sess[WEB_SESSION_STARTED_AT_KEY] = int(datetime.now(UTC).timestamp())
        sess["_permanent"] = True

    revoke = client.post(f"/api/users/{user_id}/revoke-sessions", headers=_headers())
    assert revoke.status_code == 200

    response = client.get("/")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
