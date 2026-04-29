"""Persistent agent keystore for rotated API keys + pinned server certs.

Stores values in a small JSON file alongside the agent (or under
``~/.aaditech-agent/`` in dev) so credential rotation survives restarts.
Never logs the actual key value, only fingerprints.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
from typing import Optional

logger = logging.getLogger('aaditech-agent.keystore')


def default_keystore_path(state_dir: str | None, frozen_executable: str | None = None) -> str:
    if state_dir:
        base = state_dir
    elif frozen_executable:
        base = os.path.dirname(os.path.abspath(frozen_executable))
    else:
        base = os.path.join(os.path.expanduser('~'), '.aaditech-agent')
    if not os.path.isdir(base):
        os.makedirs(base, exist_ok=True)
    return os.path.join(base, 'keystore.json')


class AgentKeystore:
    """Tiny JSON-backed keystore. Atomic write to survive crashes."""

    def __init__(self, path: str) -> None:
        self._path = path
        self._data = self._load()

    def _load(self) -> dict:
        if not os.path.exists(self._path):
            return {}
        try:
            with open(self._path, 'r', encoding='utf-8') as fh:
                return json.load(fh) or {}
        except Exception as exc:
            logger.warning('Keystore unreadable, starting fresh: %s', exc)
            return {}

    def _save(self) -> None:
        directory = os.path.dirname(os.path.abspath(self._path)) or '.'
        os.makedirs(directory, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(prefix='ks_', dir=directory)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as fh:
                json.dump(self._data, fh)
            os.replace(tmp_path, self._path)
        except Exception:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
            raise

    # ---- API key -----------------------------------------------------

    def get_api_key(self, fallback: str | None = None) -> Optional[str]:
        return self._data.get('api_key') or fallback

    def set_api_key(self, key: str) -> None:
        self._data['api_key'] = key
        self._save()
        logger.info(
            'API key updated in keystore (sha256=%s...)',
            hashlib.sha256(key.encode('utf-8')).hexdigest()[:12],
        )

    # ---- Server cert pin --------------------------------------------

    def get_pin(self) -> Optional[str]:
        value = self._data.get('server_cert_sha256')
        return value.lower() if value else None

    def set_pin(self, sha256_hex: str) -> None:
        normalized = sha256_hex.strip().lower().replace(':', '')
        if len(normalized) != 64 or not all(c in '0123456789abcdef' for c in normalized):
            raise ValueError('invalid sha256 hex pin')
        self._data['server_cert_sha256'] = normalized
        self._save()
        logger.info('Server cert pin updated (sha256=%s...)', normalized[:12])

    def clear_pin(self) -> None:
        self._data.pop('server_cert_sha256', None)
        self._save()


def fetch_server_cert_sha256(host: str, port: int = 443, timeout: float = 5.0) -> str:
    """Connect via TLS and return the leaf cert's SHA-256 fingerprint (hex)."""
    import socket
    import ssl

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    with socket.create_connection((host, port), timeout=timeout) as sock:
        with ctx.wrap_socket(sock, server_hostname=host) as ssock:
            der = ssock.getpeercert(binary_form=True)
    return hashlib.sha256(der).hexdigest()
