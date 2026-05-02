"""Aaditech UFO client agent.

This agent collects host metrics and submits them to the server endpoint:
POST /api/submit_data

Environment variables:
- SERVER_BASE_URL (default: http://localhost:5000)
- AGENT_SUBMIT_PATH (default: /api/submit_data)
- AGENT_API_KEY (required in production)
- TENANT_HEADER (default: X-Tenant-Slug)
- TENANT_SLUG (optional)
- AGENT_REPORT_INTERVAL_SECONDS (default: 60)
- AGENT_REQUEST_TIMEOUT_SECONDS (default: 10)
- AGENT_UPDATE_CHECK_INTERVAL_SECONDS (default: 3600; <=0 disables)
- AGENT_UPDATE_ENABLED (default: 1; set to 0 to disable self-update)
- AGENT_LOG_FORWARD_ENABLED (default: 0; set to 1 to enable)
- AGENT_LOG_FORWARD_PATHS (comma-separated file paths to tail)
- AGENT_LOG_FORWARD_WINDOWS_EVENT_LOGS (comma-separated channels e.g. System,Application)
- AGENT_LOG_FORWARD_INTERVAL_SECONDS (default: 60)
- AGENT_LOG_FORWARD_STATE_DIR (default: alongside the .exe)
"""

from __future__ import annotations

import getpass
import logging
import os
import platform
import socket
import subprocess
import sys
import time
from datetime import datetime
from urllib.parse import urljoin

import psutil
import requests
from dotenv import load_dotenv

try:
    from agent.updater import check_and_apply_update
    from agent.version import AGENT_VERSION
    from agent.log_forwarder import forward_logs_once
    from agent.transport import AgentTransport, default_state_path
    from agent.commands import poll_and_execute as poll_and_execute_commands
except ImportError:  # pragma: no cover - PyInstaller flattens packages
    from updater import check_and_apply_update  # type: ignore[no-redef]
    from version import AGENT_VERSION  # type: ignore[no-redef]
    from log_forwarder import forward_logs_once  # type: ignore[no-redef]
    from transport import AgentTransport, default_state_path  # type: ignore[no-redef]
    from commands import poll_and_execute as poll_and_execute_commands  # type: ignore[no-redef]


load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s [agent] %(levelname)s: %(message)s')
logger = logging.getLogger('aaditech-agent')


def _env_int(name: str, default: int, min_value: int, max_value: int) -> int:
    value_raw = os.getenv(name, str(default)).strip()
    try:
        value = int(value_raw)
    except ValueError:
        return default
    return max(min_value, min(value, max_value))


SERVER_BASE_URL = os.getenv('SERVER_BASE_URL', 'http://localhost:5000').strip().rstrip('/')
AGENT_SUBMIT_PATH = os.getenv('AGENT_SUBMIT_PATH', '/api/submit_data').strip()
SUBMIT_URL = urljoin(SERVER_BASE_URL + '/', AGENT_SUBMIT_PATH.lstrip('/'))
AGENT_API_KEY = os.getenv('AGENT_API_KEY', 'default-key-change-this').strip()
TENANT_HEADER = os.getenv('TENANT_HEADER', 'X-Tenant-Slug').strip() or 'X-Tenant-Slug'
TENANT_SLUG = os.getenv('TENANT_SLUG', '').strip().lower()
REPORT_INTERVAL = _env_int('AGENT_REPORT_INTERVAL_SECONDS', 60, 15, 86400)
REQUEST_TIMEOUT = _env_int('AGENT_REQUEST_TIMEOUT_SECONDS', 10, 3, 60)
UPDATE_CHECK_INTERVAL = _env_int('AGENT_UPDATE_CHECK_INTERVAL_SECONDS', 3600, 0, 86400)
UPDATE_REQUEST_TIMEOUT = _env_int('AGENT_UPDATE_REQUEST_TIMEOUT_SECONDS', 120, 10, 600)
UPDATE_ENABLED = os.getenv('AGENT_UPDATE_ENABLED', '1').strip().lower() not in ('0', 'false', 'no', 'off', '')

