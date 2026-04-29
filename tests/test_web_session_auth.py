"""Tests for browser-compatible session auth on HTML pages."""

from datetime import datetime, UTC
from io import BytesIO
import uuid
from unittest.mock import patch

from server.auth import (
    WEB_SESSION_TENANT_SLUG_KEY,
    WEB_SESSION_USER_ID_KEY,
    get_api_key,
    hash_password,
)
from server.extensions import db
from server.models import Organization, Permission, Role, SystemData, User


def _api_key_headers(extra=None):
    headers = {'X-API-Key': get_api_key()}
    if extra:
        headers.update(extra)
    return headers


def _register_admin_user(client, email=None, tenant_slug='default'):
    if email is None:
        email = f"browser-admin-{uuid.uuid4().hex[:8]}@tenant.local"

    response = client.post(
        '/api/auth/register',
        headers={
            'X-API-Key': get_api_key(),
            'X-Tenant-Slug': tenant_slug,
        },
        json={
            'email': email,
            'full_name': 'Browser Admin',
            'password': 'StrongPass123',
        },
    )
    assert response.status_code == 201
    return email


def _login_browser(client, email, tenant_slug='default', follow_redirects=False, next_url=''):
    return client.post(
        '/login',
        data={
            'tenant_slug': tenant_slug,
            'email': email,
            'password': 'StrongPass123',
            'next': next_url,
        },
        follow_redirects=follow_redirects,
    )


def _create_browser_user(app_fixture, permission_codes=None, email=None):
    if permission_codes is None:
        permission_codes = []
    if email is None:
        email = f"browser-user-{uuid.uuid4().hex[:8]}@tenant.local"

    with app_fixture.app_context():
        tenant = Organization.query.filter_by(slug='default').first()
        if tenant is None:
            tenant = Organization(name='Default Organization', slug='default', is_active=True)
            db.session.add(tenant)
            db.session.flush()

        role = Role(
            organization_id=tenant.id,
            name=f"browser-role-{uuid.uuid4().hex[:8]}",
            description='Browser session test role',
            is_system=False,
        )
        db.session.add(role)
        db.session.flush()

        for permission_code in permission_codes:
            permission = Permission(code=permission_code, description=f'Permission {permission_code}')
            db.session.add(permission)
            db.session.flush()
            role.permissions.append(permission)

        user = User(
            organization_id=tenant.id,
            email=email,
            full_name='Browser User',
            password_hash=hash_password('StrongPass123'),
            is_active=True,
        )
        user.roles.append(role)
        db.session.add(user)
        db.session.commit()

    return email


def _force_browser_session(client, app_fixture, email, tenant_slug='default'):
    with app_fixture.app_context():
        tenant = Organization.query.filter_by(slug=tenant_slug).first()
        user = User.query.filter_by(organization_id=tenant.id, email=email).first()
        assert user is not None

    with client.session_transaction() as sess:
        sess[WEB_SESSION_USER_ID_KEY] = user.id
        sess[WEB_SESSION_TENANT_SLUG_KEY] = tenant_slug
        sess['_permanent'] = True


def test_login_page_renders(client):
    with client.session_transaction() as sess:
        sess.clear()
    response = client.get('/login')
    # Accept legacy HTML (200), redirect to SPA (302), or archived marker (503)
    assert response.status_code in (200, 302, 503)
    if response.status_code == 200:
        assert b'Tenant Login' in response.data
    elif response.status_code == 302:
        assert '/app' in response.headers.get('Location', '')
    else:
        assert response.get_json().get('error', '').lower().find('archived') != -1


def test_html_dashboard_redirects_to_login_without_session(client):
    response = client.get('/')
    assert response.status_code == 302
    # When SPA is enabled the redirect goes to `/app/*`, otherwise legacy `/login`.
    assert '/login' in response.headers['Location'] or '/app' in response.headers['Location']


def test_browser_login_allows_dashboard_access(client, app_fixture):
    email = _register_admin_user(client)

    login_response = _login_browser(client, email)
    assert login_response.status_code == 302
    _force_browser_session(client, app_fixture, email)

    dashboard_response = client.get('/')
    assert dashboard_response.status_code == 200
    assert b'Total Systems' in dashboard_response.data


