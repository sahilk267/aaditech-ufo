"""Log ingestion service for Phase 2 Week 13-14 foundation."""

from __future__ import annotations

import re
import subprocess
from typing import Any


class LogService:
    """Business logic for log ingestion pipeline adapter boundaries."""

    SAFE_SOURCE_PATTERN = re.compile(r'^[a-zA-Z0-9_.-]{1,64}$')
    SAFE_QUERY_PATTERN = re.compile(r'^[a-zA-Z0-9_.:\- ]{1,128}$')
    ALLOWED_INGESTION_ADAPTERS = {'windows', 'linux_test_double'}

    @classmethod
    def search_and_index_logs(
        cls,
        source_name: str,
        query_text: str,
        runtime_config: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], str | None]:
        """Search logs by query and build a lightweight inverted index for results."""
        runtime_config = runtime_config or {}

        source_name = str(source_name or '').strip()
        if not source_name:
            return {'status': 'validation_failed', 'reason': 'source_name_missing'}, 'source_name_missing'

        if not cls.SAFE_SOURCE_PATTERN.fullmatch(source_name):
            return {'status': 'policy_blocked', 'reason': 'source_name_invalid'}, 'source_name_invalid'

        query_text = str(query_text or '').strip()
        if not query_text:
            return {'status': 'validation_failed', 'reason': 'query_text_missing'}, 'query_text_missing'

        if not cls.SAFE_QUERY_PATTERN.fullmatch(query_text):
            return {'status': 'policy_blocked', 'reason': 'query_text_invalid'}, 'query_text_invalid'

        allowed_sources = runtime_config.get('allowed_sources') or []
        if allowed_sources:
            allowed_set = {str(value).strip() for value in allowed_sources if str(value).strip()}
            if source_name not in allowed_set:
                return {
                    'status': 'policy_blocked',
                    'reason': 'source_not_allowlisted',
                    'source_name': source_name,
                }, 'source_not_allowlisted'

        adapter = str(runtime_config.get('search_adapter') or 'linux_test_double').strip()
        if adapter not in cls.ALLOWED_INGESTION_ADAPTERS:
            return {'status': 'policy_blocked', 'reason': 'adapter_not_allowed'}, 'adapter_not_allowed'

        max_results = runtime_config.get('max_results', 25)
        try:
            max_results = int(max_results)
        except (TypeError, ValueError):
            max_results = 25
        max_results = max(1, min(max_results, 200))

        timeout_seconds = runtime_config.get('command_timeout_seconds', 8)
        try:
            timeout_seconds = int(timeout_seconds)
        except (TypeError, ValueError):
            timeout_seconds = 8
        timeout_seconds = max(1, min(timeout_seconds, 30))

        if adapter == 'windows':
            return cls._search_windows_logs(source_name, query_text, timeout_seconds, max_results)

        search_map = runtime_config.get('linux_test_double_search_entries') or {}
        return cls._search_linux_test_double_logs(source_name, query_text, search_map, max_results)

    @classmethod
    def monitor_drivers(
        cls,
        host_name: str,
        runtime_config: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], str | None]:
        """Collect driver inventory using adapter boundary."""
        runtime_config = runtime_config or {}

        host_name = str(host_name or '').strip()
        if not host_name:
            return {'status': 'validation_failed', 'reason': 'host_name_missing'}, 'host_name_missing'

        if not cls.SAFE_SOURCE_PATTERN.fullmatch(host_name):
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

        adapter = str(runtime_config.get('driver_monitor_adapter') or 'linux_test_double').strip()
        if adapter not in cls.ALLOWED_INGESTION_ADAPTERS:
            return {'status': 'policy_blocked', 'reason': 'adapter_not_allowed'}, 'adapter_not_allowed'

        max_entries = runtime_config.get('max_entries', 50)
        try:
            max_entries = int(max_entries)
        except (TypeError, ValueError):
            max_entries = 50
        max_entries = max(1, min(max_entries, 500))

        timeout_seconds = runtime_config.get('command_timeout_seconds', 8)
        try:
            timeout_seconds = int(timeout_seconds)
        except (TypeError, ValueError):
            timeout_seconds = 8
        timeout_seconds = max(1, min(timeout_seconds, 30))

        if adapter == 'windows':
            return cls._monitor_windows_drivers(host_name, timeout_seconds, max_entries)

        driver_map = runtime_config.get('linux_test_double_drivers') or {}
        return cls._monitor_linux_test_double_drivers(host_name, driver_map, max_entries)

    @classmethod
    def detect_driver_errors(
        cls,
        host_name: str,
        runtime_config: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], str | None]:
        """Detect driver error conditions via adapter boundary."""
        runtime_config = runtime_config or {}

        host_name = str(host_name or '').strip()
        if not host_name:
            return {'status': 'validation_failed', 'reason': 'host_name_missing'}, 'host_name_missing'

        if not cls.SAFE_SOURCE_PATTERN.fullmatch(host_name):
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

        adapter = str(runtime_config.get('driver_error_adapter') or 'linux_test_double').strip()
        if adapter not in cls.ALLOWED_INGESTION_ADAPTERS:
            return {'status': 'policy_blocked', 'reason': 'adapter_not_allowed'}, 'adapter_not_allowed'

        max_entries = runtime_config.get('max_entries', 50)
        try:
            max_entries = int(max_entries)
        except (TypeError, ValueError):
            max_entries = 50
        max_entries = max(1, min(max_entries, 500))

        timeout_seconds = runtime_config.get('command_timeout_seconds', 8)
        try:
            timeout_seconds = int(timeout_seconds)
        except (TypeError, ValueError):
            timeout_seconds = 8
        timeout_seconds = max(1, min(timeout_seconds, 30))

        if adapter == 'windows':
            return cls._detect_windows_driver_errors(host_name, timeout_seconds, max_entries)

        error_map = runtime_config.get('linux_test_double_driver_errors') or {}
        return cls._detect_linux_test_double_driver_errors(host_name, error_map, max_entries)

    @classmethod
    def stream_events(
        cls,
        source_name: str,
        runtime_config: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], str | None]:
        """Provide foundational event stream batches with cursor."""
        runtime_config = runtime_config or {}

        source_name = str(source_name or '').strip()
        if not source_name:
            return {'status': 'validation_failed', 'reason': 'source_name_missing'}, 'source_name_missing'

        if not cls.SAFE_SOURCE_PATTERN.fullmatch(source_name):
            return {'status': 'policy_blocked', 'reason': 'source_name_invalid'}, 'source_name_invalid'

        allowed_sources = runtime_config.get('allowed_sources') or []
        if allowed_sources:
            allowed_set = {str(value).strip() for value in allowed_sources if str(value).strip()}
            if source_name not in allowed_set:
                return {
                    'status': 'policy_blocked',
                    'reason': 'source_not_allowlisted',
                    'source_name': source_name,
                }, 'source_not_allowlisted'

        adapter = str(runtime_config.get('event_stream_adapter') or 'linux_test_double').strip()
        if adapter not in cls.ALLOWED_INGESTION_ADAPTERS:
            return {'status': 'policy_blocked', 'reason': 'adapter_not_allowed'}, 'adapter_not_allowed'

        batch_size = runtime_config.get('batch_size', 25)
        try:
            batch_size = int(batch_size)
        except (TypeError, ValueError):
            batch_size = 25
        batch_size = max(1, min(batch_size, 200))

        timeout_seconds = runtime_config.get('command_timeout_seconds', 8)
        try:
            timeout_seconds = int(timeout_seconds)
        except (TypeError, ValueError):
            timeout_seconds = 8
        timeout_seconds = max(1, min(timeout_seconds, 30))

        if adapter == 'windows':
            return cls._stream_windows_events(source_name, timeout_seconds, batch_size)

        stream_map = runtime_config.get('linux_test_double_streams') or {}
        return cls._stream_linux_test_double_events(source_name, stream_map, batch_size)

    @classmethod
    def query_event_entries(
        cls,
        source_name: str,
        runtime_config: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], str | None]:
        """Query event entries using win32 event adapter boundary."""
        runtime_config = runtime_config or {}

        source_name = str(source_name or '').strip()
        if not source_name:
            return {'status': 'validation_failed', 'reason': 'source_name_missing'}, 'source_name_missing'

        if not cls.SAFE_SOURCE_PATTERN.fullmatch(source_name):
            return {'status': 'policy_blocked', 'reason': 'source_name_invalid'}, 'source_name_invalid'

        allowed_sources = runtime_config.get('allowed_sources') or []
        if allowed_sources:
            allowed_set = {str(value).strip() for value in allowed_sources if str(value).strip()}
            if source_name not in allowed_set:
                return {
                    'status': 'policy_blocked',
                    'reason': 'source_not_allowlisted',
                    'source_name': source_name,
                }, 'source_not_allowlisted'

        adapter = str(runtime_config.get('event_query_adapter') or 'linux_test_double').strip()
        if adapter not in cls.ALLOWED_INGESTION_ADAPTERS:
            return {'status': 'policy_blocked', 'reason': 'adapter_not_allowed'}, 'adapter_not_allowed'

        max_entries = runtime_config.get('max_entries', 25)
        try:
            max_entries = int(max_entries)
        except (TypeError, ValueError):
            max_entries = 25
        max_entries = max(1, min(max_entries, 200))

        timeout_seconds = runtime_config.get('command_timeout_seconds', 8)
        try:
            timeout_seconds = int(timeout_seconds)
        except (TypeError, ValueError):
            timeout_seconds = 8
        timeout_seconds = max(1, min(timeout_seconds, 30))

        if adapter == 'windows':
            return cls._query_windows_event_entries(source_name, timeout_seconds, max_entries)

        test_double_map = runtime_config.get('linux_test_double_events') or {}
        return cls._query_linux_test_double_event_entries(source_name, test_double_map, max_entries)

    @classmethod
    def ingest_logs(
        cls,
        source_name: str,
        runtime_config: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], str | None]:
        """Ingest logs from a source using configured adapter boundary."""
        runtime_config = runtime_config or {}

        source_name = str(source_name or '').strip()
        if not source_name:
            return {'status': 'validation_failed', 'reason': 'source_name_missing'}, 'source_name_missing'

        if not cls.SAFE_SOURCE_PATTERN.fullmatch(source_name):
            return {'status': 'policy_blocked', 'reason': 'source_name_invalid'}, 'source_name_invalid'

        allowed_sources = runtime_config.get('allowed_sources') or []
        if allowed_sources:
            allowed_set = {str(value).strip() for value in allowed_sources if str(value).strip()}
            if source_name not in allowed_set:
                return {
                    'status': 'policy_blocked',
                    'reason': 'source_not_allowlisted',
                    'source_name': source_name,
                }, 'source_not_allowlisted'

        adapter = str(runtime_config.get('log_ingestion_adapter') or 'linux_test_double').strip()
        if adapter not in cls.ALLOWED_INGESTION_ADAPTERS:
            return {'status': 'policy_blocked', 'reason': 'adapter_not_allowed'}, 'adapter_not_allowed'

        max_entries = runtime_config.get('max_entries', 25)
        try:
            max_entries = int(max_entries)
        except (TypeError, ValueError):
            max_entries = 25
        max_entries = max(1, min(max_entries, 200))

        timeout_seconds = runtime_config.get('command_timeout_seconds', 8)
        try:
            timeout_seconds = int(timeout_seconds)
        except (TypeError, ValueError):
            timeout_seconds = 8
        timeout_seconds = max(1, min(timeout_seconds, 30))

        if adapter == 'windows':
            return cls._ingest_windows_logs(source_name, timeout_seconds, max_entries)

        test_double_map = runtime_config.get('linux_test_double_logs') or {}
        return cls._ingest_linux_test_double_logs(source_name, test_double_map, max_entries)

    @classmethod
    def _ingest_windows_logs(
        cls,
        source_name: str,
        timeout_seconds: int,
        max_entries: int,
    ) -> tuple[dict[str, Any], str | None]:
        """Ingest logs from Windows Event Log using wevtutil boundary."""
        command = ['wevtutil', 'qe', source_name, f'/c:{max_entries}', '/f:text']
        completed = cls._run_windows_log_ingestion_command(command, timeout_seconds)

        stdout_text = (completed.stdout or '').strip()
        stderr_text = (completed.stderr or '').strip()
        parsed_entries = [line.strip() for line in stdout_text.splitlines() if line.strip()][:max_entries]

        is_success = int(completed.returncode) == 0
        result = {
            'status': 'success' if is_success else 'command_failed',
            'adapter': 'windows',
            'source_name': source_name,
            'entries': parsed_entries,
            'entry_count': len(parsed_entries),
            'command': command,
            'returncode': int(completed.returncode),
            'stdout': stdout_text[:500],
            'stderr': stderr_text[:500],
        }
        return result, None if is_success else 'command_failed'

    @staticmethod
    def _run_windows_log_ingestion_command(command: list[str], timeout_seconds: int):
        """Execute Windows log ingestion command with shell disabled."""
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=False,
        )

    @staticmethod
    def _ingest_linux_test_double_logs(
        source_name: str,
        test_double_map: dict[str, Any],
        max_entries: int,
    ) -> tuple[dict[str, Any], str | None]:
        """Resolve log entries from deterministic Linux test-double map."""
        raw_value = test_double_map.get(source_name, [])
        if isinstance(raw_value, str):
            entries = [item.strip() for item in raw_value.split('|') if item.strip()]
        elif isinstance(raw_value, list):
            entries = [str(item).strip() for item in raw_value if str(item).strip()]
        else:
            entries = []

        entries = entries[:max_entries]
        return {
            'status': 'success',
            'adapter': 'linux_test_double',
            'source_name': source_name,
            'entries': entries,
            'entry_count': len(entries),
            'source': 'configured_test_double',
        }, None

    @classmethod
    def _query_windows_event_entries(
        cls,
        source_name: str,
        timeout_seconds: int,
        max_entries: int,
    ) -> tuple[dict[str, Any], str | None]:
        """Query Windows events through a win32-event wrapper command boundary."""
        query_script = (
            "Get-WinEvent -LogName '"
            + source_name
            + "' -MaxEvents "
            + str(max_entries)
            + " | ForEach-Object { \"$($_.TimeCreated.ToString('o'))|$($_.LevelDisplayName)|$($_.Id)|$($_.ProviderName)|$($_.Message)\" }"
        )
        command = ['powershell.exe', '-Command', query_script]
        completed = cls._run_windows_event_query_command(command, timeout_seconds)

        stdout_text = (completed.stdout or '').strip()
        stderr_text = (completed.stderr or '').strip()
        entries = [line.strip() for line in stdout_text.splitlines() if line.strip()][:max_entries]

        is_success = int(completed.returncode) == 0
        result = {
            'status': 'success' if is_success else 'command_failed',
            'adapter': 'windows',
            'source_name': source_name,
            'entries': entries,
            'entry_count': len(entries),
            'command': command,
            'returncode': int(completed.returncode),
            'stdout': stdout_text[:500],
            'stderr': stderr_text[:500],
        }
        return result, None if is_success else 'command_failed'

    @staticmethod
    def _run_windows_event_query_command(command: list[str], timeout_seconds: int):
        """Execute Windows event query boundary with shell disabled."""
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=False,
        )

    @staticmethod
    def _query_linux_test_double_event_entries(
        source_name: str,
        test_double_map: dict[str, Any],
        max_entries: int,
    ) -> tuple[dict[str, Any], str | None]:
        """Resolve event entries from deterministic Linux test-double map."""
        raw_value = test_double_map.get(source_name, [])
        if isinstance(raw_value, str):
            entries = [item.strip() for item in raw_value.split('||') if item.strip()]
        elif isinstance(raw_value, list):
            entries = [str(item).strip() for item in raw_value if str(item).strip()]
        else:
            entries = []

        entries = entries[:max_entries]
        return {
            'status': 'success',
            'adapter': 'linux_test_double',
            'source_name': source_name,
            'entries': entries,
            'entry_count': len(entries),
            'source': 'configured_test_double',
        }, None

    @staticmethod
    def parse_log_entries(
        entries: list[Any],
        runtime_config: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], str | None]:
        """Parse raw log/event entries into structured records."""
        runtime_config = runtime_config or {}

        if not isinstance(entries, list):
            return {'status': 'validation_failed', 'reason': 'entries_must_be_list'}, 'entries_must_be_list'

        max_entries = runtime_config.get('max_entries', 50)
        try:
            max_entries = int(max_entries)
        except (TypeError, ValueError):
            max_entries = 50
        max_entries = max(1, min(max_entries, 500))

        normalized = [str(item).strip() for item in entries if str(item).strip()][:max_entries]
        structured = [LogService._parse_single_entry(item) for item in normalized]

        return {
            'status': 'success',
            'entry_count': len(normalized),
            'structured_count': len(structured),
            'events': structured,
        }, None

    @staticmethod
    def filter_and_correlate_events(
        events: list[dict[str, Any]],
        runtime_config: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], str | None]:
        """Filter events by severity and correlate by source/event id."""
        runtime_config = runtime_config or {}

        if not isinstance(events, list):
            return {'status': 'validation_failed', 'reason': 'events_must_be_list'}, 'events_must_be_list'

        allowed_severities = runtime_config.get('allowed_severities') or []
        allowed_set = {str(item).strip().lower() for item in allowed_severities if str(item).strip()}

        min_group_size = runtime_config.get('min_group_size', 2)
        try:
            min_group_size = int(min_group_size)
        except (TypeError, ValueError):
            min_group_size = 2
        min_group_size = max(1, min(min_group_size, 20))

        filtered_events: list[dict[str, Any]] = []
        for event in events:
            if not isinstance(event, dict):
                continue
            severity = str(event.get('severity') or 'info').strip().lower()
            if allowed_set and severity not in allowed_set:
                continue
            filtered_events.append(event)

        grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for event in filtered_events:
            source = str(event.get('source') or 'unknown')
            event_id = str(event.get('event_id') or 'unknown')
            grouped.setdefault((source, event_id), []).append(event)

        correlated_groups: list[dict[str, Any]] = []
        for (source, event_id), group_items in grouped.items():
            if len(group_items) < min_group_size:
                continue
            severities = sorted({str(item.get('severity') or 'info').lower() for item in group_items})
            correlated_groups.append({
                'source': source,
                'event_id': event_id,
                'group_size': len(group_items),
                'severities': severities,
                'sample_events': group_items[:3],
            })

        return {
            'status': 'success',
            'input_count': len(events),
            'filtered_count': len(filtered_events),
            'group_count': len(correlated_groups),
            'groups': correlated_groups,
        }, None

    @staticmethod
    def _parse_single_entry(entry_text: str) -> dict[str, Any]:
        """Parse a single pipe-delimited entry into normalized event fields."""
        parts = [part.strip() for part in str(entry_text).split('|')]
        if len(parts) >= 5:
            timestamp, severity, event_id, source, message = parts[:5]
        else:
            timestamp = ''
            severity = 'info'
            event_id = 'unknown'
            source = 'unknown'
            message = str(entry_text).strip()

        return {
            'timestamp': timestamp,
            'severity': str(severity or 'info').lower(),
            'event_id': str(event_id or 'unknown'),
            'source': str(source or 'unknown'),
            'message': str(message or ''),
            'raw': str(entry_text),
        }

    @classmethod
    def _monitor_windows_drivers(
        cls,
        host_name: str,
        timeout_seconds: int,
        max_entries: int,
    ) -> tuple[dict[str, Any], str | None]:
        """Collect driver inventory through Win32_PnPSignedDriver boundary."""
        query_script = (
            "Get-CimInstance Win32_PnPSignedDriver | Select-Object -First "
            + str(max_entries)
            + " DeviceName,DriverVersion,Manufacturer,IsSigned | "
            + "ForEach-Object { \"$($_.DeviceName)|$($_.DriverVersion)|$($_.Manufacturer)|$($_.IsSigned)\" }"
        )
        command = ['powershell.exe', '-Command', query_script]
        completed = cls._run_windows_driver_monitor_command(command, timeout_seconds)

        stdout_text = (completed.stdout or '').strip()
        stderr_text = (completed.stderr or '').strip()
        raw_entries = [line.strip() for line in stdout_text.splitlines() if line.strip()][:max_entries]
        drivers = [cls._parse_driver_entry(item) for item in raw_entries]

        is_success = int(completed.returncode) == 0
        result = {
            'status': 'success' if is_success else 'command_failed',
            'adapter': 'windows',
            'host_name': host_name,
            'drivers': drivers,
            'driver_count': len(drivers),
            'command': command,
            'returncode': int(completed.returncode),
            'stdout': stdout_text[:500],
            'stderr': stderr_text[:500],
        }
        return result, None if is_success else 'command_failed'

    @staticmethod
    def _run_windows_driver_monitor_command(command: list[str], timeout_seconds: int):
        """Execute Win32 driver monitor command with shell disabled."""
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=False,
        )

    @staticmethod
    def _monitor_linux_test_double_drivers(
        host_name: str,
        driver_map: dict[str, Any],
        max_entries: int,
    ) -> tuple[dict[str, Any], str | None]:
        """Resolve driver inventory from deterministic Linux test-double map."""
        raw_value = driver_map.get(host_name, [])
        if isinstance(raw_value, str):
            items = [item.strip() for item in raw_value.split('||') if item.strip()]
        elif isinstance(raw_value, list):
            items = [str(item).strip() for item in raw_value if str(item).strip()]
        else:
            items = []

        drivers = [LogService._parse_driver_entry(item) for item in items[:max_entries]]
        return {
            'status': 'success',
            'adapter': 'linux_test_double',
            'host_name': host_name,
            'drivers': drivers,
            'driver_count': len(drivers),
            'source': 'configured_test_double',
        }, None

    @classmethod
    def _detect_windows_driver_errors(
        cls,
        host_name: str,
        timeout_seconds: int,
        max_entries: int,
    ) -> tuple[dict[str, Any], str | None]:
        """Detect unsigned/failing drivers via Win32 boundary."""
        query_script = (
            "Get-CimInstance Win32_PnPSignedDriver | "
            + "Where-Object { $_.IsSigned -eq $false } | Select-Object -First "
            + str(max_entries)
            + " DeviceName,DriverVersion,Manufacturer,IsSigned | "
            + "ForEach-Object { \"$($_.DeviceName)|$($_.DriverVersion)|$($_.Manufacturer)|$($_.IsSigned)|unsigned\" }"
        )
        command = ['powershell.exe', '-Command', query_script]
        completed = cls._run_windows_driver_error_command(command, timeout_seconds)

        stdout_text = (completed.stdout or '').strip()
        stderr_text = (completed.stderr or '').strip()
        raw_entries = [line.strip() for line in stdout_text.splitlines() if line.strip()][:max_entries]
        errors = [cls._parse_driver_error_entry(item) for item in raw_entries]

        is_success = int(completed.returncode) == 0
        result = {
            'status': 'success' if is_success else 'command_failed',
            'adapter': 'windows',
            'host_name': host_name,
            'errors': errors,
            'error_count': len(errors),
            'command': command,
            'returncode': int(completed.returncode),
            'stdout': stdout_text[:500],
            'stderr': stderr_text[:500],
        }
        return result, None if is_success else 'command_failed'

    @staticmethod
    def _run_windows_driver_error_command(command: list[str], timeout_seconds: int):
        """Execute Windows driver error query with shell disabled."""
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=False,
        )

    @staticmethod
    def _detect_linux_test_double_driver_errors(
        host_name: str,
        error_map: dict[str, Any],
        max_entries: int,
    ) -> tuple[dict[str, Any], str | None]:
        """Resolve driver errors from deterministic Linux test-double map."""
        raw_value = error_map.get(host_name, [])
        if isinstance(raw_value, str):
            items = [item.strip() for item in raw_value.split('||') if item.strip()]
        elif isinstance(raw_value, list):
            items = [str(item).strip() for item in raw_value if str(item).strip()]
        else:
            items = []

        errors = [LogService._parse_driver_error_entry(item) for item in items[:max_entries]]
        return {
            'status': 'success',
            'adapter': 'linux_test_double',
            'host_name': host_name,
            'errors': errors,
            'error_count': len(errors),
            'source': 'configured_test_double',
        }, None

    @classmethod
    def _stream_windows_events(
        cls,
        source_name: str,
        timeout_seconds: int,
        batch_size: int,
    ) -> tuple[dict[str, Any], str | None]:
        """Stream event batch through Windows event boundary."""
        query_script = (
            "Get-WinEvent -LogName '"
            + source_name
            + "' -MaxEvents "
            + str(batch_size)
            + " | ForEach-Object { \"$($_.RecordId)|$($_.TimeCreated.ToString('o'))|$($_.LevelDisplayName)|$($_.Id)|$($_.ProviderName)|$($_.Message)\" }"
        )
        command = ['powershell.exe', '-Command', query_script]
        completed = cls._run_windows_event_stream_command(command, timeout_seconds)

        stdout_text = (completed.stdout or '').strip()
        stderr_text = (completed.stderr or '').strip()
        entries = [line.strip() for line in stdout_text.splitlines() if line.strip()][:batch_size]

        last_cursor = None
        if entries:
            first_token = entries[-1].split('|', 1)[0].strip()
            last_cursor = first_token if first_token else str(len(entries))

        is_success = int(completed.returncode) == 0
        result = {
            'status': 'success' if is_success else 'command_failed',
            'adapter': 'windows',
            'source_name': source_name,
            'events': entries,
            'event_count': len(entries),
            'next_cursor': last_cursor,
            'command': command,
            'returncode': int(completed.returncode),
            'stdout': stdout_text[:500],
            'stderr': stderr_text[:500],
        }
        return result, None if is_success else 'command_failed'

    @staticmethod
    def _run_windows_event_stream_command(command: list[str], timeout_seconds: int):
        """Execute Windows event stream command with shell disabled."""
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=False,
        )

    @staticmethod
    def _stream_linux_test_double_events(
        source_name: str,
        stream_map: dict[str, Any],
        batch_size: int,
    ) -> tuple[dict[str, Any], str | None]:
        """Resolve event stream batch from deterministic Linux test-double map."""
        raw_value = stream_map.get(source_name, [])
        if isinstance(raw_value, str):
            entries = [item.strip() for item in raw_value.split('||') if item.strip()]
        elif isinstance(raw_value, list):
            entries = [str(item).strip() for item in raw_value if str(item).strip()]
        else:
            entries = []

        entries = entries[:batch_size]
        next_cursor = str(len(entries)) if entries else None
        return {
            'status': 'success',
            'adapter': 'linux_test_double',
            'source_name': source_name,
            'events': entries,
            'event_count': len(entries),
            'next_cursor': next_cursor,
            'source': 'configured_test_double',
        }, None

    @classmethod
    def _search_windows_logs(
        cls,
        source_name: str,
        query_text: str,
        timeout_seconds: int,
        max_results: int,
    ) -> tuple[dict[str, Any], str | None]:
        """Search Windows events using Get-WinEvent command boundary."""
        escaped_query = query_text.replace("'", "''")
        query_script = (
            "Get-WinEvent -LogName '"
            + source_name
            + "' -MaxEvents "
            + str(max_results)
            + " | Where-Object { $_.Message -like '*"
            + escaped_query
            + "*' } | ForEach-Object { \"$($_.TimeCreated.ToString('o'))|$($_.LevelDisplayName)|$($_.Id)|$($_.ProviderName)|$($_.Message)\" }"
        )
        command = ['powershell.exe', '-Command', query_script]
        completed = cls._run_windows_log_search_command(command, timeout_seconds)

        stdout_text = (completed.stdout or '').strip()
        stderr_text = (completed.stderr or '').strip()
        raw_entries = [line.strip() for line in stdout_text.splitlines() if line.strip()]
        filtered_entries = [
            item
            for item in raw_entries
            if query_text.lower() in item.lower()
        ][:max_results]
        structured_results = [cls._parse_single_entry(item) for item in filtered_entries]
        index_data = cls._build_simple_inverted_index(structured_results)

        is_success = int(completed.returncode) == 0
        result = {
            'status': 'success' if is_success else 'command_failed',
            'adapter': 'windows',
            'source_name': source_name,
            'query_text': query_text,
            'results': structured_results,
            'result_count': len(structured_results),
            'index': index_data,
            'command': command,
            'returncode': int(completed.returncode),
            'stdout': stdout_text[:500],
            'stderr': stderr_text[:500],
        }
        return result, None if is_success else 'command_failed'

    @staticmethod
    def _run_windows_log_search_command(command: list[str], timeout_seconds: int):
        """Execute Windows log search command with shell disabled."""
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=False,
        )

    @classmethod
    def _search_linux_test_double_logs(
        cls,
        source_name: str,
        query_text: str,
        search_map: dict[str, Any],
        max_results: int,
    ) -> tuple[dict[str, Any], str | None]:
        """Search deterministic Linux test-double log entries."""
        raw_value = search_map.get(source_name, [])
        if isinstance(raw_value, str):
            entries = [item.strip() for item in raw_value.split('||') if item.strip()]
        elif isinstance(raw_value, list):
            entries = [str(item).strip() for item in raw_value if str(item).strip()]
        else:
            entries = []

        filtered_entries = [
            item
            for item in entries
            if query_text.lower() in item.lower()
        ][:max_results]
        structured_results = [cls._parse_single_entry(item) for item in filtered_entries]
        index_data = cls._build_simple_inverted_index(structured_results)

        return {
            'status': 'success',
            'adapter': 'linux_test_double',
            'source_name': source_name,
            'query_text': query_text,
            'results': structured_results,
            'result_count': len(structured_results),
            'index': index_data,
            'source': 'configured_test_double',
        }, None

    @staticmethod
    def _build_simple_inverted_index(events: list[dict[str, Any]]) -> dict[str, Any]:
        """Build lightweight token index metadata from event messages."""
        token_map: dict[str, list[int]] = {}
        for idx, event in enumerate(events):
            message = str(event.get('message') or '').lower()
            for token in re.findall(r'[a-z0-9_\-]{2,}', message):
                positions = token_map.setdefault(token, [])
                if idx not in positions:
                    positions.append(idx)

        return {
            'document_count': len(events),
            'token_count': len(token_map),
            'tokens': sorted(token_map.keys())[:50],
        }

    @staticmethod
    def _parse_driver_entry(entry_text: str) -> dict[str, Any]:
        """Parse a single driver inventory entry."""
        parts = [part.strip() for part in str(entry_text).split('|')]
        name = parts[0] if len(parts) > 0 else 'unknown'
        version = parts[1] if len(parts) > 1 else ''
        manufacturer = parts[2] if len(parts) > 2 else ''
        signed_raw = parts[3] if len(parts) > 3 else 'true'

        return {
            'driver_name': name,
            'driver_version': version,
            'manufacturer': manufacturer,
            'is_signed': str(signed_raw).lower() in {'true', '1', 'yes'},
        }

    @staticmethod
    def _parse_driver_error_entry(entry_text: str) -> dict[str, Any]:
        """Parse a single driver error entry."""
        parts = [part.strip() for part in str(entry_text).split('|')]
        name = parts[0] if len(parts) > 0 else 'unknown'
        version = parts[1] if len(parts) > 1 else ''
        manufacturer = parts[2] if len(parts) > 2 else ''
        signed_raw = parts[3] if len(parts) > 3 else 'false'
        reason = parts[4] if len(parts) > 4 else 'reported_by_test_double'

        return {
            'driver_name': name,
            'driver_version': version,
            'manufacturer': manufacturer,
            'is_signed': str(signed_raw).lower() in {'true', '1', 'yes'},
            'reason': reason,
        }
