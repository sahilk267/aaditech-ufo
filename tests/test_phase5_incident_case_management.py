"""Tests for Phase 5 incident case-management v1."""

from __future__ import annotations

from server.auth import get_api_key
from server.extensions import db
from server.models import IncidentRecord, Organization
from server.tenant_context import get_or_create_default_tenant


def _headers(tenant_slug: str = 'default') -> dict[str, str]:
    return {'X-API-Key': get_api_key(), 'X-Tenant-Slug': tenant_slug}


def _default_tenant() -> Organization:
    return Organization.query.filter_by(slug='default').first() or get_or_create_default_tenant()


def test_incident_case_comment_create_and_list(client, db_session, app_fixture):
    with app_fixture.app_context():
        tenant = _default_tenant()
        incident = IncidentRecord(
            organization_id=tenant.id,
            fingerprint='case-mgmt-incident',
            hostname='srv-case',
            title='Case management incident',
            severity='critical',
            status='open',
        )
        db_session.add(incident)
        db_session.commit()
        incident_id = incident.id

    created = client.post(
        f'/api/incidents/{incident_id}/comments',
        headers=_headers(),
        json={'body': 'Investigated host and confirmed the alert correlates with a transient CPU spike.', 'comment_type': 'note'},
    )
    assert created.status_code == 201
    assert created.get_json()['comment']['incident_id'] == incident_id

    listed = client.get(f'/api/incidents/{incident_id}/comments', headers=_headers())
    assert listed.status_code == 200
    payload = listed.get_json()
    assert payload['count'] == 1
    assert payload['comments'][0]['body'].startswith('Investigated host')
