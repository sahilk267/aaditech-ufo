"""Tests for TLS pin storage + API key rotation endpoints (T6)."""

from __future__ import annotations

from server.auth import get_api_key
from server.extensions import db
from server.models import AgentServerPin


def _h():
    return {'X-API-Key': get_api_key()}


SAMPLE_SHA = 'a' * 64


def test_get_pin_when_none_returns_null(client):
    resp = client.get('/api/agent/cert/pin', headers=_h())
    assert resp.status_code == 200
    assert resp.get_json() == {'pin': None}


def test_set_pin_rejects_short_sha(client):
    resp = client.put('/api/agent/cert/pin', headers=_h(), json={'cert_sha256': 'short'})
    assert resp.status_code == 400


def test_set_pin_rejects_non_hex(client):
    bad = 'g' * 64
    resp = client.put('/api/agent/cert/pin', headers=_h(), json={'cert_sha256': bad})
    assert resp.status_code == 400


def test_set_pin_accepts_colon_separated_form(client):
    sha_with_colons = ':'.join(SAMPLE_SHA[i:i+2] for i in range(0, 64, 2))
    resp = client.put('/api/agent/cert/pin', headers=_h(), json={'cert_sha256': sha_with_colons, 'label': 'prod'})
    assert resp.status_code == 200
    pin = resp.get_json()['pin']
    assert pin['cert_sha256'] == SAMPLE_SHA
    assert pin['is_active'] is True
    assert pin['label'] == 'prod'


def test_pin_rotation_deactivates_previous(client, app_fixture):
    client.put('/api/agent/cert/pin', headers=_h(), json={'cert_sha256': 'a' * 64})
    client.put('/api/agent/cert/pin', headers=_h(), json={'cert_sha256': 'b' * 64})

    with app_fixture.app_context():
        active = AgentServerPin.query.filter_by(is_active=True).all()
        assert len(active) == 1
        assert active[0].cert_sha256 == 'b' * 64
        rotated = AgentServerPin.query.filter_by(is_active=False).all()
        assert len(rotated) == 1
        assert rotated[0].cert_sha256 == 'a' * 64
        assert rotated[0].rotated_at is not None


def test_get_pin_returns_active_after_set(client):
    client.put('/api/agent/cert/pin', headers=_h(), json={'cert_sha256': SAMPLE_SHA})
    resp = client.get('/api/agent/cert/pin', headers=_h())
    assert resp.status_code == 200
    pin = resp.get_json()['pin']
    assert pin is not None
    assert pin['cert_sha256'] == SAMPLE_SHA


def test_key_rotation_returns_new_key_and_grace_window(client):
    resp = client.post('/api/agent/key/rotate', headers=_h(), json={'grace_seconds': 600})
    assert resp.status_code == 200
    body = resp.get_json()
    assert 'new_api_key' in body
    assert len(body['new_api_key']) >= 32
    assert body['grace_seconds'] == 600
    assert 'rotated_at' in body


def test_key_rotation_clamps_negative_grace(client):
    resp = client.post('/api/agent/key/rotate', headers=_h(), json={'grace_seconds': -1})
    assert resp.status_code == 200
    assert resp.get_json()['grace_seconds'] == 0


def test_key_rotation_default_grace_seconds(client):
    resp = client.post('/api/agent/key/rotate', headers=_h(), json={})
    assert resp.status_code == 200
    assert resp.get_json()['grace_seconds'] == 300


def test_pin_endpoints_require_auth(client):
    assert client.get('/api/agent/cert/pin').status_code == 401
    assert client.put('/api/agent/cert/pin', json={'cert_sha256': SAMPLE_SHA}).status_code == 401
    assert client.post('/api/agent/key/rotate').status_code == 401
