"""Log forwarding for the Aaditech agent.

Tails one or more local files (and optionally the Windows event log channels
exposed by `wevtutil`) and ships freshly observed lines to the server's
`/api/logs/parse` endpoint, which persists them as `LogEntry` rows.

Wire format expected by the server (`LogService._parse_single_entry`):
    "<timestamp>|<severity>|<event_id>|<source>|<message>"

Designed to be safe-by-default:
- Never blocks the metric loop for more than `request_timeout` seconds.
- Persists per-file read offsets and per-channel last-record-id under a
  state directory so a restart does not re-send historical lines.
- Truncates oversized lines and caps the per-batch payload size.
- Falls back silently when a path does not exist or `wevtutil` is missing.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import urljoin

import requests


logger = logging.getLogger('aaditech-agent.log_forwarder')

_MAX_LINE_BYTES = 8 * 1024  # individual line cap
_MAX_BATCH_ENTRIES = 200
_MAX_LINES_PER_FILE_PER_TICK = 500
_STATE_FILENAME = 'log_forwarder_state.json'
_FIELD_DELIM = '|'
_REPLACEMENT_DELIM = '/'
_DEFAULT_SEVERITY_RE = re.compile(
    r'\b(EMERG|ALERT|CRIT|CRITICAL|ERROR|ERR|WARN|WARNING|NOTICE|INFO|DEBUG|TRACE)\b',
    re.IGNORECASE,
)


def _parse_csv(value: str) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(',') if item.strip()]


def _safe_field(value: str) -> str:
    """Strip pipe characters so the wire format stays parseable."""
    return value.replace(_FIELD_DELIM, _REPLACEMENT_DELIM).strip()


def _detect_severity(line: str) -> str:
    match = _DEFAULT_SEVERITY_RE.search(line)
    if not match:
        return 'info'
    token = match.group(1).upper()
    if token in ('EMERG', 'ALERT', 'CRIT', 'CRITICAL'):
        return 'critical'
    if token in ('ERROR', 'ERR'):
        return 'error'
    if token in ('WARN', 'WARNING'):
        return 'warning'
    if token == 'NOTICE':
        return 'notice'
    if token == 'DEBUG':
        return 'debug'
    if token == 'TRACE':
        return 'trace'
    return 'info'


def _format_entry(*, source: str, message: str, severity: Optional[str] = None,
                  event_id: str = '0', timestamp: Optional[str] = None) -> str:
    safe_source = _safe_field(source) or 'agent'
    safe_message = _safe_field(message)
    if len(safe_message.encode('utf-8', errors='replace')) > _MAX_LINE_BYTES:
        safe_message = safe_message.encode('utf-8', errors='replace')[:_MAX_LINE_BYTES].decode('utf-8', errors='replace')
        safe_message += ' [truncated]'
    sev = (severity or _detect_severity(message)).strip().lower() or 'info'
    ts = timestamp or datetime.now(timezone.utc).isoformat()
    return _FIELD_DELIM.join([
        _safe_field(ts),
        _safe_field(sev),
        _safe_field(str(event_id) or '0'),
        safe_source,
        safe_message,
    ])


class _StateStore:
    """Tiny JSON-backed offset store. Failures are logged and ignored."""

    def __init__(self, state_path: Path):
        self.state_path = state_path
        self._data: dict = {'files': {}, 'event_logs': {}}
        try:
            if state_path.exists():
                with state_path.open('r', encoding='utf-8') as handle:
                    parsed = json.load(handle)
                if isinstance(parsed, dict):
                    self._data['files'] = parsed.get('files') or {}
                    self._data['event_logs'] = parsed.get('event_logs') or {}
        except (OSError, ValueError) as exc:
            logger.warning('Could not read log-forwarder state %s: %s', state_path, exc)

    def get_file(self, path: str) -> dict:
        return self._data['files'].get(path) or {}

    def set_file(self, path: str, *, offset: int, inode: Optional[int], size: int) -> None:
        self._data['files'][path] = {
            'offset': int(offset),
            'inode': int(inode) if inode is not None else None,
            'size': int(size),
        }

    def get_event_log(self, channel: str) -> dict:
        return self._data['event_logs'].get(channel) or {}

    def set_event_log(self, channel: str, *, last_record_id: int) -> None:
        self._data['event_logs'][channel] = {'last_record_id': int(last_record_id)}

    def save(self) -> None:
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.state_path.with_suffix(self.state_path.suffix + '.tmp')
            with tmp.open('w', encoding='utf-8') as handle:
                json.dump(self._data, handle, indent=2)
            os.replace(tmp, self.state_path)
        except OSError as exc:
            logger.warning('Could not persist log-forwarder state: %s', exc)


def _tail_file(path: Path, store: _StateStore) -> list[str]:
    """Return new lines appended since the last call. Handles rotation."""
    if not path.exists() or not path.is_file():
        return []

    try:
        stat = path.stat()
    except OSError as exc:
        logger.debug('Could not stat %s: %s', path, exc)
        return []

    state = store.get_file(str(path))
    saved_offset = int(state.get('offset') or 0)
    saved_inode = state.get('inode')
    saved_size = int(state.get('size') or 0)

    inode_matches = saved_inode in (None, getattr(stat, 'st_ino', None))
    if not inode_matches or stat.st_size < saved_size:
        # Rotation or truncation — start from the beginning of the new file.
        saved_offset = 0

    if saved_offset > stat.st_size:
        saved_offset = 0

    if saved_offset == stat.st_size:
        store.set_file(str(path), offset=stat.st_size, inode=getattr(stat, 'st_ino', None), size=stat.st_size)
        return []

    new_lines: list[str] = []
    bytes_read_offset = saved_offset
    try:
        with path.open('rb') as handle:
            handle.seek(saved_offset)
            for _ in range(_MAX_LINES_PER_FILE_PER_TICK):
                raw = handle.readline()
                if not raw:
                    break
                if not raw.endswith(b'\n'):
                    # Partial line — leave it for the next tick.
                    break
                bytes_read_offset = handle.tell()
                line = raw.decode('utf-8', errors='replace').rstrip('\r\n')
                if line:
                    new_lines.append(line)
            else:
                bytes_read_offset = handle.tell()
    except OSError as exc:
        logger.warning('Reading %s failed: %s', path, exc)
        return []

    store.set_file(
        str(path),
        offset=bytes_read_offset,
        inode=getattr(stat, 'st_ino', None),
        size=stat.st_size,
    )
    return new_lines


def _read_windows_event_log(channel: str, store: _StateStore, max_entries: int,
                             timeout_seconds: int) -> list[tuple[str, dict]]:
    """Return new Windows event log entries via `wevtutil`.

    Each entry is `(formatted_wire_string, metadata_dict)`. Returns [] on any
    failure (missing wevtutil, non-Windows host, parse error, etc.).
    """
    if not sys.platform.startswith('win'):
        return []

    state = store.get_event_log(channel)
    last_record_id = int(state.get('last_record_id') or 0)
    query = f"*[System[EventRecordID > {last_record_id}]]"

    cmd = [
        'wevtutil', 'qe', channel,
        '/c:' + str(int(max_entries)),
        '/rd:false',
        '/f:xml',
        '/q:' + query,
    ]

    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        logger.debug('wevtutil unavailable for channel %s: %s', channel, exc)
        return []

    if completed.returncode != 0:
        logger.debug(
            'wevtutil returned %s for channel %s: %s',
            completed.returncode,
            channel,
            (completed.stderr or '')[:200],
        )
        return []

    output = (completed.stdout or '').strip()
    if not output:
        return []

    try:
        import xml.etree.ElementTree as ET  # noqa: WPS433 - lazy import
    except ImportError:  # pragma: no cover
        return []

    namespace = '{http://schemas.microsoft.com/win/2004/08/events/event}'
    entries: list[tuple[str, dict]] = []
    max_seen_id = last_record_id

    # wevtutil emits one <Event>...</Event> XML doc per record concatenated.
    for chunk in re.split(r'(?<=</Event>)', output):
        chunk = chunk.strip()
        if not chunk.startswith('<Event'):
            continue
        try:
            root = ET.fromstring(chunk)
        except ET.ParseError:
            continue

        system = root.find(f'{namespace}System')
        if system is None:
            continue

        record_id_el = system.find(f'{namespace}EventRecordID')
        event_id_el = system.find(f'{namespace}EventID')
        provider_el = system.find(f'{namespace}Provider')
        time_el = system.find(f'{namespace}TimeCreated')
        level_el = system.find(f'{namespace}Level')
        rendering = root.find(f'{namespace}RenderingInfo/{namespace}Message')
        message = (rendering.text if rendering is not None and rendering.text else '').strip()

        if not message:
            data_strings = [
                (data.text or '').strip()
                for data in root.iter(f'{namespace}Data')
                if (data.text or '').strip()
            ]
            message = ' '.join(data_strings) or 'event'

        try:
            record_id = int(record_id_el.text) if record_id_el is not None and record_id_el.text else 0
        except ValueError:
            record_id = 0
        if record_id > max_seen_id:
            max_seen_id = record_id

        try:
            event_id = int(event_id_el.text) if event_id_el is not None and event_id_el.text else 0
        except ValueError:
            event_id = 0

        provider = (provider_el.get('Name') if provider_el is not None else '') or 'EventLog'
        timestamp = (time_el.get('SystemTime') if time_el is not None else '') or datetime.now(timezone.utc).isoformat()
        level_raw = (level_el.text if level_el is not None else '2')
        severity = {
            '1': 'critical',
            '2': 'error',
            '3': 'warning',
            '4': 'info',
            '5': 'debug',
        }.get(str(level_raw).strip(), 'info')

        wire = _format_entry(
            source=f'eventlog:{channel}:{provider}',
            message=message,
            severity=severity,
            event_id=str(event_id),
            timestamp=timestamp,
        )
        entries.append((wire, {'record_id': record_id}))

    if max_seen_id > last_record_id:
        store.set_event_log(channel, last_record_id=max_seen_id)
    return entries


def _post_batch(batch: list[str], *, server_base_url: str, api_key: str,
                tenant_header: str, tenant_slug: str, timeout: int) -> bool:
    if not batch:
        return True
    url = urljoin(server_base_url.rstrip('/') + '/', 'api/logs/parse')
    headers = {
        'X-API-Key': api_key,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }
    if tenant_slug:
        headers[tenant_header] = tenant_slug
    payload = {'entries': batch}
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=timeout)
    except requests.RequestException as exc:
        logger.warning('Log batch upload failed: %s', exc)
        return False
    if response.status_code != 200:
        logger.warning(
            'Log batch upload returned HTTP %s: %s',
            response.status_code,
            response.text[:200],
        )
        return False
    return True


def _resolve_state_dir(configured: str) -> Path:
    if configured:
        return Path(configured)
    if getattr(sys, 'frozen', False):
        return Path(os.path.dirname(os.path.realpath(sys.executable)))
    return Path.home() / '.aaditech-agent'


def forward_logs_once(
    *,
    server_base_url: str,
    api_key: str,
    tenant_header: str,
    tenant_slug: str,
    file_paths: Iterable[str],
    event_log_channels: Iterable[str],
    state_dir: str,
    request_timeout: int,
    enabled: bool = True,
) -> dict:
    """Run a single forward cycle. Returns a small stats dict."""
    stats = {'files_seen': 0, 'event_channels_seen': 0, 'lines_collected': 0,
             'lines_uploaded': 0, 'batches_failed': 0}

    if not enabled:
        return stats

    if not api_key or api_key == 'default-key-change-this':
        logger.debug('Log forwarding skipped: no real API key configured')
        return stats

    file_paths = [p for p in (str(item).strip() for item in file_paths) if p]
    event_log_channels = [c for c in (str(item).strip() for item in event_log_channels) if c]
    if not file_paths and not event_log_channels:
        return stats

    state_path = _resolve_state_dir(state_dir) / _STATE_FILENAME
    store = _StateStore(state_path)

    pending: list[str] = []

    for raw_path in file_paths:
        path = Path(raw_path).expanduser()
        new_lines = _tail_file(path, store)
        stats['files_seen'] += 1
        for line in new_lines:
            wire = _format_entry(source=f'file:{path.name}', message=line)
            pending.append(wire)
            if len(pending) >= _MAX_BATCH_ENTRIES:
                ok = _post_batch(
                    pending,
                    server_base_url=server_base_url,
                    api_key=api_key,
                    tenant_header=tenant_header,
                    tenant_slug=tenant_slug,
                    timeout=request_timeout,
                )
                if ok:
                    stats['lines_uploaded'] += len(pending)
                else:
                    stats['batches_failed'] += 1
                stats['lines_collected'] += len(pending)
                pending = []

    for channel in event_log_channels:
        events = _read_windows_event_log(
            channel,
            store,
            max_entries=_MAX_BATCH_ENTRIES,
            timeout_seconds=request_timeout,
        )
        stats['event_channels_seen'] += 1
        for wire, _meta in events:
            pending.append(wire)
            if len(pending) >= _MAX_BATCH_ENTRIES:
                ok = _post_batch(
                    pending,
                    server_base_url=server_base_url,
                    api_key=api_key,
                    tenant_header=tenant_header,
                    tenant_slug=tenant_slug,
                    timeout=request_timeout,
                )
                if ok:
                    stats['lines_uploaded'] += len(pending)
                else:
                    stats['batches_failed'] += 1
                stats['lines_collected'] += len(pending)
                pending = []

    if pending:
        ok = _post_batch(
            pending,
            server_base_url=server_base_url,
            api_key=api_key,
            tenant_header=tenant_header,
            tenant_slug=tenant_slug,
            timeout=request_timeout,
        )
        if ok:
            stats['lines_uploaded'] += len(pending)
        else:
            stats['batches_failed'] += 1
        stats['lines_collected'] += len(pending)

    store.save()
    return stats
