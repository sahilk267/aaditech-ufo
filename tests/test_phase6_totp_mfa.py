"""Tests for Phase 6 TOTP MFA foundation and login challenge flow."""

from __future__ import annotations

import base64
import hashlib
import hmac
from datetime import UTC, datetime

from server.auth import get_api_key
from server.models import UserTotpFactor


def _headers(tenant_slug: str = "default") -> dict[str, str]:
    return {"X-API-Key": get_api_key(), "X-Tenant-Slug": tenant_slug}


def _current_totp_code(secret: str, period: int = 30) -> str:
    normalized = str(secret).strip().replace(" ", "").upper()
    padding = "=" * ((8 - len(normalized) % 8) % 8)
    secret_bytes = base64.b32decode(normalized + padding, casefold=True)
    counter = int(datetime.now(UTC).timestamp() // period)
    digest = hmac.new(secret_bytes, counter.to_bytes(8, "big"), hashlib.sha1).digest()
    pos = digest[-1] & 0x0F
    binary = ((digest[pos] & 0x7F) << 24) | (digest[pos + 1] << 16) | (digest[pos + 2] << 8) | digest[pos + 3]
    return str(binary % 1_000_000).zfill(6)


def _register_user(client, email: str, password: str = "StrongPass123"):
    response = client.post(
        "/api/auth/register",
        headers=_headers(),
        json={"email": email, "full_name": "MFA User", "password": password},
    )
    assert response.status_code == 201
    return response.get_json()["user"]["id"]


def _login(client, email: str, password: str = "StrongPass123"):
    return client.post(
        "/api/auth/login",
        headers={"X-Tenant-Slug": "default"},
        json={"email": email, "password": password},
    )


def test_totp_enrollment_activation_and_mfa_login(client, app_fixture):
    email = "mfa-user@example.com"
    user_id = _register_user(client, email)

    login_response = _login(client, email)
    assert login_response.status_code == 200
    tokens = login_response.get_json()["tokens"]
    access_headers = {"Authorization": f"Bearer {tokens['access_token']}", "X-Tenant-Slug": "default"}

    enroll = client.post("/api/auth/mfa/totp/enroll", headers=access_headers)
    assert enroll.status_code == 200
    enroll_payload = enroll.get_json()["totp"]
    assert enroll_payload["status"] == "pending"
    assert enroll_payload["secret"]
    assert "otpauth://totp/" in enroll_payload["provisioning_uri"]

    code = _current_totp_code(enroll_payload["secret"])
    activate = client.post("/api/auth/mfa/totp/activate", headers=access_headers, json={"code": code})
    assert activate.status_code == 200
    assert activate.get_json()["totp"]["enabled"] is True

    policy_update = client.patch(
        "/api/tenant-settings",
        headers=_headers(),
        json={"auth_policy": {"totp_mfa_enabled": True}},
    )
    assert policy_update.status_code == 200

    challenge_login = _login(client, email)
    assert challenge_login.status_code == 202
    challenge_payload = challenge_login.get_json()
    assert challenge_payload["status"] == "mfa_required"
    challenge_token = challenge_payload["challenge"]["challenge_token"]

    verify = client.post(
        "/api/auth/mfa/totp/verify-login",
        headers={"X-Tenant-Slug": "default"},
        json={"challenge_token": challenge_token, "code": _current_totp_code(enroll_payload["secret"])},
    )
    assert verify.status_code == 200
    verified_tokens = verify.get_json()["tokens"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {verified_tokens['access_token']}"})
    assert me.status_code == 200
    assert me.get_json()["user"]["mfa"]["totp_enabled"] is True

    disable = client.post(
        "/api/auth/mfa/totp/disable",
        headers={"Authorization": f"Bearer {verified_tokens['access_token']}", "X-Tenant-Slug": "default"},
        json={"current_password": "StrongPass123"},
    )
    assert disable.status_code == 200
    assert disable.get_json()["totp"]["enabled"] is False

    with app_fixture.app_context():
        factor = UserTotpFactor.query.filter_by(user_id=user_id).first()
        assert factor is not None
        assert factor.status == "disabled"

    login_after_disable = _login(client, email)
    assert login_after_disable.status_code == 200


def test_verify_login_rejects_invalid_totp_code(client):
    email = "mfa-user-invalid@example.com"
    _register_user(client, email)
    login_response = _login(client, email)
    tokens = login_response.get_json()["tokens"]
    access_headers = {"Authorization": f"Bearer {tokens['access_token']}", "X-Tenant-Slug": "default"}

    enroll = client.post("/api/auth/mfa/totp/enroll", headers=access_headers)
    secret = enroll.get_json()["totp"]["secret"]
    activate = client.post("/api/auth/mfa/totp/activate", headers=access_headers, json={"code": _current_totp_code(secret)})
    assert activate.status_code == 200
    policy_update = client.patch(
        "/api/tenant-settings",
        headers=_headers(),
        json={"auth_policy": {"totp_mfa_enabled": True}},
    )
    assert policy_update.status_code == 200

    challenge_login = _login(client, email)
    challenge_token = challenge_login.get_json()["challenge"]["challenge_token"]

    denied = client.post(
        "/api/auth/mfa/totp/verify-login",
        headers={"X-Tenant-Slug": "default"},
        json={"challenge_token": challenge_token, "code": "000000"},
    )
    assert denied.status_code == 401
