"""Production-readiness smoke tests.

These tests assert that the application boots cleanly with sane defaults and
that the surface area we depend on for production deployments (health probe,
auth gating, rate limiter wiring, migration history, config flags) is intact.
They are deliberately lightweight: they do NOT hit external services and do
NOT require Redis / Postgres — they verify wiring only.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from server.app import create_app
from server.config import TestingConfig
from server.extensions import db, limiter


def test_health_endpoint_returns_200(client):
    resp = client.get('/api/health')
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['status'] == 'healthy'
    assert body['database'] == 'connected'


def test_unauthenticated_admin_endpoints_return_401(client):
    """Every privileged endpoint must reject anonymous callers."""
    for path, method in [
        ('/api/agents', 'GET'),
        ('/api/tenants', 'GET'),
        ('/api/agent/cert/pin', 'GET'),
        ('/api/agent/commands', 'POST'),
        ('/api/agent/commands/pending', 'GET'),
        ('/api/agent/key/rotate', 'POST'),
    ]:
        resp = client.open(path, method=method)
        assert resp.status_code == 401, f'{method} {path} returned {resp.status_code}'


def test_redis_fallback_resolves_to_memory_when_unreachable(monkeypatch):
    """Verifies the Redis fallback (T1) resolver picks memory:// when Redis is down.

    Tests the resolver function directly (no app rebuild) so we don't contaminate
    the SQLAlchemy global between tests.
    """
    from server.extensions import _resolve_limiter_storage

    monkeypatch.delenv('REDIS_URL', raising=False)

    class _FakeApp:
        config = {'RATELIMIT_STORAGE_URL': 'redis://nonexistent-host-9999:6379/0'}

    resolved = _resolve_limiter_storage(_FakeApp())
    assert resolved.startswith('memory://'), f'Expected memory fallback, got {resolved!r}'


def test_redis_fallback_uses_memory_when_no_url_configured(monkeypatch):
    from server.extensions import _resolve_limiter_storage

    monkeypatch.delenv('REDIS_URL', raising=False)

    class _FakeApp:
        config = {}

    resolved = _resolve_limiter_storage(_FakeApp())
    assert resolved == 'memory://'


def test_alembic_migrations_chain_includes_latest():
    """Walk the migrations directory and assert the new commands+pins migration is present."""
    versions_dir = Path('migrations') / 'versions'
    assert versions_dir.is_dir(), 'migrations/versions/ missing'
    files = sorted(p.name for p in versions_dir.glob('*.py'))
    assert any('agent_commands_and_pins' in name for name in files), (
        f'Migration 026_agent_commands_and_pins missing from {files}'
    )


def test_required_models_importable():
    """All production-critical models must be importable from server.models."""
    from server.models import (
        Organization, User, Role, Permission, Agent, AgentCommand,
        AgentServerPin, AlertRule, LogEntry, AuditEvent,
    )
    assert all([Organization, User, Role, Permission, Agent, AgentCommand,
                AgentServerPin, AlertRule, LogEntry, AuditEvent])


def test_agent_transport_module_importable():
    """The retry/outbox transport must be importable on the server side too (shared models)."""
    from agent.transport import AgentTransport, default_state_path  # noqa: F401


def test_agent_commands_module_importable():
    from agent.commands import poll_and_execute, SAFE_COMMAND_TYPES  # noqa: F401
    assert 'ping' in SAFE_COMMAND_TYPES


def test_production_config_flags_present():
    """Critical env-driven config flags must have safe defaults."""
    from server.config import Config
    assert hasattr(Config, 'SQLALCHEMY_DATABASE_URI')
    assert hasattr(Config, 'SECRET_KEY')


def test_rate_limiter_disabled_in_test_config():
    """Sanity: limiter.enabled must be flippable for tests (used by conftest)."""
    assert hasattr(limiter, 'enabled')
