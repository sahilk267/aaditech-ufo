"""Verify graceful Redis fallback for the rate limiter."""


import pytest


@pytest.fixture
def reset_extensions(monkeypatch):
    """Re-import extensions module so init runs cleanly per test."""
    monkeypatch.delenv('REDIS_URL', raising=False)
    monkeypatch.delenv('RATELIMIT_STORAGE_URL', raising=False)
    yield


def test_falls_back_to_memory_when_no_redis(reset_extensions, monkeypatch):
    from server import extensions as ext

    class FakeApp:
        def __init__(self):
            self.config = {}
            self.extensions = {}

    app = FakeApp()
    storage = ext._resolve_limiter_storage(app)
    assert storage == 'memory://'


def test_uses_redis_when_reachable(reset_extensions, monkeypatch):
    from server import extensions as ext

    monkeypatch.setattr(ext, '_ping_redis', lambda url, timeout=1.0: True)

    class FakeApp:
        def __init__(self):
            self.config = {'REDIS_URL': 'redis://example.com:6379/0'}
            self.extensions = {}

    app = FakeApp()
    storage = ext._resolve_limiter_storage(app)
    assert storage == 'redis://example.com:6379/0'


def test_falls_back_when_redis_unreachable(reset_extensions, monkeypatch):
    from server import extensions as ext

    monkeypatch.setattr(ext, '_ping_redis', lambda url, timeout=1.0: False)

    class FakeApp:
        def __init__(self):
            self.config = {'REDIS_URL': 'redis://unreachable.example:6379/0'}
            self.extensions = {}

    app = FakeApp()
    storage = ext._resolve_limiter_storage(app)
    assert storage == 'memory://'


def test_explicit_override_wins(reset_extensions, monkeypatch):
    from server import extensions as ext

    monkeypatch.setattr(ext, '_ping_redis', lambda url, timeout=1.0: False)

    class FakeApp:
        def __init__(self):
            self.config = {'RATELIMIT_STORAGE_URL': 'memory://', 'REDIS_URL': 'redis://elsewhere/0'}
            self.extensions = {}

    app = FakeApp()
    storage = ext._resolve_limiter_storage(app)
    assert storage == 'memory://'


def test_safe_url_strips_credentials():
    from server.extensions import _safe_url
    assert _safe_url('redis://:secret@example.com:6379/0') == 'redis://***@example.com:6379/0'
    assert _safe_url('redis://example.com:6379/0') == 'redis://example.com:6379/0'
    assert _safe_url('memory://') == 'memory://'


# NOTE: full-app boot smoke (without Redis) is covered indirectly by the
# `client` fixture in conftest.py, which always boots create_app() during the
# test session. The resolver-level fallback path is covered above by
# `test_falls_back_to_memory_when_no_redis` and `test_falls_back_when_redis_unreachable`.
# A second create_app() call inside this module poisoned the SQLAlchemy global
# state for downstream fixture-based tests; it is intentionally not present.
