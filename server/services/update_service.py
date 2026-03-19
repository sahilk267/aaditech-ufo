"""Windows Update monitoring service for Phase 2 Week 16 foundation."""

from __future__ import annotations

import re
import subprocess
from typing import Any


class UpdateService:
    """Business logic for Windows Update monitor adapter boundaries."""

    SAFE_HOST_PATTERN = re.compile(r'^[a-zA-Z0-9_.-]{1,64}$')
    ALLOWED_ADAPTERS = {'windows', 'linux_test_double'}

    @classmethod
    def monitor_windows_updates(
        cls,
        host_name: str,
        runtime_config: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], str | None]:
        """Collect a bounded Windows Update status snapshot."""
        runtime_config = runtime_config or {}

        host_name = str(host_name or '').strip()
        if not host_name:
            return {'status': 'validation_failed', 'reason': 'host_name_missing'}, 'host_name_missing'

        if not cls.SAFE_HOST_PATTERN.fullmatch(host_name):
            return {'status': 'policy_blocked', 'reason': 'host_name_invalid'}, 'host_name_invalid'

        allowed_hosts = runtime_config.get('allowed_hosts') or []
        if allowed_hosts:
            allowed_set = {str(value).strip() for value in allowed_hosts if str(value).strip()}
            if host_name not in allowed_set:
                return {
                    'status': 'policy_blocked',
                    'reason': 'host_not_allowlisted',
                    'host_name': host_name,
                }, 'host_not_allowlisted'

        adapter = str(runtime_config.get('update_monitor_adapter') or 'linux_test_double').strip()
        if adapter not in cls.ALLOWED_ADAPTERS:
            return {'status': 'policy_blocked', 'reason': 'adapter_not_allowed'}, 'adapter_not_allowed'

        max_updates = runtime_config.get('max_updates', 25)
        try:
            max_updates = int(max_updates)
        except (TypeError, ValueError):
            max_updates = 25
        max_updates = max(1, min(max_updates, 200))

        timeout_seconds = runtime_config.get('command_timeout_seconds', 8)
        try:
            timeout_seconds = int(timeout_seconds)
        except (TypeError, ValueError):
            timeout_seconds = 8
        timeout_seconds = max(1, min(timeout_seconds, 30))

        if adapter == 'windows':
            return cls._monitor_windows_updates(host_name, timeout_seconds, max_updates)

        updates_map = runtime_config.get('linux_test_double_updates') or {}
        return cls._monitor_linux_test_double_updates(host_name, updates_map, max_updates)

    @classmethod
    def _monitor_windows_updates(
        cls,
        host_name: str,
        timeout_seconds: int,
        max_updates: int,
    ) -> tuple[dict[str, Any], str | None]:
        """Collect installed hotfixes through a bounded PowerShell boundary."""
        query_script = (
            "Get-HotFix -ComputerName '"
            + host_name
            + "' | Select-Object -First "
            + str(max_updates)
            + " HotFixID,Description,InstalledOn | "
            + "ForEach-Object { \"$($_.HotFixID)|$($_.Description)|$($_.InstalledOn.ToString('yyyy-MM-dd'))\" }"
        )
        command = ['powershell.exe', '-Command', query_script]
        completed = cls._run_windows_update_monitor_command(command, timeout_seconds)

        stdout_text = (completed.stdout or '').strip()
        stderr_text = (completed.stderr or '').strip()
        if int(completed.returncode) != 0:
            return {
                'status': 'command_failed',
                'adapter': 'windows',
                'host_name': host_name,
                'returncode': int(completed.returncode),
                'stderr': stderr_text[:500],
            }, 'command_failed'

        updates = [
            cls._parse_update_entry(line)
            for line in stdout_text.splitlines()
            if line.strip()
        ][:max_updates]
        latest_installed_on = max(
            (item.get('installed_on') or '' for item in updates),
            default='',
        )

        return {
            'status': 'success',
            'adapter': 'windows',
            'host_name': host_name,
            'updates': updates,
            'update_count': len(updates),
            'latest_installed_on': latest_installed_on,
            'status_summary': 'updates_detected' if updates else 'no_updates_visible',
            'monitoring_version': 'foundation-v1',
            'stdout_preview': stdout_text[:500],
        }, None

    @staticmethod
    def _run_windows_update_monitor_command(command: list[str], timeout_seconds: int):
        """Execute Windows Update monitor command with shell disabled."""
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=False,
        )

    @classmethod
    def _monitor_linux_test_double_updates(
        cls,
        host_name: str,
        updates_map: dict[str, Any],
        max_updates: int,
    ) -> tuple[dict[str, Any], str | None]:
        """Resolve deterministic update data for tests/dev on Linux."""
        raw_value = updates_map.get(host_name, [])
        if isinstance(raw_value, str):
            entries = [item.strip() for item in raw_value.split('||') if item.strip()]
        elif isinstance(raw_value, list):
            entries = [str(item).strip() for item in raw_value if str(item).strip()]
        else:
            entries = []

        updates = [cls._parse_update_entry(item) for item in entries[:max_updates]]
        latest_installed_on = max(
            (item.get('installed_on') or '' for item in updates),
            default='',
        )

        return {
            'status': 'success',
            'adapter': 'linux_test_double',
            'host_name': host_name,
            'updates': updates,
            'update_count': len(updates),
            'latest_installed_on': latest_installed_on,
            'status_summary': 'updates_detected' if updates else 'no_updates_visible',
            'monitoring_version': 'foundation-v1',
            'source': 'configured_test_double',
        }, None

    @staticmethod
    def _parse_update_entry(entry_text: str) -> dict[str, Any]:
        """Parse a single Windows Update entry into normalized fields."""
        parts = [part.strip() for part in str(entry_text).split('|', 2)]
        hotfix_id = parts[0] if len(parts) > 0 else ''
        description = parts[1] if len(parts) > 1 else ''
        installed_on = parts[2] if len(parts) > 2 else ''

        classification = 'other'
        description_lower = description.lower()
        if 'security' in description_lower:
            classification = 'security'
        elif 'cumulative' in description_lower:
            classification = 'cumulative'
        elif 'update' in description_lower:
            classification = 'update'

        return {
            'hotfix_id': hotfix_id,
            'description': description,
            'installed_on': installed_on,
            'classification': classification,
        }