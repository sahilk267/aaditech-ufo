"""Tests for tenant admin management API endpoints."""

from server.auth import get_api_key, hash_password
from server.extensions import db
from server.models import Organization, User, Role, Permission


def _auth_headers(extra=None):
    headers = {'X-API-Key': get_api_key()}
    if extra:
        headers.update(extra)
    return headers


def _register_and_login_admin(client, email='tenant-admin@example.com'):
    register = client.post(
        '/api/auth/register',
        headers=_auth_headers(),
        json={
            'email': email,
            'full_name': 'Tenant Admin',
            'password': 'StrongPass123',
        },
    )
    assert register.status_code == 201

    login = client.post(
        '/api/auth/login',
        json={'email': email, 'password': 'StrongPass123'},
    )
    assert login.status_code == 200
    return login.get_json()['tokens']['access_token']


def test_list_tenants_returns_current_tenant(client):
    response = client.get('/api/tenants', headers=_auth_headers())
    assert response.status_code == 200

    payload = response.get_json()
    assert payload['status'] == 'success'
    assert 'tenants' in payload
    assert 'current_tenant' in payload


def test_create_tenant_success(client, app_fixture):
    response = client.post(
        '/api/tenants',
        headers=_auth_headers(),
        json={'name': 'Beta Org', 'slug': 'beta-org'}
    )
    assert response.status_code == 201

    with app_fixture.app_context():
        org = Organization.query.filter_by(slug='beta-org').first()
        assert org is not None
        assert org.name == 'Beta Org'


def test_create_tenant_auto_slug(client):
    response = client.post(
        '/api/tenants',
        headers=_auth_headers(),
        json={'name': 'Gamma Team 01'}
    )
    assert response.status_code == 201
    payload = response.get_json()
    assert payload['tenant']['slug'] == 'gamma-team-01'


def test_create_tenant_duplicate_slug_conflict(client, app_fixture):
    with app_fixture.app_context():
        db.session.add(Organization(name='Delta', slug='delta', is_active=True))
        db.session.commit()

    response = client.post(
        '/api/tenants',
        headers=_auth_headers(),
        json={'name': 'Delta 2', 'slug': 'delta'}
    )
    assert response.status_code == 409


def test_update_tenant_status_success(client, app_fixture):
    with app_fixture.app_context():
        tenant = Organization(name='Inactive Co', slug='inactive-co', is_active=True)
        db.session.add(tenant)
        db.session.commit()
        tenant_id = tenant.id

    response = client.patch(
        f'/api/tenants/{tenant_id}/status',
        headers=_auth_headers(),
        json={'is_active': False}
    )
    assert response.status_code == 200

    with app_fixture.app_context():
        tenant = db.session.get(Organization, tenant_id)
        assert tenant is not None
        assert tenant.is_active is False


def test_update_default_tenant_cannot_deactivate(client, app_fixture):
    with app_fixture.app_context():
        default_tenant = Organization.query.filter_by(slug='default').first()
        if default_tenant is None:
            default_tenant = Organization(name='Default Organization', slug='default', is_active=True)
            db.session.add(default_tenant)
            db.session.commit()
        default_id = default_tenant.id

    response = client.patch(
        f'/api/tenants/{default_id}/status',
        headers=_auth_headers(),
        json={'is_active': False}
    )
    assert response.status_code == 400


def test_tenant_admin_endpoints_require_authentication(client):
    list_response = client.get('/api/tenants')
    create_response = client.post('/api/tenants', json={'name': 'No Key'})

    assert list_response.status_code == 401
    assert create_response.status_code == 401


def test_tenant_admin_endpoints_allow_jwt_with_permission(client):
    access_token = _register_and_login_admin(client)

    response = client.get('/api/tenants', headers={'Authorization': f'Bearer {access_token}'})
    assert response.status_code == 200