LOG_FORWARD_ENABLED = os.getenv('AGENT_LOG_FORWARD_ENABLED', '0').strip().lower() in ('1', 'true', 'yes', 'on')
LOG_FORWARD_PATHS = [item.strip() for item in os.getenv('AGENT_LOG_FORWARD_PATHS', '').split(',') if item.strip()]
LOG_FORWARD_EVENT_LOGS = [item.strip() for item in os.getenv('AGENT_LOG_FORWARD_WINDOWS_EVENT_LOGS', '').split(',') if item.strip()]
LOG_FORWARD_INTERVAL = _env_int('AGENT_LOG_FORWARD_INTERVAL_SECONDS', 60, 15, 3600)
LOG_FORWARD_STATE_DIR = os.getenv('AGENT_LOG_FORWARD_STATE_DIR', '').strip()
LOG_FORWARD_REQUEST_TIMEOUT = _env_int('AGENT_LOG_FORWARD_REQUEST_TIMEOUT_SECONDS', 15, 3, 120)

OUTBOX_STATE_DIR = os.getenv('AGENT_OUTBOX_STATE_DIR', '').strip()
OUTBOX_MAX_QUEUE = _env_int('AGENT_OUTBOX_MAX_QUEUE', 5000, 100, 100000)
TRANSPORT_MAX_ATTEMPTS = _env_int('AGENT_TRANSPORT_MAX_ATTEMPTS', 3, 1, 10)

COMMAND_POLL_ENABLED = os.getenv('AGENT_COMMAND_POLL_ENABLED', '1').strip().lower() not in ('0', 'false', 'no', 'off', '')
COMMAND_POLL_INTERVAL = _env_int('AGENT_COMMAND_POLL_INTERVAL_SECONDS', 30, 10, 3600)
COMMAND_POLL_TIMEOUT = _env_int('AGENT_COMMAND_POLL_TIMEOUT_SECONDS', 15, 3, 60)


_transport_instance: AgentTransport | None = None


def _get_transport() -> AgentTransport:
    global _transport_instance
    if _transport_instance is None:
        frozen_exe = sys.executable if getattr(sys, 'frozen', False) else None
        path = default_state_path(OUTBOX_STATE_DIR or None, frozen_exe)
        _transport_instance = AgentTransport(
            db_path=path,
            max_queue=OUTBOX_MAX_QUEUE,
            max_attempts_per_call=TRANSPORT_MAX_ATTEMPTS,
        )
    return _transport_instance


def _run_wmic_value(command: str, default: str) -> str:
    try:
        output = subprocess.check_output(command, shell=True, text=True, stderr=subprocess.DEVNULL)
        lines = [line.strip() for line in output.splitlines() if line.strip()]
        if len(lines) >= 2:
            return lines[1]
    except Exception as exc:
        logger.debug('WMIC command failed (%s): %s', command, exc)
    return default


def _get_public_ip() -> str:
    try:
        return requests.get('https://api.ipify.org', timeout=REQUEST_TIMEOUT).text.strip()
    except Exception:
        return 'N/A'


def _get_local_ip() -> str:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(('8.8.8.8', 80))
        local_ip = sock.getsockname()[0]
        sock.close()
        return local_ip
    except Exception:
        return 'N/A'


def get_system_info() -> dict:
    serial_number = _run_wmic_value('wmic bios get serialnumber', platform.node())
    cpu_info = _run_wmic_value('wmic cpu get name', platform.processor() or 'Unknown CPU')

    model_primary = _run_wmic_value('wmic csproduct get name', '')
    model_fallback = _run_wmic_value('wmic computersystem get model', 'Unknown Model')
    model_number = model_primary if model_primary and model_primary != 'To be filled by O.E.M.' else model_fallback

    ram = psutil.virtual_memory()
    ram_info = {
        'total': ram.total / (1024**3),
        'available': ram.available / (1024**3),
        'used': (ram.total - ram.available) / (1024**3),
        'percent': ram.percent,
    }

    return {
        'serial_number': serial_number or 'N/A',
        'hostname': platform.node() or 'N/A',
        'model_number': model_number or 'Unknown Model',
        'local_ip': _get_local_ip(),
        'public_ip': _get_public_ip(),
        'cpu_info': cpu_info,
        'cpu_cores': psutil.cpu_count(logical=False),
        'cpu_threads': psutil.cpu_count(logical=True),
        'ram_info': ram_info,
        'current_user': getpass.getuser() or 'N/A',
    }


