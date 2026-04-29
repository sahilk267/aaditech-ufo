"""Agent-side remote command poller and executor.

Polls ``/api/agent/commands/pending`` for queued instructions, runs each via a
strict whitelist, and POSTs the result to ``/api/agent/commands/<id>/result``.
Designed to fail safe: unknown command types or unsafe payloads are rejected
without execution.
"""

from __future__ import annotations

import logging
import platform
import shlex
import subprocess
from typing import Any
from urllib.parse import urljoin

import requests

logger = logging.getLogger('aaditech-agent.commands')


SAFE_COMMAND_TYPES = {
    'ping',
    'restart_service',
    'rotate_logs',
    'collect_diagnostics',
    'run_powershell',
}

# Allow-list of PowerShell verbs/scripts that are safe to execute. The agent
# refuses to run anything else even when the server queues it (defense in depth).
POWERSHELL_ALLOWED_PREFIXES = (
    'Get-Service',
    'Get-Process',
    'Get-EventLog',
    'Get-WinEvent',
    'Get-ComputerInfo',
    'Get-Item',
    'Test-Path',
    'Test-NetConnection',
)


def _is_default_key(key: str) -> bool:
    return key in ('', 'default-key-change-this', 'default-api-key-change-me')


def poll_and_execute(
    *,
    server_base_url: str,
    api_key: str,
    tenant_header: str,
    tenant_slug: str,
    serial_number: str,
    request_timeout: float = 15.0,
) -> dict[str, int]:
    """One full poll → execute → report cycle. Safe against all errors."""
    if _is_default_key(api_key):
        logger.debug('Skipping command poll: default API key in use.')
        return {'fetched': 0, 'executed': 0, 'reported': 0, 'failures': 0}

    headers = {'X-API-Key': api_key, 'Content-Type': 'application/json'}
    if tenant_slug:
        headers[tenant_header or 'X-Tenant-Slug'] = tenant_slug

    fetch_url = urljoin(server_base_url + '/', 'api/agent/commands/pending')
    try:
        resp = requests.get(
            fetch_url,
            params={'serial_number': serial_number} if serial_number else None,
            headers=headers,
            timeout=request_timeout,
        )
    except requests.RequestException as exc:
        logger.warning('Command poll request failed: %s', exc)
        return {'fetched': 0, 'executed': 0, 'reported': 0, 'failures': 1}

    if resp.status_code >= 400:
        logger.warning('Command poll returned HTTP %s: %s', resp.status_code, resp.text[:200])
        return {'fetched': 0, 'executed': 0, 'reported': 0, 'failures': 1}

    try:
        commands = (resp.json() or {}).get('commands') or []
    except ValueError:
        commands = []

    stats = {'fetched': len(commands), 'executed': 0, 'reported': 0, 'failures': 0}

    for cmd in commands:
        cmd_id = cmd.get('id')
        cmd_type = (cmd.get('command_type') or '').strip()
        payload = cmd.get('payload') or {}
        if cmd_id is None or cmd_type not in SAFE_COMMAND_TYPES:
            stats['failures'] += 1
            _post_result(server_base_url, headers, cmd_id, 'failure', None, f'Unknown command type: {cmd_type}', request_timeout)
            continue

        try:
            outcome = _execute(cmd_type, payload)
            stats['executed'] += 1
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning('Command %s execution failed: %s', cmd_type, exc)
            outcome = {'status': 'failure', 'error': str(exc), 'result': None}
            stats['failures'] += 1

        if _post_result(
            server_base_url,
            headers,
            cmd_id,
            outcome['status'],
            outcome.get('result'),
            outcome.get('error'),
            request_timeout,
        ):
            stats['reported'] += 1
        else:
            stats['failures'] += 1

    return stats


def _post_result(
    server_base_url: str,
    headers: dict[str, str],
    cmd_id: int | None,
    status: str,
    result: Any,
    error: str | None,
    timeout: float,
) -> bool:
    if cmd_id is None:
        return False
    body = {'status': status, 'result': result, 'error': error}
    url = urljoin(server_base_url + '/', f'api/agent/commands/{int(cmd_id)}/result')
    try:
        resp = requests.post(url, json=body, headers=headers, timeout=timeout)
        return resp.status_code < 400
    except requests.RequestException as exc:
        logger.warning('Command %s result POST failed: %s', cmd_id, exc)
        return False


def _execute(cmd_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    if cmd_type == 'ping':
        return _ok({'pong': True, 'platform': platform.system().lower()})

    if cmd_type == 'collect_diagnostics':
        import psutil
        return _ok({
            'cpu_percent': psutil.cpu_percent(interval=0.2),
            'ram_percent': psutil.virtual_memory().percent,
            'platform': platform.platform(),
            'python_version': platform.python_version(),
        })

    if cmd_type == 'restart_service':
        service = (payload.get('service_name') or '').strip()
        if not service or any(c in service for c in ' ;|&`$()<>'):
            return _fail('invalid service_name')
        if platform.system().lower() == 'windows':
            cmd = ['powershell', '-NoProfile', '-Command', f'Restart-Service -Name {shlex.quote(service)} -Force']
        else:
            cmd = ['systemctl', 'restart', service]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        if proc.returncode != 0:
            return _fail(proc.stderr.strip()[:500] or 'restart failed', stdout=proc.stdout[:500])
        return _ok({'service': service, 'stdout': proc.stdout[:500]})

    if cmd_type == 'rotate_logs':
        path = (payload.get('path') or '').strip()
        if not path:
            return _fail('path required')
        import os
        from datetime import datetime
        if not os.path.isfile(path):
            return _fail(f'file not found: {path}')
        rotated = f"{path}.{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.bak"
        os.replace(path, rotated)
        open(path, 'w', encoding='utf-8').close()
        return _ok({'rotated_to': rotated})

    if cmd_type == 'run_powershell':
        script = (payload.get('script') or '').strip()
        if not script:
            return _fail('script required')
        if not any(script.startswith(prefix) for prefix in POWERSHELL_ALLOWED_PREFIXES):
            return _fail(f'script not in allow-list (must start with one of {POWERSHELL_ALLOWED_PREFIXES})')
        if platform.system().lower() != 'windows':
            return _fail('run_powershell only supported on Windows')
        proc = subprocess.run(
            ['powershell', '-NoProfile', '-Command', script],
            capture_output=True, text=True, timeout=30,
        )
        if proc.returncode != 0:
            return _fail(proc.stderr.strip()[:500] or 'script failed', stdout=proc.stdout[:500])
        return _ok({'stdout': proc.stdout[:2000]})

    return _fail(f'unhandled command type: {cmd_type}')


def _ok(result: Any) -> dict[str, Any]:
    return {'status': 'success', 'result': result, 'error': None}


def _fail(error: str, **extra) -> dict[str, Any]:
    return {'status': 'failure', 'result': extra or None, 'error': error}
