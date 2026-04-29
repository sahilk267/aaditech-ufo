"""Self-update logic for the Aaditech agent.

Calls the server's `/api/agent/releases/guide` endpoint, decides whether the
running version differs from the recommended one, downloads the recommended
binary, and replaces the currently-running executable atomically.

Designed to fail safe: any network, validation, or filesystem error is logged
and the agent simply keeps running on the existing version.
"""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
import stat
import sys
import tempfile
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests


logger = logging.getLogger('aaditech-agent.updater')

_SAFE_FILENAME = ('aaditech-agent-', '.exe')
_DEFAULT_DOWNLOAD_TIMEOUT = 120
_MAX_DOWNLOAD_BYTES = 512 * 1024 * 1024  # 512 MB hard cap


def _is_frozen() -> bool:
    """True when the agent is running as a PyInstaller-built executable."""
    return getattr(sys, 'frozen', False)


def _running_executable_path() -> Optional[str]:
    """Path of the currently-running .exe, or None when running from source."""
    if _is_frozen():
        return os.path.realpath(sys.executable)
    return None


def _safe_filename(filename: str) -> bool:
    """Validate that the server-supplied filename matches our naming scheme."""
    if not filename or '/' in filename or '\\' in filename or '..' in filename:
        return False
    return filename.startswith(_SAFE_FILENAME[0]) and filename.endswith(_SAFE_FILENAME[1])


def _absolute_url(base_url: str, candidate: str) -> str:
    """Resolve a possibly-relative download URL against the server base URL."""
    parsed = urlparse(candidate)
    if parsed.scheme in ('http', 'https'):
        return candidate
    return urljoin(base_url.rstrip('/') + '/', candidate.lstrip('/'))


def fetch_guide(
    server_base_url: str,
    api_key: str,
    tenant_header: str,
    tenant_slug: str,
    current_version: str,
    timeout: int,
) -> Optional[dict]:
    """Call the server guide endpoint and return the parsed `guide` dict."""
    url = urljoin(server_base_url.rstrip('/') + '/', 'api/agent/releases/guide')
    headers = {'X-API-Key': api_key, 'Accept': 'application/json'}
    if tenant_slug:
        headers[tenant_header] = tenant_slug

    try:
        response = requests.get(
            url,
            headers=headers,
            params={'current_version': current_version},
            timeout=timeout,
        )
    except requests.RequestException as exc:
        logger.warning('Update guide request failed: %s', exc)
        return None

    if response.status_code != 200:
        logger.warning(
            'Update guide returned HTTP %s: %s',
            response.status_code,
            response.text[:200],
        )
        return None

    try:
        body = response.json()
    except ValueError:
        logger.warning('Update guide returned non-JSON body')
        return None

    guide = body.get('guide') if isinstance(body, dict) else None
    if not isinstance(guide, dict):
        logger.warning('Update guide payload missing "guide" object')
        return None
    return guide


def _download_binary(
    url: str,
    api_key: str,
    tenant_header: str,
    tenant_slug: str,
    expected_sha256: Optional[str],
    timeout: int,
) -> Optional[str]:
    """Stream the .exe to a temp file. Returns temp path on success."""
    headers = {'X-API-Key': api_key}
    if tenant_slug:
        headers[tenant_header] = tenant_slug

    try:
        response = requests.get(url, headers=headers, stream=True, timeout=timeout)
    except requests.RequestException as exc:
        logger.warning('Update download failed: %s', exc)
        return None

    if response.status_code != 200:
        logger.warning(
            'Update download returned HTTP %s: %s',
            response.status_code,
            response.text[:200],
        )
        return None

    hasher = hashlib.sha256()
    total = 0
    fd, tmp_path = tempfile.mkstemp(prefix='aaditech-agent-update-', suffix='.exe')
    try:
        with os.fdopen(fd, 'wb') as handle:
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                total += len(chunk)
                if total > _MAX_DOWNLOAD_BYTES:
                    logger.warning(
                        'Update download aborted: exceeded %s bytes', _MAX_DOWNLOAD_BYTES
                    )
                    raise IOError('download_too_large')
                handle.write(chunk)
                hasher.update(chunk)
    except (IOError, OSError) as exc:
        logger.warning('Update download write failed: %s', exc)
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        return None

    digest = hasher.hexdigest()
    if expected_sha256:
        if digest.lower() != expected_sha256.lower():
            logger.warning(
                'Update sha256 mismatch: expected=%s got=%s', expected_sha256, digest
            )
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            return None
        logger.info('Update sha256 verified (%s)', digest[:16])
    else:
        logger.info('Update downloaded (%s bytes, sha256=%s)', total, digest[:16])

    return tmp_path


