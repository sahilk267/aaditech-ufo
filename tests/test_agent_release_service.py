from pathlib import Path

from server.services.agent_release_service import AgentReleaseService


class _UploadFileDouble:
    def __init__(self, source_file: Path):
        self.filename = source_file.name
        self._source_file = source_file

    def save(self, target_path):
        Path(target_path).write_bytes(self._source_file.read_bytes())


def test_register_release_file_copies_versioned_exe(tmp_path):
    instance_dir = tmp_path / 'instance'
    instance_dir.mkdir(parents=True)

    source_exe = tmp_path / 'agent.exe'
    source_exe.write_bytes(b'fake-binary')

    release = AgentReleaseService.register_release_file(
        source_path=str(source_exe),
        version='1.2.3',
        config={'AGENT_RELEASES_DIR': 'agent_releases'},
        instance_path=str(instance_dir),
    )

    assert release.version == '1.2.3'
    assert release.filename == 'aaditech-agent-1.2.3.exe'

    target = instance_dir / 'agent_releases' / 'aaditech-agent-1.2.3.exe'
    assert target.exists()
    assert target.read_bytes() == b'fake-binary'


def test_list_releases_returns_sorted_versioned_exe_files(tmp_path):
    instance_dir = tmp_path / 'instance'
    release_dir = instance_dir / 'agent_releases'
    release_dir.mkdir(parents=True)

    (release_dir / 'aaditech-agent-1.0.0.exe').write_bytes(b'v1')
    (release_dir / 'aaditech-agent-1.1.0.exe').write_bytes(b'v2')
    (release_dir / 'ignore.txt').write_text('x')

    releases = AgentReleaseService.list_releases(
        config={'AGENT_RELEASES_DIR': 'agent_releases'},
        instance_path=str(instance_dir),
    )

    assert len(releases) == 2
    assert {r.version for r in releases} == {'1.0.0', '1.1.0'}


def test_save_uploaded_release_validates_exe_and_version(tmp_path):
    instance_dir = tmp_path / 'instance'
    instance_dir.mkdir(parents=True)

    source_exe = tmp_path / 'upload.exe'
    source_exe.write_bytes(b'upload-binary')
    upload = _UploadFileDouble(source_exe)

    release = AgentReleaseService.save_uploaded_release(
        uploaded_file=upload,
        version='2.0.0',
        config={'AGENT_RELEASES_DIR': 'agent_releases'},
        instance_path=str(instance_dir),
    )

    assert release.filename == 'aaditech-agent-2.0.0.exe'
    target = instance_dir / 'agent_releases' / 'aaditech-agent-2.0.0.exe'
    assert target.exists()