def get_performance_metrics() -> dict:
    cpu_usage = psutil.cpu_percent(interval=1)
    cpu_per_core = psutil.cpu_percent(interval=1, percpu=True)
    cpu_freq = psutil.cpu_freq()
    ram_usage = psutil.virtual_memory().percent

    disk_info = []
    for partition in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(partition.mountpoint)
            disk_info.append(
                {
                    'device': partition.device,
                    'mountpoint': partition.mountpoint,
                    'total': usage.total / (1024**3),
                    'used': usage.used / (1024**3),
                    'free': usage.free / (1024**3),
                    'percent': usage.percent,
                }
            )
        except Exception:
            continue

    return {
        'cpu_usage': cpu_usage,
        'cpu_per_core': cpu_per_core,
        'cpu_frequency': {
            'current': cpu_freq.current if cpu_freq else None,
            'min': cpu_freq.min if cpu_freq else None,
            'max': cpu_freq.max if cpu_freq else None,
        },
        'ram_usage': ram_usage,
        'storage_usage': psutil.disk_usage('/').percent,
        'disk_info': disk_info,
    }


def run_benchmark() -> dict:
    software_benchmark = (psutil.cpu_count() or 1) * 10
    hardware_benchmark = psutil.virtual_memory().total / (1024 * 1024)
    overall_benchmark = (software_benchmark + hardware_benchmark) / 2
    return {
        'software_benchmark': software_benchmark,
        'hardware_benchmark': hardware_benchmark,
        'overall_benchmark': overall_benchmark,
    }


def send_data(payload: dict) -> None:
    headers = {
        'X-API-Key': AGENT_API_KEY,
        'Content-Type': 'application/json',
    }
    if TENANT_SLUG:
        headers[TENANT_HEADER] = TENANT_SLUG

    transport = _get_transport()
    result = transport.post(SUBMIT_URL, json=payload, headers=headers, timeout=REQUEST_TIMEOUT)

    if result.success:
        if result.drained:
            logger.info(
                'Data submitted to %s (also drained %s queued payloads)',
                SUBMIT_URL,
                result.drained,
            )
        else:
            logger.info('Data submitted successfully to %s', SUBMIT_URL)
    elif result.queued:
        logger.warning(
            'Data submission failed (%s); queued for retry. Outbox size=%s',
            result.error or 'transient error',
            transport.queue_size(),
        )
    else:
        logger.error(
            'Data submission permanently rejected (%s status=%s). Payload dropped.',
            result.error,
            result.status_code,
        )


def build_payload() -> dict:
    payload = {}
    payload.update(get_system_info())
    payload.update(get_performance_metrics())
    payload.update(run_benchmark())
    payload['last_update'] = datetime.now().isoformat()
    payload['status'] = 'active'
    payload['agent_version'] = AGENT_VERSION
    return payload


