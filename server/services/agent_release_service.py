"""Agent release management service.

Supports server-side storage of versioned Windows agent artifacts and
portal/API-friendly listing + download access.
"""

from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from werkzeug.utils import secure_filename


@dataclass
class AgentRelease:
    filename: str
    version: str
    size_bytes: int
    modified_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            'filename': self.filename,
            'version': self.version,
            'size_bytes': self.size_bytes,
            'modified_at': self.modified_at,
        }


class AgentReleaseService:
    """Manage release artifact directory and metadata extraction."""

    RELEASE_PATTERN = re.compile(r'^aaditech-agent-([A-Za-z0-9._-]+)\.exe$')

    @classmethod
    def _resolve_release_dir(cls, config: dict[str, Any], instance_path: str) -> Path:
        configured = str(config.get('AGENT_RELEASES_DIR', '')).strip()
        if not configured:
            return Path(instance_path) / 'agent_releases'

        path = Path(configured)
        if path.is_absolute():
            return path
        return Path(instance_path) / path

    @classmethod
    def ensure_release_dir(cls, config: dict[str, Any], instance_path: str) -> Path:
        release_dir = cls._resolve_release_dir(config, instance_path)
        release_dir.mkdir(parents=True, exist_ok=True)
        return release_dir

    @classmethod
    def _extract_version(cls, filename: str) -> str:
        match = cls.RELEASE_PATTERN.match(filename)
        if match:
            return match.group(1)
        return 'unknown'

    @classmethod
    def list_releases(cls, config: dict[str, Any], instance_path: str) -> list[AgentRelease]:
        release_dir = cls.ensure_release_dir(config, instance_path)
        releases: list[AgentRelease] = []
        for item in release_dir.iterdir():
            if not item.is_file():
                continue
            if item.suffix.lower() != '.exe':
                continue

            stat = item.stat()
            releases.append(
                AgentRelease(
                    filename=item.name,
                    version=cls._extract_version(item.name),
                    size_bytes=int(stat.st_size),
                    modified_at=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                )
            )

        releases.sort(key=lambda rel: rel.modified_at, reverse=True)
        return releases

    @classmethod
    def save_uploaded_release(
        cls,
        uploaded_file,
        version: str,
        config: dict[str, Any],
        instance_path: str,
    ) -> AgentRelease:
        release_dir = cls.ensure_release_dir(config, instance_path)

        version = str(version or '').strip()
        if not version:
            raise ValueError('version_required')
        if not re.fullmatch(r'[A-Za-z0-9._-]{1,64}', version):
            raise ValueError('version_invalid')

        original_name = secure_filename(uploaded_file.filename or '')
        if not original_name.lower().endswith('.exe'):
            raise ValueError('only_exe_allowed')

        target_name = f'aaditech-agent-{version}.exe'
        target_path = release_dir / target_name
        uploaded_file.save(target_path)

        stat = target_path.stat()
        return AgentRelease(
            filename=target_name,
            version=version,
            size_bytes=int(stat.st_size),
            modified_at=datetime.fromtimestamp(stat.st_mtime).isoformat(),
        )

    @classmethod
    def register_release_file(
        cls,
        source_path: str,
        version: str,
        config: dict[str, Any],
        instance_path: str,
    ) -> AgentRelease:
        release_dir = cls.ensure_release_dir(config, instance_path)

        source = Path(source_path)
        if not source.exists() or not source.is_file():
            raise ValueError('source_not_found')
        if source.suffix.lower() != '.exe':
            raise ValueError('source_not_exe')

        version = str(version or '').strip()
        if not version or not re.fullmatch(r'[A-Za-z0-9._-]{1,64}', version):
            raise ValueError('version_invalid')

        target_name = f'aaditech-agent-{version}.exe'
        target_path = release_dir / target_name
        shutil.copyfile(source, target_path)

        stat = target_path.stat()
        return AgentRelease(
            filename=target_name,
            version=version,
            size_bytes=int(stat.st_size),
            modified_at=datetime.fromtimestamp(stat.st_mtime).isoformat(),
        )

    @classmethod
    def resolve_download_path(
        cls,
        filename: str,
        config: dict[str, Any],
        instance_path: str,
    ) -> Path | None:
        release_dir = cls.ensure_release_dir(config, instance_path)
        safe_name = secure_filename(filename or '')
        if not safe_name or os.path.sep in safe_name or safe_name.startswith('.'):
            return None

        file_path = release_dir / safe_name
        if not file_path.exists() or not file_path.is_file():
            return None
        return file_path