def test_tenant_admin_jwt_rebinds_current_tenant_to_authenticated_user(client, app_fixture):
    with app_fixture.app_context():
        beta = Organization(name='Beta Tenant', slug='beta-tenant', is_active=True)
        db.session.add(beta)
        db.session.flush()

        role = Role(
            organization_id=beta.id,
            name='beta-admin',
            description='Tenant admin for beta tenant',
            is_system=False,
        )
        db.session.add(role)
        db.session.flush()

        permission = Permission(code='tenant.manage.beta-test', description='Manage beta tenant settings')
        db.session.add(permission)
        db.session.flush()
        role.permissions.append(permission)

        canonical_permission = Permission.query.filter_by(code='tenant.manage').first()
        if canonical_permission is None:
            canonical_permission = Permission(code='tenant.manage', description='Manage tenant settings and users')
            db.session.add(canonical_permission)
            db.session.flush()
        role.permissions.append(canonical_permission)

        user = User(
            organization_id=beta.id,
            email='beta-admin@example.com',
            full_name='Beta Admin',
            password_hash=hash_password('StrongPass123'),
            is_active=True,
        )
        user.roles.append(role)
        db.session.add(user)
        db.session.commit()

    login = client.post(
        '/api/auth/login',
        headers={'X-Tenant-Slug': 'beta-tenant'},
        json={'email': 'beta-admin@example.com', 'password': 'StrongPass123'},
    )
    assert login.status_code == 200
    access_token = login.get_json()['tokens']['access_token']

    response = client.get('/api/tenants', headers={'Authorization': f'Bearer {access_token}'})
    assert response.status_code == 200

    payload = response.get_json()
    assert payload['current_tenant']['slug'] == 'beta-tenant'


def test_register_endpoint_allows_jwt_with_permission(client):
    access_token = _register_and_login_admin(client, email='bootstrap-admin@example.com')

    response = client.post(
        '/api/auth/register',
        headers={'Authorization': f'Bearer {access_token}'},
        json={
            'email': 'created-by-jwt@example.com',
            'full_name': 'Created By JWT',
            'password': 'StrongPass123',
        },
    )

    assert response.status_code == 201
    payload = response.get_json()
    assert payload['user']['email'] == 'created-by-jwt@example.com'


def test_tenant_admin_endpoints_forbid_jwt_without_permission(client, app_fixture):
    with app_fixture.app_context():
        tenant = Organization.query.filter_by(slug='default').first()
        if tenant is None:
            tenant = Organization(name='Default Organization', slug='default', is_active=True)
            db.session.add(tenant)
            db.session.flush()

        role = Role(
            organization_id=tenant.id,
            name='viewer',
            description='Read-only role',
            is_system=False,
        )
        db.session.add(role)
        db.session.flush()

        permission = Permission(code='dashboard.readonly', description='Read-only dashboard access')
        db.session.add(permission)
        db.session.flush()

        role.permissions.append(permission)

        user = User(
            organization_id=tenant.id,
            email='viewer@example.com',
            full_name='Viewer User',
            password_hash=hash_password('StrongPass123'),
            is_active=True,
        )
        user.roles.append(role)
        db.session.add(user)
        db.session.commit()

    login = client.post(
        '/api/auth/login',
        json={'email': 'viewer@example.com', 'password': 'StrongPass123'},
    )
    assert login.status_code == 200
    access_token = login.get_json()['tokens']['access_token']

    denied = client.get('/api/tenants', headers={'Authorization': f'Bearer {access_token}'})
    assert denied.status_code == 403


def test_register_endpoint_forbids_jwt_without_permission(client, app_fixture):
    with app_fixture.app_context():
        tenant = Organization.query.filter_by(slug='default').first()
        if tenant is None:
            tenant = Organization(name='Default Organization', slug='default', is_active=True)
            db.session.add(tenant)
            db.session.flush()

        role = Role(
            organization_id=tenant.id,
            name='register-viewer',
            description='Role without tenant.manage',
            is_system=False,
        )
        db.session.add(role)
        db.session.flush()

        permission = Permission(code='dashboard.readonly.register-test', description='Read-only dashboard access')
        db.session.add(permission)
        db.session.flush()
        role.permissions.append(permission)

        user = User(
            organization_id=tenant.id,
            email='register-viewer@example.com',
            full_name='Register Viewer',
            password_hash=hash_password('StrongPass123'),
            is_active=True,
        )
        user.roles.append(role)
        db.session.add(user)
        db.session.commit()

    login = client.post(
        '/api/auth/login',
        json={'email': 'register-viewer@example.com', 'password': 'StrongPass123'},
    )
    assert login.status_code == 200
    access_token = login.get_json()['tokens']['access_token']

    denied = client.post(
        '/api/auth/register',
        headers={'Authorization': f'Bearer {access_token}'},
        json={
            'email': 'blocked-register@example.com',
            'full_name': 'Blocked Register',
            'password': 'StrongPass123',
        },
    )
    assert denied.status_code == 403