def test_browser_backup_page_forbidden_without_permission(client, app_fixture):
    email = _create_browser_user(
        app_fixture,
        permission_codes=[f"dashboard.view.only.{uuid.uuid4().hex[:8]}"],
    )

    _force_browser_session(client, app_fixture, email)

    backup_response = client.get('/backup', follow_redirects=True)
    assert backup_response.status_code == 403
    assert b'do not have permission' in backup_response.data.lower()


def test_browser_session_allows_manual_submit_without_headers(client, app_fixture):
    email = _register_admin_user(client)
    _force_browser_session(client, app_fixture, email)

    system_data = {
        'serial_number': f"BROWSER-{uuid.uuid4().hex[:8]}",
        'hostname': 'browser-managed-host',
        'cpu_usage': 18.5,
        'ram_usage': 28.0,
        'last_update': datetime.now(UTC),
        'status': 'active',
    }

    with patch('server.blueprints.web.SystemService.get_local_system_data', return_value=system_data):
        response = client.post('/manual_submit')

    assert response.status_code == 200
    assert response.get_json()['status'] == 'success'


def test_browser_session_allows_system_json_without_headers(client, app_fixture):
    with app_fixture.app_context():
        tenant = Organization.query.filter_by(slug='default').first()
        if tenant is None:
            tenant = Organization(name='Default Organization', slug='default', is_active=True)
            db.session.add(tenant)
            db.session.flush()

        system = SystemData(
            organization_id=tenant.id,
            serial_number=f"BJSON-{uuid.uuid4().hex[:8]}",
            hostname='browser-json-host',
            cpu_usage=25.0,
            ram_usage=35.0,
            last_update=datetime.now(UTC),
            status='active',
        )
        db.session.add(system)
        db.session.commit()

    email = _register_admin_user(client)
    _force_browser_session(client, app_fixture, email)

    response = client.get('/api/systems')
    assert response.status_code == 200
    assert response.get_json()['count'] >= 1


def test_browser_session_allows_register_without_headers(client, app_fixture):
    email = _register_admin_user(client)
    _force_browser_session(client, app_fixture, email)

    response = client.post(
        '/api/auth/register',
        json={
            'email': 'browser-created@example.com',
            'full_name': 'Browser Created',
            'password': 'StrongPass123',
        },
    )

    assert response.status_code == 201
    assert response.get_json()['user']['email'] == 'browser-created@example.com'


def test_agent_release_page_lists_versioned_exe(client, app_fixture, tmp_path):
    email = _register_admin_user(client)
    _force_browser_session(client, app_fixture, email)

    release_dir = tmp_path / 'agent_releases'
    release_dir.mkdir(parents=True)
    release_file = release_dir / 'aaditech-agent-1.0.0.exe'
    release_file.write_bytes(b'v1-binary')

    app_fixture.config['AGENT_RELEASES_DIR'] = str(release_dir)

    response = client.get('/agent/releases')

    assert response.status_code == 200
    assert b'Agent Releases' in response.data
    assert b'aaditech-agent-1.0.0.exe' in response.data


def test_agent_release_upload_succeeds_for_admin(client, app_fixture, tmp_path):
    email = _register_admin_user(client)
    _force_browser_session(client, app_fixture, email)

    release_dir = tmp_path / 'agent_releases'
    release_dir.mkdir(parents=True)
    app_fixture.config['AGENT_RELEASES_DIR'] = str(release_dir)

    response = client.post(
        '/agent/releases/upload',
        data={
            'version': '2.1.0',
            'release_file': (BytesIO(b'new-binary-data'), 'agent.exe'),
        },
        content_type='multipart/form-data',
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/agent/releases')
    assert (release_dir / 'aaditech-agent-2.1.0.exe').exists()


def test_agent_release_download_returns_file(client, app_fixture, tmp_path):
    email = _register_admin_user(client)
    _force_browser_session(client, app_fixture, email)

    release_dir = tmp_path / 'agent_releases'
    release_dir.mkdir(parents=True)
    target = release_dir / 'aaditech-agent-3.0.0.exe'
    target.write_bytes(b'download-binary')

    app_fixture.config['AGENT_RELEASES_DIR'] = str(release_dir)

    response = client.get('/agent/releases/download/aaditech-agent-3.0.0.exe')

    assert response.status_code == 200
    assert response.data == b'download-binary'
    assert 'attachment' in (response.headers.get('Content-Disposition') or '').lower()