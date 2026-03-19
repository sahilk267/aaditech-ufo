"""Reliability history service for Phase 2 Week 15 foundation."""

from __future__ import annotations

import ntpath
import re
import subprocess
from typing import Any


class ReliabilityService:
    """Business logic for reliability/crash history adapter boundaries."""

    SAFE_HOST_PATTERN = re.compile(r'^[a-zA-Z0-9_.-]{1,64}$')
    SAFE_DUMP_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9_.-]{1,128}\.(dmp|mdmp)$', re.IGNORECASE)
    SAFE_DUMP_ROOT_PATTERN = re.compile(r'^[a-zA-Z0-9_:\\/.\- ]{1,260}$')
    ALLOWED_ADAPTERS = {'windows', 'linux_test_double'}

    EXCEPTION_SIGNATURES = {
        'access-violation': ('0xc0000005', 'access_violation'),
        'stack-overflow': ('0xc00000fd', 'stack_overflow'),
        'heap-corruption': ('0xc0000374', 'heap_corruption'),
        'illegal-instruction': ('0xc000001d', 'illegal_instruction'),
        'divide-by-zero': ('0xc0000094', 'divide_by_zero'),
    }
    STACK_TRACE_PROFILES = {
        'access-violation': [
            'ntdll!KiUserExceptionDispatch',
            'app!CrashHandler',
            'kernel32!BaseThreadInitThunk',
        ],
        'stack-overflow': [
            'app!RecursiveEntry',
            'app!RecursiveWorker',
            'kernel32!BaseThreadInitThunk',
        ],
        'heap-corruption': [
            'ntdll!RtlReportCriticalFailure',
            'ucrtbase!free_base',
            'app!ReleaseBuffer',
        ],
        'illegal-instruction': [
            'app!ExecuteVectorPath',
            'ntdll!LdrInitializeThunk',
            'kernel32!BaseThreadInitThunk',
        ],
        'divide-by-zero': [
            'app!ComputeRatio',
            'app!EvaluateTelemetry',
            'kernel32!BaseThreadInitThunk',
        ],
    }

    @classmethod
    def analyze_stack_trace(
        cls,
        host_name: str,
        dump_name: str,
        runtime_config: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], str | None]:
        """Analyze stack trace from crash dump evidence via safe boundary."""
        runtime_config = runtime_config or {}

        host_name = str(host_name or '').strip()
        if not host_name:
            return {'status': 'validation_failed', 'reason': 'host_name_missing'}, 'host_name_missing'

        if not cls.SAFE_HOST_PATTERN.fullmatch(host_name):
            return {'status': 'policy_blocked', 'reason': 'host_name_invalid'}, 'host_name_invalid'

        dump_name = str(dump_name or '').strip()
        if not dump_name:
            return {'status': 'validation_failed', 'reason': 'dump_name_missing'}, 'dump_name_missing'

        if not cls.SAFE_DUMP_NAME_PATTERN.fullmatch(dump_name):
            return {'status': 'policy_blocked', 'reason': 'dump_name_invalid'}, 'dump_name_invalid'

        allowed_hosts = runtime_config.get('allowed_hosts') or []
        if allowed_hosts:
            allowed_set = {str(value).strip() for value in allowed_hosts if str(value).strip()}
            if host_name not in allowed_set:
                return {
                    'status': 'policy_blocked',
                    'reason': 'host_not_allowlisted',
                    'host_name': host_name,
                }, 'host_not_allowlisted'

        dump_root = str(runtime_config.get('crash_dump_root') or r'C:\CrashDumps').strip()
        if not dump_root or not cls.SAFE_DUMP_ROOT_PATTERN.fullmatch(dump_root):
            return {'status': 'policy_blocked', 'reason': 'crash_dump_root_invalid'}, 'crash_dump_root_invalid'

        allowed_dump_roots = runtime_config.get('allowed_dump_roots') or []
        if allowed_dump_roots:
            allowed_roots = {str(value).strip() for value in allowed_dump_roots if str(value).strip()}
            if dump_root not in allowed_roots:
                return {
                    'status': 'policy_blocked',
                    'reason': 'crash_dump_root_not_allowlisted',
                    'crash_dump_root': dump_root,
                }, 'crash_dump_root_not_allowlisted'

        adapter = str(runtime_config.get('stack_trace_adapter') or 'linux_test_double').strip()
        if adapter not in cls.ALLOWED_ADAPTERS:
            return {'status': 'policy_blocked', 'reason': 'adapter_not_allowed'}, 'adapter_not_allowed'

        timeout_seconds = runtime_config.get('command_timeout_seconds', 8)
        try:
            timeout_seconds = int(timeout_seconds)
        except (TypeError, ValueError):
            timeout_seconds = 8
        timeout_seconds = max(1, min(timeout_seconds, 30))

        if adapter == 'windows':
            return cls._analyze_windows_stack_trace(host_name, dump_name, dump_root, timeout_seconds)

        stack_map = runtime_config.get('linux_test_double_stack_traces') or {}
        return cls._analyze_linux_test_double_stack_trace(host_name, dump_name, dump_root, stack_map)

    @classmethod
    def score_reliability(
        cls,
        host_name: str,
        runtime_config: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], str | None]:
        """Score host reliability using safe stability-index boundary."""
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

        adapter = str(runtime_config.get('reliability_scorer_adapter') or 'linux_test_double').strip()
        if adapter not in cls.ALLOWED_ADAPTERS:
            return {'status': 'policy_blocked', 'reason': 'adapter_not_allowed'}, 'adapter_not_allowed'

        timeout_seconds = runtime_config.get('command_timeout_seconds', 8)
        try:
            timeout_seconds = int(timeout_seconds)
        except (TypeError, ValueError):
            timeout_seconds = 8
        timeout_seconds = max(1, min(timeout_seconds, 30))

        if adapter == 'windows':
            return cls._score_windows_reliability(host_name, timeout_seconds)

        score_map = runtime_config.get('linux_test_double_reliability_scores') or {}
        return cls._score_linux_test_double_reliability(host_name, score_map)

    @classmethod
    def analyze_reliability_trend(
        cls,
        host_name: str,
        runtime_config: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], str | None]:
        """Analyze reliability trend direction from stability score history."""
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

        adapter = str(runtime_config.get('trend_adapter') or 'linux_test_double').strip()
        if adapter not in cls.ALLOWED_ADAPTERS:
            return {'status': 'policy_blocked', 'reason': 'adapter_not_allowed'}, 'adapter_not_allowed'

        window_size = runtime_config.get('window_size', 6)
        try:
            window_size = int(window_size)
        except (TypeError, ValueError):
            window_size = 6
        window_size = max(3, min(window_size, 30))

        timeout_seconds = runtime_config.get('command_timeout_seconds', 8)
        try:
            timeout_seconds = int(timeout_seconds)
        except (TypeError, ValueError):
            timeout_seconds = 8
        timeout_seconds = max(1, min(timeout_seconds, 30))

        if adapter == 'windows':
            return cls._analyze_windows_reliability_trend(host_name, timeout_seconds, window_size)

        trend_map = runtime_config.get('linux_test_double_reliability_trends') or {}
        return cls._analyze_linux_test_double_reliability_trend(host_name, trend_map, window_size)

    @classmethod
    def predict_reliability(
        cls,
        host_name: str,
        runtime_config: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], str | None]:
        """Predict near-term reliability score from stability score history."""
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

        adapter = str(runtime_config.get('prediction_adapter') or 'linux_test_double').strip()
        if adapter not in cls.ALLOWED_ADAPTERS:
            return {'status': 'policy_blocked', 'reason': 'adapter_not_allowed'}, 'adapter_not_allowed'

        window_size = runtime_config.get('window_size', 6)
        try:
            window_size = int(window_size)
        except (TypeError, ValueError):
            window_size = 6
        window_size = max(3, min(window_size, 30))

        prediction_horizon = runtime_config.get('prediction_horizon', 2)
        try:
            prediction_horizon = int(prediction_horizon)
        except (TypeError, ValueError):
            prediction_horizon = 2
        prediction_horizon = max(1, min(prediction_horizon, 12))

        timeout_seconds = runtime_config.get('command_timeout_seconds', 8)
        try:
            timeout_seconds = int(timeout_seconds)
        except (TypeError, ValueError):
            timeout_seconds = 8
        timeout_seconds = max(1, min(timeout_seconds, 30))

        if adapter == 'windows':
            return cls._predict_windows_reliability(host_name, timeout_seconds, window_size, prediction_horizon)

        prediction_map = runtime_config.get('linux_test_double_reliability_predictions') or {}
        return cls._predict_linux_test_double_reliability(host_name, prediction_map, window_size, prediction_horizon)

    @classmethod
    def detect_reliability_patterns(
        cls,
        host_name: str,
        runtime_config: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], str | None]:
        """Detect reliability score patterns from stability history."""
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

        adapter = str(runtime_config.get('pattern_adapter') or 'linux_test_double').strip()
        if adapter not in cls.ALLOWED_ADAPTERS:
            return {'status': 'policy_blocked', 'reason': 'adapter_not_allowed'}, 'adapter_not_allowed'

        window_size = runtime_config.get('window_size', 6)
        try:
            window_size = int(window_size)
        except (TypeError, ValueError):
            window_size = 6
        window_size = max(4, min(window_size, 30))

        timeout_seconds = runtime_config.get('command_timeout_seconds', 8)
        try:
            timeout_seconds = int(timeout_seconds)
        except (TypeError, ValueError):
            timeout_seconds = 8
        timeout_seconds = max(1, min(timeout_seconds, 30))

        if adapter == 'windows':
            return cls._detect_windows_reliability_patterns(host_name, timeout_seconds, window_size)

        pattern_map = runtime_config.get('linux_test_double_reliability_patterns') or {}
        return cls._detect_linux_test_double_reliability_patterns(host_name, pattern_map, window_size)

    @classmethod
    def identify_exception(
        cls,
        host_name: str,
        dump_name: str,
        runtime_config: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], str | None]:
        """Identify exception signature from crash dump metadata via safe boundary."""
        runtime_config = runtime_config or {}

        host_name = str(host_name or '').strip()
        if not host_name:
            return {'status': 'validation_failed', 'reason': 'host_name_missing'}, 'host_name_missing'

        if not cls.SAFE_HOST_PATTERN.fullmatch(host_name):
            return {'status': 'policy_blocked', 'reason': 'host_name_invalid'}, 'host_name_invalid'

        dump_name = str(dump_name or '').strip()
        if not dump_name:
            return {'status': 'validation_failed', 'reason': 'dump_name_missing'}, 'dump_name_missing'

        if not cls.SAFE_DUMP_NAME_PATTERN.fullmatch(dump_name):
            return {'status': 'policy_blocked', 'reason': 'dump_name_invalid'}, 'dump_name_invalid'

        allowed_hosts = runtime_config.get('allowed_hosts') or []
        if allowed_hosts:
            allowed_set = {str(value).strip() for value in allowed_hosts if str(value).strip()}
            if host_name not in allowed_set:
                return {
                    'status': 'policy_blocked',
                    'reason': 'host_not_allowlisted',
                    'host_name': host_name,
                }, 'host_not_allowlisted'

        dump_root = str(runtime_config.get('crash_dump_root') or r'C:\CrashDumps').strip()
        if not dump_root or not cls.SAFE_DUMP_ROOT_PATTERN.fullmatch(dump_root):
            return {'status': 'policy_blocked', 'reason': 'crash_dump_root_invalid'}, 'crash_dump_root_invalid'

        allowed_dump_roots = runtime_config.get('allowed_dump_roots') or []
        if allowed_dump_roots:
            allowed_roots = {str(value).strip() for value in allowed_dump_roots if str(value).strip()}
            if dump_root not in allowed_roots:
                return {
                    'status': 'policy_blocked',
                    'reason': 'crash_dump_root_not_allowlisted',
                    'crash_dump_root': dump_root,
                }, 'crash_dump_root_not_allowlisted'

        adapter = str(runtime_config.get('exception_identifier_adapter') or 'linux_test_double').strip()
        if adapter not in cls.ALLOWED_ADAPTERS:
            return {'status': 'policy_blocked', 'reason': 'adapter_not_allowed'}, 'adapter_not_allowed'

        timeout_seconds = runtime_config.get('command_timeout_seconds', 8)
        try:
            timeout_seconds = int(timeout_seconds)
        except (TypeError, ValueError):
            timeout_seconds = 8
        timeout_seconds = max(1, min(timeout_seconds, 30))

        if adapter == 'windows':
            return cls._identify_windows_exception(host_name, dump_name, dump_root, timeout_seconds)

        exception_map = runtime_config.get('linux_test_double_exceptions') or {}
        return cls._identify_linux_test_double_exception(host_name, dump_name, dump_root, exception_map)

    @classmethod
    def parse_crash_dump(
        cls,
        host_name: str,
        dump_name: str,
        runtime_config: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], str | None]:
        """Parse crash dump metadata via safe adapter boundary."""
        runtime_config = runtime_config or {}

        host_name = str(host_name or '').strip()
        if not host_name:
            return {'status': 'validation_failed', 'reason': 'host_name_missing'}, 'host_name_missing'

        if not cls.SAFE_HOST_PATTERN.fullmatch(host_name):
            return {'status': 'policy_blocked', 'reason': 'host_name_invalid'}, 'host_name_invalid'

        dump_name = str(dump_name or '').strip()
        if not dump_name:
            return {'status': 'validation_failed', 'reason': 'dump_name_missing'}, 'dump_name_missing'

        if not cls.SAFE_DUMP_NAME_PATTERN.fullmatch(dump_name):
            return {'status': 'policy_blocked', 'reason': 'dump_name_invalid'}, 'dump_name_invalid'

        allowed_hosts = runtime_config.get('allowed_hosts') or []
        if allowed_hosts:
            allowed_set = {str(value).strip() for value in allowed_hosts if str(value).strip()}
            if host_name not in allowed_set:
                return {
                    'status': 'policy_blocked',
                    'reason': 'host_not_allowlisted',
                    'host_name': host_name,
                }, 'host_not_allowlisted'

        dump_root = str(runtime_config.get('crash_dump_root') or r'C:\CrashDumps').strip()
        if not dump_root or not cls.SAFE_DUMP_ROOT_PATTERN.fullmatch(dump_root):
            return {'status': 'policy_blocked', 'reason': 'crash_dump_root_invalid'}, 'crash_dump_root_invalid'

        allowed_dump_roots = runtime_config.get('allowed_dump_roots') or []
        if allowed_dump_roots:
            allowed_roots = {str(value).strip() for value in allowed_dump_roots if str(value).strip()}
            if dump_root not in allowed_roots:
                return {
                    'status': 'policy_blocked',
                    'reason': 'crash_dump_root_not_allowlisted',
                    'crash_dump_root': dump_root,
                }, 'crash_dump_root_not_allowlisted'

        adapter = str(runtime_config.get('crash_dump_adapter') or 'linux_test_double').strip()
        if adapter not in cls.ALLOWED_ADAPTERS:
            return {'status': 'policy_blocked', 'reason': 'adapter_not_allowed'}, 'adapter_not_allowed'

        timeout_seconds = runtime_config.get('command_timeout_seconds', 8)
        try:
            timeout_seconds = int(timeout_seconds)
        except (TypeError, ValueError):
            timeout_seconds = 8
        timeout_seconds = max(1, min(timeout_seconds, 30))

        if adapter == 'windows':
            return cls._parse_windows_crash_dump(host_name, dump_name, dump_root, timeout_seconds)

        dump_map = runtime_config.get('linux_test_double_crash_dumps') or {}
        return cls._parse_linux_test_double_crash_dump(host_name, dump_name, dump_root, dump_map)

    @classmethod
    def collect_reliability_history(
        cls,
        host_name: str,
        runtime_config: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], str | None]:
        """Collect reliability history via safe adapter boundary."""
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

        adapter = str(runtime_config.get('history_adapter') or 'linux_test_double').strip()
        if adapter not in cls.ALLOWED_ADAPTERS:
            return {'status': 'policy_blocked', 'reason': 'adapter_not_allowed'}, 'adapter_not_allowed'

        max_records = runtime_config.get('max_records', 25)
        try:
            max_records = int(max_records)
        except (TypeError, ValueError):
            max_records = 25
        max_records = max(1, min(max_records, 200))

        timeout_seconds = runtime_config.get('command_timeout_seconds', 8)
        try:
            timeout_seconds = int(timeout_seconds)
        except (TypeError, ValueError):
            timeout_seconds = 8
        timeout_seconds = max(1, min(timeout_seconds, 30))

        if adapter == 'windows':
            return cls._collect_windows_reliability_history(host_name, timeout_seconds, max_records)

        history_map = runtime_config.get('linux_test_double_history') or {}
        return cls._collect_linux_test_double_reliability_history(host_name, history_map, max_records)

    @classmethod
    def _collect_windows_reliability_history(
        cls,
        host_name: str,
        timeout_seconds: int,
        max_records: int,
    ) -> tuple[dict[str, Any], str | None]:
        """Collect reliability records using Get-CimInstance WMI query."""
        command = [
            'powershell.exe',
            '-Command',
            (
                "Get-CimInstance -ClassName Win32_ReliabilityRecords "
                f"-ComputerName '{host_name}' "
                f"| Select-Object -First {max_records} TimeGenerated,SourceName,ProductName,EventIdentifier,Message "
                "| ForEach-Object { \"$($_.TimeGenerated)|$($_.SourceName)|$($_.ProductName)|$($_.EventIdentifier)|$($_.Message)\" }"
            ),
        ]
        completed = cls._run_windows_reliability_history_command(command, timeout_seconds)

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

        records: list[dict[str, str]] = []
        for line in stdout_text.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = [part.strip() for part in line.split('|', 4)]
            if len(parts) < 5:
                continue
            records.append(
                {
                    'timestamp': parts[0],
                    'source': parts[1],
                    'product': parts[2],
                    'event_id': parts[3],
                    'message': parts[4],
                }
            )

        result = {
            'status': 'success',
            'adapter': 'windows',
            'host_name': host_name,
            'record_count': len(records),
            'records': records,
            'stdout_preview': stdout_text[:500],
        }
        return result, None

    @staticmethod
    def _run_windows_reliability_history_command(command: list[str], timeout_seconds: int):
        """Execute reliability history command with shell disabled for safety."""
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=False,
        )

    @classmethod
    def _collect_linux_test_double_reliability_history(
        cls,
        host_name: str,
        history_map: dict[str, list[str]],
        max_records: int,
    ) -> tuple[dict[str, Any], str | None]:
        """Collect deterministic reliability history records for tests/dev on Linux."""
        configured_records = history_map.get(host_name, [])

        records: list[dict[str, str]] = []
        for raw in configured_records[:max_records]:
            parts = [part.strip() for part in str(raw).split('|', 4)]
            if len(parts) < 5:
                continue
            records.append(
                {
                    'timestamp': parts[0],
                    'source': parts[1],
                    'product': parts[2],
                    'event_id': parts[3],
                    'message': parts[4],
                }
            )

        result = {
            'status': 'success',
            'adapter': 'linux_test_double',
            'host_name': host_name,
            'record_count': len(records),
            'records': records,
        }
        return result, None

    @classmethod
    def _parse_windows_crash_dump(
        cls,
        host_name: str,
        dump_name: str,
        dump_root: str,
        timeout_seconds: int,
    ) -> tuple[dict[str, Any], str | None]:
        """Parse crash dump metadata using safe PowerShell file metadata boundary."""
        dump_path = ntpath.join(dump_root, dump_name)
        command = [
            'powershell.exe',
            '-Command',
            (
                "Get-Item -Path '"
                + dump_path
                + "' | ForEach-Object { \"$($_.Name)|$($_.Length)|$($_.LastWriteTimeUtc.ToString('o'))|$($_.Extension)|$($_.DirectoryName)\" }"
            ),
        ]
        completed = cls._run_windows_crash_dump_parse_command(command, timeout_seconds)

        stdout_text = (completed.stdout or '').strip()
        stderr_text = (completed.stderr or '').strip()
        if int(completed.returncode) != 0:
            return {
                'status': 'command_failed',
                'adapter': 'windows',
                'host_name': host_name,
                'dump_name': dump_name,
                'returncode': int(completed.returncode),
                'stderr': stderr_text[:500],
            }, 'command_failed'

        parsed_dump = cls._parse_dump_metadata_line(stdout_text.splitlines()[0] if stdout_text else '', dump_name, dump_root)
        result = {
            'status': 'success',
            'adapter': 'windows',
            'host_name': host_name,
            'dump_name': dump_name,
            'dump_path': dump_path,
            'parsed_dump': parsed_dump,
            'stdout_preview': stdout_text[:500],
        }
        return result, None

    @staticmethod
    def _run_windows_crash_dump_parse_command(command: list[str], timeout_seconds: int):
        """Execute crash dump metadata command with shell disabled."""
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=False,
        )

    @classmethod
    def _parse_linux_test_double_crash_dump(
        cls,
        host_name: str,
        dump_name: str,
        dump_root: str,
        dump_map: dict[str, str],
    ) -> tuple[dict[str, Any], str | None]:
        """Parse deterministic crash dump metadata for tests/dev on Linux."""
        record_key = f'{host_name}:{dump_name}'
        raw_metadata = str(dump_map.get(record_key, '')).strip()
        parsed_dump = cls._parse_dump_metadata_line(raw_metadata, dump_name, dump_root)

        return {
            'status': 'success',
            'adapter': 'linux_test_double',
            'host_name': host_name,
            'dump_name': dump_name,
            'dump_path': ntpath.join(dump_root, dump_name),
            'parsed_dump': parsed_dump,
        }, None

    @staticmethod
    def _parse_dump_metadata_line(raw_line: str, dump_name: str, dump_root: str) -> dict[str, Any]:
        """Normalize dump metadata into a lightweight parser result."""
        parts = [part.strip() for part in str(raw_line).split('|', 4)] if raw_line else []
        file_name = parts[0] if len(parts) > 0 and parts[0] else dump_name
        try:
            size_bytes = int(parts[1]) if len(parts) > 1 and parts[1] else 0
        except ValueError:
            size_bytes = 0
        last_modified_utc = parts[2] if len(parts) > 2 else ''
        extension = parts[3] if len(parts) > 3 and parts[3] else ntpath.splitext(file_name)[1]
        directory_name = parts[4] if len(parts) > 4 and parts[4] else dump_root

        base_name = ntpath.splitext(file_name)[0]
        normalized_bucket = re.sub(r'[^a-z0-9]+', '-', base_name.lower()).strip('-') or 'unknown-crash'
        primary_module = re.split(r'[-_]', base_name, maxsplit=1)[0] if base_name else 'unknown'
        extension_lower = extension.lower()
        if extension_lower == '.mdmp':
            dump_type = 'minidump'
        elif extension_lower == '.dmp':
            dump_type = 'full_dump'
        else:
            dump_type = 'unknown_dump'

        return {
            'file_name': file_name,
            'size_bytes': size_bytes,
            'last_modified_utc': last_modified_utc,
            'extension': extension,
            'directory_name': directory_name,
            'dump_type': dump_type,
            'primary_module': primary_module,
            'fault_bucket': normalized_bucket,
            'exception_code': 'unknown_exception',
            'parser_version': 'foundation-v1',
        }

    @classmethod
    def _identify_windows_exception(
        cls,
        host_name: str,
        dump_name: str,
        dump_root: str,
        timeout_seconds: int,
    ) -> tuple[dict[str, Any], str | None]:
        """Identify exception from safe PowerShell file-name boundary."""
        dump_path = ntpath.join(dump_root, dump_name)
        command = [
            'powershell.exe',
            '-Command',
            (
                "Get-Item -Path '"
                + dump_path
                + "' | ForEach-Object { \"$($_.Name)\" }"
            ),
        ]
        completed = cls._run_windows_exception_identifier_command(command, timeout_seconds)

        stdout_text = (completed.stdout or '').strip()
        stderr_text = (completed.stderr or '').strip()
        if int(completed.returncode) != 0:
            return {
                'status': 'command_failed',
                'adapter': 'windows',
                'host_name': host_name,
                'dump_name': dump_name,
                'returncode': int(completed.returncode),
                'stderr': stderr_text[:500],
            }, 'command_failed'

        evidence = stdout_text.splitlines()[0].strip() if stdout_text else dump_name
        identified_exception = cls._classify_exception_signature(evidence)
        return {
            'status': 'success',
            'adapter': 'windows',
            'host_name': host_name,
            'dump_name': dump_name,
            'dump_path': dump_path,
            'identified_exception': identified_exception,
            'stdout_preview': stdout_text[:500],
        }, None

    @staticmethod
    def _run_windows_exception_identifier_command(command: list[str], timeout_seconds: int):
        """Execute exception identifier command with shell disabled."""
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=False,
        )

    @classmethod
    def _identify_linux_test_double_exception(
        cls,
        host_name: str,
        dump_name: str,
        dump_root: str,
        exception_map: dict[str, str],
    ) -> tuple[dict[str, Any], str | None]:
        """Identify deterministic exception signature for tests/dev on Linux."""
        record_key = f'{host_name}:{dump_name}'
        raw_exception = str(exception_map.get(record_key, '')).strip()
        identified_exception = cls._parse_exception_test_double(raw_exception, dump_name)
        return {
            'status': 'success',
            'adapter': 'linux_test_double',
            'host_name': host_name,
            'dump_name': dump_name,
            'dump_path': ntpath.join(dump_root, dump_name),
            'identified_exception': identified_exception,
        }, None

    @classmethod
    def _classify_exception_signature(cls, evidence_text: str) -> dict[str, Any]:
        """Map stable evidence text to a known exception signature."""
        normalized = str(evidence_text or '').strip().lower()
        for token, (code, name) in cls.EXCEPTION_SIGNATURES.items():
            if token in normalized:
                return {
                    'exception_code': code,
                    'exception_name': name,
                    'confidence': 'high',
                    'signature_source': 'filename_pattern',
                    'classifier_version': 'foundation-v1',
                }

        return {
            'exception_code': 'unknown_exception',
            'exception_name': 'unknown_exception',
            'confidence': 'low',
            'signature_source': 'filename_pattern',
            'classifier_version': 'foundation-v1',
        }

    @classmethod
    def _parse_exception_test_double(cls, raw_exception: str, dump_name: str) -> dict[str, Any]:
        """Parse deterministic exception payload or fall back to signature classifier."""
        parts = [part.strip() for part in str(raw_exception).split('|', 3)] if raw_exception else []
        if len(parts) >= 4:
            return {
                'exception_code': parts[0],
                'exception_name': parts[1],
                'confidence': parts[2],
                'signature_source': parts[3],
                'classifier_version': 'foundation-v1',
            }

        return cls._classify_exception_signature(dump_name)

    @classmethod
    def _analyze_windows_stack_trace(
        cls,
        host_name: str,
        dump_name: str,
        dump_root: str,
        timeout_seconds: int,
    ) -> tuple[dict[str, Any], str | None]:
        """Analyze stack trace from safe PowerShell dump-name boundary."""
        dump_path = ntpath.join(dump_root, dump_name)
        command = [
            'powershell.exe',
            '-Command',
            (
                "Get-Item -Path '"
                + dump_path
                + "' | ForEach-Object { \"$($_.Name)\" }"
            ),
        ]
        completed = cls._run_windows_stack_trace_command(command, timeout_seconds)

        stdout_text = (completed.stdout or '').strip()
        stderr_text = (completed.stderr or '').strip()
        if int(completed.returncode) != 0:
            return {
                'status': 'command_failed',
                'adapter': 'windows',
                'host_name': host_name,
                'dump_name': dump_name,
                'returncode': int(completed.returncode),
                'stderr': stderr_text[:500],
            }, 'command_failed'

        evidence = stdout_text.splitlines()[0].strip() if stdout_text else dump_name
        analyzed_trace = cls._build_stack_trace_from_evidence(evidence)
        return {
            'status': 'success',
            'adapter': 'windows',
            'host_name': host_name,
            'dump_name': dump_name,
            'dump_path': dump_path,
            'stack_trace': analyzed_trace,
            'stdout_preview': stdout_text[:500],
        }, None

    @staticmethod
    def _run_windows_stack_trace_command(command: list[str], timeout_seconds: int):
        """Execute stack trace command with shell disabled."""
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=False,
        )

    @classmethod
    def _analyze_linux_test_double_stack_trace(
        cls,
        host_name: str,
        dump_name: str,
        dump_root: str,
        stack_map: dict[str, str],
    ) -> tuple[dict[str, Any], str | None]:
        """Analyze deterministic stack trace payload for tests/dev on Linux."""
        record_key = f'{host_name}:{dump_name}'
        raw_trace = str(stack_map.get(record_key, '')).strip()
        analyzed_trace = cls._parse_stack_trace_test_double(raw_trace, dump_name)
        return {
            'status': 'success',
            'adapter': 'linux_test_double',
            'host_name': host_name,
            'dump_name': dump_name,
            'dump_path': ntpath.join(dump_root, dump_name),
            'stack_trace': analyzed_trace,
        }, None

    @classmethod
    def _parse_stack_trace_test_double(cls, raw_trace: str, dump_name: str) -> dict[str, Any]:
        """Parse deterministic stack trace payload or fall back to signature profile."""
        frames = [item.strip() for item in str(raw_trace).split('>') if item.strip()]
        if frames:
            return cls._normalize_stack_frames(frames, source='test_double_trace')
        return cls._build_stack_trace_from_evidence(dump_name)

    @classmethod
    def _build_stack_trace_from_evidence(cls, evidence_text: str) -> dict[str, Any]:
        """Build a lightweight normalized stack trace from evidence text."""
        normalized = str(evidence_text or '').strip().lower()
        for token, frames in cls.STACK_TRACE_PROFILES.items():
            if token in normalized:
                return cls._normalize_stack_frames(frames, source='signature_profile')
        return cls._normalize_stack_frames(
            ['unknown!UnknownFault', 'kernel32!BaseThreadInitThunk'],
            source='signature_profile',
        )

    @staticmethod
    def _normalize_stack_frames(frames: list[str], source: str) -> dict[str, Any]:
        """Return normalized stack trace metadata."""
        normalized_frames = [str(frame).strip() for frame in frames if str(frame).strip()]
        top_frame = normalized_frames[0] if normalized_frames else 'unknown!UnknownFault'
        normalized_signature = ' > '.join(normalized_frames[:5]) if normalized_frames else top_frame
        return {
            'frames': normalized_frames,
            'frame_count': len(normalized_frames),
            'top_frame': top_frame,
            'normalized_signature': normalized_signature,
            'analysis_source': source,
            'analyzer_version': 'foundation-v1',
        }

    @classmethod
    def _score_windows_reliability(
        cls,
        host_name: str,
        timeout_seconds: int,
    ) -> tuple[dict[str, Any], str | None]:
        """Query Windows stability index using Win32_ReliabilityStabilityMetrics."""
        command = [
            'powershell.exe',
            '-Command',
            (
                "Get-CimInstance -ClassName Win32_ReliabilityStabilityMetrics "
                f"-ComputerName '{host_name}' "
                "| Select-Object -First 1 TimeGenerated,SystemStabilityIndex "
                "| ForEach-Object { \"$($_.TimeGenerated)|$($_.SystemStabilityIndex)\" }"
            ),
        ]
        completed = cls._run_windows_reliability_score_command(command, timeout_seconds)

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

        score = cls._parse_reliability_score_line(stdout_text.splitlines()[0] if stdout_text else '')
        result = {
            'status': 'success',
            'adapter': 'windows',
            'host_name': host_name,
            'reliability_score': score,
            'stdout_preview': stdout_text[:500],
        }
        return result, None

    @staticmethod
    def _run_windows_reliability_score_command(command: list[str], timeout_seconds: int):
        """Execute reliability score command with shell disabled."""
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=False,
        )

    @classmethod
    def _score_linux_test_double_reliability(
        cls,
        host_name: str,
        score_map: dict[str, str],
    ) -> tuple[dict[str, Any], str | None]:
        """Resolve deterministic reliability score from Linux test-double map."""
        raw_score = str(score_map.get(host_name, '')).strip()
        score = cls._parse_reliability_score_line(raw_score)
        return {
            'status': 'success',
            'adapter': 'linux_test_double',
            'host_name': host_name,
            'reliability_score': score,
        }, None

    @staticmethod
    def _parse_reliability_score_line(raw_line: str) -> dict[str, Any]:
        """Normalize reliability score payload from windows or test-double text."""
        parts = [part.strip() for part in str(raw_line).split('|', 1)] if raw_line else []
        observed_at = parts[0] if len(parts) > 0 else ''
        try:
            score_value = float(parts[1]) if len(parts) > 1 else 0.0
        except ValueError:
            score_value = 0.0

        score_value = max(0.0, min(score_value, 10.0))
        health_band = ReliabilityService._health_band_for_score(score_value)

        return {
            'current_score': score_value,
            'score_max': 10.0,
            'health_band': health_band,
            'stability_index': score_value,
            'observed_at': observed_at,
            'scorer_version': 'foundation-v1',
        }

    @staticmethod
    def _health_band_for_score(score_value: float) -> str:
        """Map normalized score to health band."""
        if score_value >= 8.5:
            return 'excellent'
        if score_value >= 7.0:
            return 'good'
        if score_value >= 5.0:
            return 'degraded'
        return 'poor'

    @classmethod
    def _analyze_windows_reliability_trend(
        cls,
        host_name: str,
        timeout_seconds: int,
        window_size: int,
    ) -> tuple[dict[str, Any], str | None]:
        """Analyze trend from Win32_ReliabilityStabilityMetrics history."""
        command = [
            'powershell.exe',
            '-Command',
            (
                "Get-CimInstance -ClassName Win32_ReliabilityStabilityMetrics "
                f"-ComputerName '{host_name}' "
                f"| Select-Object -First {window_size} TimeGenerated,SystemStabilityIndex "
                "| ForEach-Object { \"$($_.TimeGenerated)|$($_.SystemStabilityIndex)\" }"
            ),
        ]
        completed = cls._run_windows_reliability_trend_command(command, timeout_seconds)

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

        score_points = cls._parse_reliability_series_lines(stdout_text, window_size)
        trend = cls._compute_trend_summary(score_points)
        return {
            'status': 'success',
            'adapter': 'windows',
            'host_name': host_name,
            'window_size': window_size,
            'trend': trend,
            'stdout_preview': stdout_text[:500],
        }, None

    @staticmethod
    def _run_windows_reliability_trend_command(command: list[str], timeout_seconds: int):
        """Execute reliability trend command with shell disabled."""
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=False,
        )

    @classmethod
    def _analyze_linux_test_double_reliability_trend(
        cls,
        host_name: str,
        trend_map: dict[str, str],
        window_size: int,
    ) -> tuple[dict[str, Any], str | None]:
        """Analyze deterministic reliability trend from Linux test-double map."""
        raw_history = str(trend_map.get(host_name, '')).strip()
        score_points = cls._parse_reliability_series_lines(raw_history, window_size)
        trend = cls._compute_trend_summary(score_points)
        return {
            'status': 'success',
            'adapter': 'linux_test_double',
            'host_name': host_name,
            'window_size': window_size,
            'trend': trend,
        }, None

    @classmethod
    def _predict_windows_reliability(
        cls,
        host_name: str,
        timeout_seconds: int,
        window_size: int,
        prediction_horizon: int,
    ) -> tuple[dict[str, Any], str | None]:
        """Predict reliability from Win32_ReliabilityStabilityMetrics history."""
        command = [
            'powershell.exe',
            '-Command',
            (
                "Get-CimInstance -ClassName Win32_ReliabilityStabilityMetrics "
                f"-ComputerName '{host_name}' "
                f"| Select-Object -First {window_size} TimeGenerated,SystemStabilityIndex "
                "| ForEach-Object { \"$($_.TimeGenerated)|$($_.SystemStabilityIndex)\" }"
            ),
        ]
        completed = cls._run_windows_reliability_prediction_command(command, timeout_seconds)

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

        score_points = cls._parse_reliability_series_lines(stdout_text, window_size)
        prediction = cls._compute_prediction_summary(score_points, prediction_horizon)
        return {
            'status': 'success',
            'adapter': 'windows',
            'host_name': host_name,
            'window_size': window_size,
            'prediction_horizon': prediction_horizon,
            'prediction': prediction,
            'stdout_preview': stdout_text[:500],
        }, None

    @staticmethod
    def _run_windows_reliability_prediction_command(command: list[str], timeout_seconds: int):
        """Execute reliability prediction command with shell disabled."""
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=False,
        )

    @classmethod
    def _predict_linux_test_double_reliability(
        cls,
        host_name: str,
        prediction_map: dict[str, str],
        window_size: int,
        prediction_horizon: int,
    ) -> tuple[dict[str, Any], str | None]:
        """Predict deterministic reliability trend from Linux test-double map."""
        raw_history = str(prediction_map.get(host_name, '')).strip()
        score_points = cls._parse_reliability_series_lines(raw_history, window_size)
        prediction = cls._compute_prediction_summary(score_points, prediction_horizon)
        return {
            'status': 'success',
            'adapter': 'linux_test_double',
            'host_name': host_name,
            'window_size': window_size,
            'prediction_horizon': prediction_horizon,
            'prediction': prediction,
        }, None

    @classmethod
    def _detect_windows_reliability_patterns(
        cls,
        host_name: str,
        timeout_seconds: int,
        window_size: int,
    ) -> tuple[dict[str, Any], str | None]:
        """Detect reliability patterns from Win32_ReliabilityStabilityMetrics history."""
        command = [
            'powershell.exe',
            '-Command',
            (
                "Get-CimInstance -ClassName Win32_ReliabilityStabilityMetrics "
                f"-ComputerName '{host_name}' "
                f"| Select-Object -First {window_size} TimeGenerated,SystemStabilityIndex "
                "| ForEach-Object { \"$($_.TimeGenerated)|$($_.SystemStabilityIndex)\" }"
            ),
        ]
        completed = cls._run_windows_reliability_pattern_command(command, timeout_seconds)

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

        score_points = cls._parse_reliability_series_lines(stdout_text, window_size)
        patterns = cls._compute_pattern_summary(score_points)
        return {
            'status': 'success',
            'adapter': 'windows',
            'host_name': host_name,
            'window_size': window_size,
            'patterns': patterns,
            'stdout_preview': stdout_text[:500],
        }, None

    @staticmethod
    def _run_windows_reliability_pattern_command(command: list[str], timeout_seconds: int):
        """Execute reliability pattern command with shell disabled."""
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=False,
        )

    @classmethod
    def _detect_linux_test_double_reliability_patterns(
        cls,
        host_name: str,
        pattern_map: dict[str, str],
        window_size: int,
    ) -> tuple[dict[str, Any], str | None]:
        """Detect deterministic reliability patterns from Linux test-double map."""
        raw_history = str(pattern_map.get(host_name, '')).strip()
        score_points = cls._parse_reliability_series_lines(raw_history, window_size)
        patterns = cls._compute_pattern_summary(score_points)
        return {
            'status': 'success',
            'adapter': 'linux_test_double',
            'host_name': host_name,
            'window_size': window_size,
            'patterns': patterns,
        }, None

    @classmethod
    def _parse_reliability_series_lines(cls, raw_text: str, window_size: int) -> list[dict[str, Any]]:
        """Parse reliability history lines into bounded score points."""
        points: list[dict[str, Any]] = []
        for raw_line in [line.strip() for line in str(raw_text).splitlines() if line.strip()]:
            parsed = cls._parse_reliability_score_line(raw_line)
            points.append(
                {
                    'observed_at': parsed.get('observed_at') or '',
                    'score': float(parsed.get('current_score', 0.0)),
                }
            )

        if not points and str(raw_text).strip() and '|' in str(raw_text):
            for raw_line in [item.strip() for item in str(raw_text).split(';') if item.strip()]:
                parsed = cls._parse_reliability_score_line(raw_line)
                points.append(
                    {
                        'observed_at': parsed.get('observed_at') or '',
                        'score': float(parsed.get('current_score', 0.0)),
                    }
                )

        return points[:window_size]

    @staticmethod
    def _compute_trend_summary(score_points: list[dict[str, Any]]) -> dict[str, Any]:
        """Compute simple trend metrics from ordered score points."""
        if not score_points:
            return {
                'point_count': 0,
                'direction': 'insufficient_data',
                'slope': 0.0,
                'latest_score': 0.0,
                'delta': 0.0,
                'volatility': 0.0,
                'analysis_version': 'foundation-v1',
            }

        scores = [float(point.get('score', 0.0)) for point in score_points]
        first_score = scores[0]
        last_score = scores[-1]
        delta = last_score - first_score
        denominator = max(1, len(scores) - 1)
        slope = delta / denominator

        if slope > 0.08:
            direction = 'improving'
        elif slope < -0.08:
            direction = 'declining'
        else:
            direction = 'stable'

        mean_score = sum(scores) / len(scores)
        variance = sum((value - mean_score) ** 2 for value in scores) / len(scores)
        volatility = variance ** 0.5

        return {
            'point_count': len(scores),
            'direction': direction,
            'slope': round(slope, 4),
            'latest_score': round(last_score, 2),
            'delta': round(delta, 2),
            'volatility': round(volatility, 4),
            'scores': scores,
            'analysis_version': 'foundation-v1',
        }

    @classmethod
    def _compute_prediction_summary(
        cls,
        score_points: list[dict[str, Any]],
        prediction_horizon: int,
    ) -> dict[str, Any]:
        """Compute lightweight linear reliability forecast summary."""
        trend = cls._compute_trend_summary(score_points)
        if not score_points:
            return {
                'point_count': 0,
                'direction': 'insufficient_data',
                'current_score': 0.0,
                'predicted_score': 0.0,
                'prediction_horizon': prediction_horizon,
                'predicted_health_band': 'poor',
                'confidence': 'low',
                'prediction_version': 'foundation-v1',
            }

        scores = [float(point.get('score', 0.0)) for point in score_points]
        current_score = scores[-1]
        slope = float(trend.get('slope', 0.0))
        predicted_score = current_score + (slope * prediction_horizon)
        predicted_score = max(0.0, min(predicted_score, 10.0))
        predicted_health_band = cls._health_band_for_score(predicted_score)

        volatility = float(trend.get('volatility', 0.0))
        if volatility <= 0.2:
            confidence = 'high'
        elif volatility <= 0.6:
            confidence = 'medium'
        else:
            confidence = 'low'

        return {
            'point_count': len(scores),
            'direction': trend.get('direction', 'stable'),
            'current_score': round(current_score, 2),
            'predicted_score': round(predicted_score, 2),
            'prediction_horizon': prediction_horizon,
            'predicted_health_band': predicted_health_band,
            'confidence': confidence,
            'slope': round(slope, 4),
            'volatility': round(volatility, 4),
            'prediction_version': 'foundation-v1',
        }

    @staticmethod
    def _compute_pattern_summary(score_points: list[dict[str, Any]]) -> dict[str, Any]:
        """Compute lightweight pattern signatures from ordered score points."""
        if len(score_points) < 2:
            return {
                'point_count': len(score_points),
                'primary_pattern': 'insufficient_data',
                'pattern_count': 0,
                'patterns': [],
                'pattern_version': 'foundation-v1',
            }

        scores = [float(point.get('score', 0.0)) for point in score_points]
        deltas = [scores[index + 1] - scores[index] for index in range(len(scores) - 1)]
        patterns: list[dict[str, Any]] = []

        negative_streak = 0
        max_negative_streak = 0
        for delta in deltas:
            if delta <= -0.12:
                negative_streak += 1
                if negative_streak > max_negative_streak:
                    max_negative_streak = negative_streak
            else:
                negative_streak = 0

        if max_negative_streak >= 3:
            patterns.append({
                'pattern_type': 'recurring_degradation',
                'streak_length': max_negative_streak,
                'severity': 'high' if max_negative_streak >= 4 else 'medium',
            })

        alternating_pairs = 0
        for index in range(len(deltas) - 1):
            left = deltas[index]
            right = deltas[index + 1]
            if left == 0 or right == 0:
                continue
            if (left > 0 and right < 0) or (left < 0 and right > 0):
                alternating_pairs += 1

        if alternating_pairs >= 2:
            patterns.append({
                'pattern_type': 'oscillation',
                'alternating_pairs': alternating_pairs,
                'severity': 'medium',
            })

        score_range = max(scores) - min(scores)
        if score_range <= 0.25:
            patterns.append({
                'pattern_type': 'stable_plateau',
                'range': round(score_range, 4),
                'severity': 'low',
            })

        primary_pattern = patterns[0]['pattern_type'] if patterns else 'none_detected'
        return {
            'point_count': len(scores),
            'primary_pattern': primary_pattern,
            'pattern_count': len(patterns),
            'patterns': patterns,
            'latest_score': round(scores[-1], 2),
            'score_range': round(score_range, 4),
            'pattern_version': 'foundation-v1',
        }
