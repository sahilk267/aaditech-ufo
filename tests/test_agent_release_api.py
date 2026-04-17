"""Tests for API-based agent release lifecycle (upload/list/guide/policy/download)."""

from io import BytesIO
from pathlib import Path

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


def test_agent_release_api_round_trip_matches_deployment_update_flow(client, app_fixture, tmp_path):
    release_dir = tmp_path / 'agent_releases'
    release_dir.mkdir(parents=True)
    app_fixture.config['AGENT_RELEASES_DIR'] = str(release_dir)

    binary_bytes = b'deployment-like-agent-binary'
    upload = client.post(
        '/api/agent/releases/upload',
        headers=_headers(),
        data={
            'version': '3.4.5',
            'release_file': (BytesIO(binary_bytes), 'agent.exe'),
        },
        content_type='multipart/form-data',
    )
    assert upload.status_code == 201

    stored_file = release_dir / 'aaditech-agent-3.4.5.exe'
    assert stored_file.exists()
    assert stored_file.read_bytes() == binary_bytes

    listing = client.get('/api/agent/releases', headers=_headers())
    assert listing.status_code == 200
    list_payload = listing.get_json()
    assert list_payload['count'] == 1
    release = list_payload['releases'][0]
    assert release['filename'] == 'aaditech-agent-3.4.5.exe'
    assert release['download_url'].endswith('/api/agent/releases/download/aaditech-agent-3.4.5.exe')

    guide = client.get('/api/agent/releases/guide?current_version=3.0.0', headers=_headers())
    assert guide.status_code == 200
    guide_payload = guide.get_json()['guide']
    assert guide_payload['recommended_version'] == '3.4.5'
    assert guide_payload['action'] == 'upgrade'
    assert guide_payload['recommended_download_url'].endswith('/api/agent/releases/download/aaditech-agent-3.4.5.exe')

    download = client.get('/api/agent/releases/download/aaditech-agent-3.4.5.exe', headers={'X-API-Key': get_api_key()})
    assert download.status_code == 200
    assert download.data == binary_bytes
    assert 'attachment' in (download.headers.get('Content-Disposition') or '').lower()
    assert 'aaditech-agent-3.4.5.exe' in (download.headers.get('Content-Disposition') or '')


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


def test_agent_build_status_includes_artifact_metadata(client, app_fixture, tmp_path):
    agent_dist_dir = Path(app_fixture.root_path).resolve().parent / 'agent' / 'dist'
    agent_dist_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = agent_dist_dir / 'aaditech-agent.exe'
    artifact_path.write_bytes(b'fake-agent-binary')

    status = client.get('/api/agent/build/status', headers=_headers())
    assert status.status_code == 200
    payload = status.get_json()
    assert payload['status'] == 'success'
    assert payload['build']['binary_available'] is True
    assert payload['build']['binary_name'] == 'aaditech-agent.exe'
    assert payload['build']['runtime_platform'] in {'linux', 'darwin', 'windows', 'unknown'}
    assert payload['build']['artifact_kind'] == 'windows_executable'
    assert payload['build']['artifact_extension'] == '.exe'


def test_agent_build_api_includes_artifact_metadata(client, app_fixture, tmp_path, monkeypatch):
    artifact_path = tmp_path / 'agent' / 'dist' / 'aaditech-agent.exe'
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_bytes(b'fake-agent-binary')

    def fake_build(root_path, timeout_seconds=180):
        return {
            'success': True,
            'returncode': 0,
            'binary_available': True,
            'binary_path': str(artifact_path),
            'stdout_tail': '',
            'stderr_tail': '',
        }

    monkeypatch.setattr('server.blueprints.api.AgentReleaseService.build_agent_binary', fake_build)
    monkeypatch.setattr('server.blueprints.api.AgentReleaseService.resolve_built_binary_path', lambda root_path: artifact_path)

    response = client.post('/api/agent/build', headers=_headers())
    assert response.status_code == 200
    payload = response.get_json()
    assert payload['status'] == 'success'
    assert payload['build']['binary_available'] is True
    assert payload['build']['binary_path'] == str(artifact_path)
    assert payload['build']['artifact_kind'] == 'windows_executable'
    assert payload['build']['artifact_extension'] == '.exe'
    assert payload['build']['runtime_platform'] in {'linux', 'darwin', 'windows', 'unknown'}
