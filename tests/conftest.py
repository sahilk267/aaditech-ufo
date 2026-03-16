"""
Pytest configuration and fixtures
Shared test setup and fixtures for all tests
"""

import pytest
import os
from server.app import app
from server.extensions import db
from server.config import TestingConfig


@pytest.fixture(scope='session')
def app_fixture():
    """Create application for testing"""
    app.config.from_object(TestingConfig)
    
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app_fixture):
    """Create test client"""
    return app_fixture.test_client()


@pytest.fixture
def runner(app_fixture):
    """Create CLI runner for Flask commands"""
    return app_fixture.test_cli_runner()


@pytest.fixture
def db_session(app_fixture):
    """Create database session for tests"""
    with app_fixture.app_context():
        connection = db.engine.connect()
        transaction = connection.begin()
        session = db.session
        
        yield session
        
        session.close()
        transaction.rollback()
        connection.close()
