"""Tests for multi-tenant request context and tenant data isolation."""

from datetime import datetime, UTC

from server.auth import get_api_key
from server.extensions import db
from server.models import Organization, SystemData


def _valid_payload(serial_number: str, hostname: str):
    return {
        'serial_number': serial_number,
        'hostname': hostname,
        'last_update': datetime.now(UTC).isoformat(),
        'status': 'active',
        'cpu_usage': 10.0,
    }


def test_default_tenant_is_created_on_request(client, app_fixture):
    response = client.get('/api/health')
    assert response.status_code == 200

    with app_fixture.app_context():
        tenant = Organization.query.filter_by(slug='default').first()
        assert tenant is not None
        assert tenant.is_active is True


def test_submit_data_attaches_current_tenant(client, app_fixture):
    with app_fixture.app_context():
        tenant = Organization(name='Acme Inc', slug='acme', is_active=True)
        db.session.add(tenant)
        db.session.commit()
        tenant_id = tenant.id

    response = client.post(
        '/api/submit_data',
        headers={
            'X-API-Key': get_api_key(),
            'X-Tenant-Slug': 'acme',
        },
        json=_valid_payload('TENANT-SN-001', 'tenant-host-1'),
    )
    assert response.status_code == 200

    with app_fixture.app_context():
        row = SystemData.query.filter_by(serial_number='TENANT-SN-001').first()
        assert row is not None
        assert row.organization_id == tenant_id


def test_system_list_is_tenant_scoped(client, app_fixture):
    with app_fixture.app_context():
        org_a = Organization(name='Tenant A', slug='tenant-a', is_active=True)
        org_b = Organization(name='Tenant B', slug='tenant-b', is_active=True)
        db.session.add(org_a)
        db.session.add(org_b)
        db.session.commit()

        db.session.add(SystemData(serial_number='A-1', hostname='a-host', organization_id=org_a.id))
        db.session.add(SystemData(serial_number='B-1', hostname='b-host', organization_id=org_b.id))
        db.session.commit()

    response_a = client.get('/api/systems', headers={'X-Tenant-Slug': 'tenant-a'})
    response_b = client.get('/api/systems', headers={'X-Tenant-Slug': 'tenant-b'})

    assert response_a.status_code == 200
    assert response_b.status_code == 200

    payload_a = response_a.get_json()
    payload_b = response_b.get_json()

    assert payload_a['count'] == 1
    assert payload_a['systems'][0]['serial_number'] == 'A-1'
    assert payload_b['count'] == 1
    assert payload_b['systems'][0]['serial_number'] == 'B-1'
