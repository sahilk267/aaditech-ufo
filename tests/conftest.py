"""
Pytest configuration and fixtures
Shared test setup and fixtures for all tests.
"""

import os
import tempfile

import pytest

from server.app import create_app
from server.config import TestingConfig
from server.extensions import db, limiter


@pytest.fixture
def app_fixture():
    """Create application for testing."""
    fd, db_path = tempfile.mkstemp(prefix='aaditech_ufo_test_', suffix='.db')
    os.close(fd)

    class TestConfig(TestingConfig):
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{db_path.replace(os.sep, '/')}"

    app = create_app(TestConfig)
    # Flask-Limiter captures self.enabled at init_app() time (before TestingConfig
    # is applied). Explicitly disable it now so per-route @limiter.limit() decorators
    # do not fire and cause 429 errors during the full test session.
    limiter.enabled = False

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()
        db.engine.dispose()

    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture
def client(app_fixture):
    """Create test client."""
    return app_fixture.test_client()


@pytest.fixture
def runner(app_fixture):
    """Create CLI runner for Flask commands."""
    return app_fixture.test_cli_runner()


@pytest.fixture
def db_session(app_fixture):
    """Create database session for tests."""
    with app_fixture.app_context():
        db.session.remove()
        yield db.session
        db.session.remove()