def _maybe_self_update() -> None:
    """Run one update check; restart the process when a new version is staged."""
    if not UPDATE_ENABLED or UPDATE_CHECK_INTERVAL <= 0:
        return
    try:
        new_version = check_and_apply_update(
            current_version=AGENT_VERSION,
            server_base_url=SERVER_BASE_URL,
            api_key=AGENT_API_KEY,
            tenant_header=TENANT_HEADER,
            tenant_slug=TENANT_SLUG,
            request_timeout=UPDATE_REQUEST_TIMEOUT,
            enabled=UPDATE_ENABLED,
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning('Self-update check failed unexpectedly: %s', exc)
        return

    if not new_version:
        return

    logger.info(
        'Self-update applied: %s -> %s. Restarting process to load the new binary.',
        AGENT_VERSION,
        new_version,
    )
    try:
        os.execv(sys.executable, [sys.executable] + sys.argv[1:])
    except OSError as exc:
        logger.error(
            'Self-update binary swapped but exec failed (%s). Exiting so the supervisor restarts us.',
            exc,
        )
        sys.exit(0)


def _maybe_forward_logs() -> None:
    """Run one log-forward cycle. Errors are swallowed."""
    if not LOG_FORWARD_ENABLED:
        return
    if not LOG_FORWARD_PATHS and not LOG_FORWARD_EVENT_LOGS:
        return
    try:
        stats = forward_logs_once(
            server_base_url=SERVER_BASE_URL,
            api_key=AGENT_API_KEY,
            tenant_header=TENANT_HEADER,
            tenant_slug=TENANT_SLUG,
            file_paths=LOG_FORWARD_PATHS,
            event_log_channels=LOG_FORWARD_EVENT_LOGS,
            state_dir=LOG_FORWARD_STATE_DIR,
            request_timeout=LOG_FORWARD_REQUEST_TIMEOUT,
            enabled=True,
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning('Log forwarding cycle failed unexpectedly: %s', exc)
        return

    if stats.get('lines_uploaded') or stats.get('batches_failed'):
        logger.info(
            'Log forward: uploaded=%s collected=%s files=%s channels=%s failed_batches=%s',
            stats.get('lines_uploaded', 0),
            stats.get('lines_collected', 0),
            stats.get('files_seen', 0),
            stats.get('event_channels_seen', 0),
            stats.get('batches_failed', 0),
        )


def main() -> None:
    logger.info(
        'Starting Aaditech agent v%s | submit_url=%s | interval=%ss | update_check=%ss%s | log_forward=%s',
        AGENT_VERSION,
        SUBMIT_URL,
        REPORT_INTERVAL,
        UPDATE_CHECK_INTERVAL,
        '' if UPDATE_ENABLED else ' (disabled)',
        f'every {LOG_FORWARD_INTERVAL}s ({len(LOG_FORWARD_PATHS)} files, {len(LOG_FORWARD_EVENT_LOGS)} channels)' if LOG_FORWARD_ENABLED else 'disabled',
    )

    last_update_check = 0.0
    last_log_forward = 0.0
    last_command_poll = 0.0
    cached_serial: str | None = None
    while True:
        now = time.monotonic()

        if UPDATE_ENABLED and UPDATE_CHECK_INTERVAL > 0 and (now - last_update_check) >= UPDATE_CHECK_INTERVAL:
            _maybe_self_update()
            last_update_check = now

        if LOG_FORWARD_ENABLED and (now - last_log_forward) >= LOG_FORWARD_INTERVAL:
            _maybe_forward_logs()
            last_log_forward = now

        payload = build_payload()
        if cached_serial is None:
            cached_serial = str(payload.get('serial_number') or '').strip() or None
        send_data(payload)

        if COMMAND_POLL_ENABLED and (now - last_command_poll) >= COMMAND_POLL_INTERVAL:
            _maybe_poll_commands(cached_serial)
            last_command_poll = now

        time.sleep(REPORT_INTERVAL)


def _maybe_poll_commands(serial_number: str | None) -> None:
    try:
        stats = poll_and_execute_commands(
            server_base_url=SERVER_BASE_URL,
            api_key=AGENT_API_KEY,
            tenant_header=TENANT_HEADER,
            tenant_slug=TENANT_SLUG,
            serial_number=serial_number or '',
            request_timeout=COMMAND_POLL_TIMEOUT,
        )
        if stats.get('fetched'):
            logger.info(
                'Remote commands processed: fetched=%d executed=%d reported=%d failures=%d',
                stats['fetched'], stats['executed'], stats['reported'], stats['failures'],
            )
    except Exception as exc:
        logger.warning('Command poll cycle failed: %s', exc)


if __name__ == '__main__':
    main()