def _replace_running_executable(new_binary_path: str, current_executable_path: str) -> bool:
    """Swap in the freshly downloaded binary in place of the running .exe.

    On Windows the running .exe is locked, so we rename it aside first
    (which Windows allows) and then move the new binary into place.
    On non-Windows hosts we simply overwrite.
    Returns True when the swap succeeded.
    """
    target_dir = os.path.dirname(current_executable_path)
    backup_path = current_executable_path + '.old'

    try:
        os.chmod(new_binary_path, os.stat(new_binary_path).st_mode | stat.S_IEXEC | stat.S_IRUSR)
    except OSError:
        pass

    if sys.platform.startswith('win'):
        try:
            if os.path.exists(backup_path):
                try:
                    os.unlink(backup_path)
                except OSError:
                    pass
            os.replace(current_executable_path, backup_path)
            shutil.move(new_binary_path, current_executable_path)
        except OSError as exc:
            logger.error('Update swap failed on Windows: %s', exc)
            return False
        logger.info(
            'Update staged: previous binary kept at %s, new binary at %s',
            backup_path,
            current_executable_path,
        )
        return True

    try:
        shutil.move(new_binary_path, current_executable_path)
    except OSError as exc:
        logger.error('Update swap failed: %s', exc)
        return False

    logger.info('Update applied to %s', current_executable_path)
    return True


def check_and_apply_update(
    *,
    current_version: str,
    server_base_url: str,
    api_key: str,
    tenant_header: str,
    tenant_slug: str,
    request_timeout: int = _DEFAULT_DOWNLOAD_TIMEOUT,
    enabled: bool = True,
) -> Optional[str]:
    """Run one update cycle.

    Returns the new version string if an update was applied (the caller
    should restart the process), otherwise None.
    """
    if not enabled:
        return None

    if not _is_frozen():
        logger.debug('Self-update skipped: agent is not running as a frozen .exe')
        return None

    if not api_key or api_key == 'default-key-change-this':
        logger.debug('Self-update skipped: no real API key configured')
        return None

    guide = fetch_guide(
        server_base_url=server_base_url,
        api_key=api_key,
        tenant_header=tenant_header,
        tenant_slug=tenant_slug,
        current_version=current_version,
        timeout=request_timeout,
    )
    if guide is None:
        return None

    action = str(guide.get('action') or 'none').lower()
    recommended = str(guide.get('recommended_version') or '').strip()
    if action not in ('upgrade', 'downgrade') or not recommended:
        logger.debug(
            'No update action required (action=%s, recommended=%s, current=%s)',
            action,
            recommended,
            current_version,
        )
        return None

    if recommended == current_version:
        logger.debug('Server recommends the version we already run (%s)', recommended)
        return None

    download_url = guide.get('recommended_download_url')
    expected_filename = None
    expected_sha256 = None
    for release in guide.get('releases', []) or []:
        if release.get('version') == recommended:
            expected_filename = release.get('filename')
            expected_sha256 = release.get('sha256') or release.get('checksum_sha256')
            if not download_url:
                download_url = release.get('download_url')
            break

    if not download_url:
        logger.warning('Update guide had no download URL for version %s', recommended)
        return None

    if expected_filename and not _safe_filename(expected_filename):
        logger.warning('Refusing to download unsafe filename: %s', expected_filename)
        return None

    absolute_url = _absolute_url(server_base_url, download_url)
    logger.info(
        'Self-update %s -> %s starting (%s)',
        current_version,
        recommended,
        absolute_url,
    )

    tmp_binary = _download_binary(
        url=absolute_url,
        api_key=api_key,
        tenant_header=tenant_header,
        tenant_slug=tenant_slug,
        expected_sha256=expected_sha256,
        timeout=request_timeout,
    )
    if not tmp_binary:
        return None

    current_executable_path = _running_executable_path()
    if not current_executable_path:
        logger.warning('Self-update aborted: cannot resolve running executable path')
        try:
            os.unlink(tmp_binary)
        except OSError:
            pass
        return None

    if not _replace_running_executable(tmp_binary, current_executable_path):
        try:
            os.unlink(tmp_binary)
        except OSError:
            pass
        return None

    return recommended
