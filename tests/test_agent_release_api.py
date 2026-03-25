"""Tests for API-based agent release lifecycle (upload/list/guide/policy/download)."""

from io import BytesIO

from server.auth import get_api_key


def _headers() -> dict[str, str]:
    return {
        'X-API-Key': get_api_key(),
        'X-Tenant-Slug': 'default',
    }


def test_agent_release_upload_and_list_via_api(client, app_fixture, tmp_path):
    release_dir = tmp_path / 'agent_releases'
    release_dir.mkdir(parents=True)
    app_fixture.config['AGENT_RELEASES_DIR'] = str(release_dir)

    upload = client.post(
        '/api/agent/releases/upload',
        headers=_headers(),
        data={
            'version': '1.2.3',
            'release_file': (BytesIO(b'binary-123'), 'aaditech-agent.exe'),
        },
        content_type='multipart/form-data',
    )
    assert upload.status_code == 201

    payload = upload.get_json()
    assert payload['status'] == 'success'
    assert payload['release']['version'] == '1.2.3'

    listing = client.get('/api/agent/releases', headers=_headers())
    assert listing.status_code == 200
    list_payload = listing.get_json()
    assert list_payload['count'] == 1
    assert list_payload['releases'][0]['version'] == '1.2.3'
    assert '/api/agent/releases/download/' in list_payload['releases'][0]['download_url']


def test_agent_release_guide_supports_server_side_downgrade_target(client, app_fixture, tmp_path):
    release_dir = tmp_path / 'agent_releases'
    release_dir.mkdir(parents=True)
    app_fixture.config['AGENT_RELEASES_DIR'] = str(release_dir)

    for version in ('1.0.0', '1.1.0', '2.0.0'):
        response = client.post(
            '/api/agent/releases/upload',
            headers=_headers(),
            data={
                'version': version,
                'release_file': (BytesIO(f'binary-{version}'.encode('utf-8')), 'agent.exe'),
            },
            content_type='multipart/form-data',
        )
        assert response.status_code == 201

    policy = client.put(
        '/api/agent/releases/policy',
        headers=_headers(),
        json={
            'target_version': '1.1.0',
            'notes': 'Rollback to stable build',
        },
    )
    assert policy.status_code == 200

    guide = client.get('/api/agent/releases/guide?current_version=2.0.0', headers=_headers())
    assert guide.status_code == 200
    guide_payload = guide.get_json()['guide']

    assert guide_payload['recommended_version'] == '1.1.0'
    assert guide_payload['action'] == 'downgrade'
    assert len(guide_payload['downgrade_candidates']) >= 1
    assert guide_payload['recommended_download_url'] is not None


def test_agent_release_policy_rejects_unknown_target_version(client, app_fixture, tmp_path):
    release_dir = tmp_path / 'agent_releases'
    release_dir.mkdir(parents=True)
    app_fixture.config['AGENT_RELEASES_DIR'] = str(release_dir)

    response = client.put(
        '/api/agent/releases/policy',
        headers=_headers(),
        json={'target_version': '9.9.9'},
    )

    assert response.status_code == 400
    payload = response.get_json()
    assert payload['error'] == 'Validation failed'
