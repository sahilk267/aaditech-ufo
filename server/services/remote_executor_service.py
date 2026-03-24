"""Remote SSH command execution service with allowlist boundary.

Phase 2 Week 15-16 — Remote Command Execution.
Adapter pattern: 'ssh' (real) | 'linux_test_double' (deterministic CI).
Security: all hosts and commands must pass allowlist checks before execution.
"""

from __future__ import annotations

import re
import subprocess
from typing import Any


class RemoteExecutorService:
    """Execute commands on remote hosts via SSH with allowlist enforcement."""

    ALLOWED_SSH_ADAPTERS = {'ssh', 'linux_test_double'}
    # Hosts: alphanumeric, dots, hyphens — standard hostname/IP pattern
    SAFE_HOST_PATTERN = re.compile(r'^[a-zA-Z0-9._-]{1,253}$')
    # Commands: printable ASCII minus shell-meta characters ( ; & | $ ` > < ! {} )
    SAFE_COMMAND_PATTERN = re.compile(r'^[a-zA-Z0-9 _./@=\-]+$')
    MAX_COMMAND_LENGTH = 512
    MAX_HOST_LENGTH = 253

    @classmethod
    def execute_remote_command(
        cls,
        host: str,
        command: str,
        runtime_config: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], str | None]:
        """Execute *command* on *host* via SSH (or test-double).

        Returns ``(result_dict, error_key|None)``.
        """
        runtime_config = runtime_config or {}

        # --- validate host ---
        host = str(host or '').strip()
        if not host:
            return {'status': 'validation_failed', 'reason': 'host_missing'}, 'host_missing'
        if len(host) > cls.MAX_HOST_LENGTH or not cls.SAFE_HOST_PATTERN.fullmatch(host):
            return {'status': 'policy_blocked', 'reason': 'host_invalid'}, 'host_invalid'

        # --- host allowlist ---
        allowed_hosts_raw = runtime_config.get('allowed_hosts') or []
        if isinstance(allowed_hosts_raw, str):
            allowed_hosts = {h.strip() for h in allowed_hosts_raw.split(',') if h.strip()}
        else:
            allowed_hosts = {str(h).strip() for h in allowed_hosts_raw if str(h).strip()}
        if allowed_hosts and host not in allowed_hosts:
            return {
                'status': 'policy_blocked',
                'reason': 'host_not_allowlisted',
                'host': host,
            }, 'host_not_allowlisted'

        # --- validate command ---
        command = str(command or '').strip()
        if not command:
            return {'status': 'validation_failed', 'reason': 'command_missing'}, 'command_missing'
        if len(command) > cls.MAX_COMMAND_LENGTH:
            return {'status': 'policy_blocked', 'reason': 'command_too_long'}, 'command_too_long'
        if not cls.SAFE_COMMAND_PATTERN.fullmatch(command):
            return {'status': 'policy_blocked', 'reason': 'command_unsafe_chars'}, 'command_unsafe_chars'

        # --- command allowlist ---
        allowed_commands_raw = runtime_config.get('allowed_commands') or []
        if isinstance(allowed_commands_raw, str):
            allowed_commands = {c.strip() for c in allowed_commands_raw.split(',') if c.strip()}
        else:
            allowed_commands = {str(c).strip() for c in allowed_commands_raw if str(c).strip()}
        if allowed_commands and command not in allowed_commands:
            return {
                'status': 'policy_blocked',
                'reason': 'command_not_allowlisted',
                'command': command[:200],
            }, 'command_not_allowlisted'

        # --- adapter routing ---
        adapter = str(runtime_config.get('ssh_adapter') or 'linux_test_double').strip()
        if adapter not in cls.ALLOWED_SSH_ADAPTERS:
            return {'status': 'policy_blocked', 'reason': 'adapter_not_allowed'}, 'adapter_not_allowed'

        timeout_seconds = runtime_config.get('ssh_timeout_seconds', 10)
        try:
            timeout_seconds = int(timeout_seconds)
        except (TypeError, ValueError):
            timeout_seconds = 10
        timeout_seconds = max(1, min(timeout_seconds, 60))

        if adapter == 'ssh':
            return cls._execute_ssh_command(host, command, timeout_seconds, runtime_config)

        # linux_test_double
        command_outputs = runtime_config.get('linux_test_double_remote_commands') or {}
        return cls._execute_linux_test_double(host, command, command_outputs)

    @classmethod
    def _execute_ssh_command(
        cls,
        host: str,
        command: str,
        timeout_seconds: int,
        runtime_config: dict[str, Any],
    ) -> tuple[dict[str, Any], str | None]:
        """Execute via real SSH subprocess boundary."""
        ssh_user = str(runtime_config.get('ssh_user') or 'root').strip()
        ssh_port = int(runtime_config.get('ssh_port', 22))
        key_path = str(runtime_config.get('ssh_key_path') or '').strip()

        cmd = ['ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'BatchMode=yes',
               '-p', str(ssh_port)]
        if key_path:
            cmd += ['-i', key_path]
        cmd += [f"{ssh_user}@{host}", command]

        completed = cls._run_ssh_subprocess(cmd, timeout_seconds)
        stdout_text = (completed.stdout or '').strip()
        stderr_text = (completed.stderr or '').strip()
        is_success = int(completed.returncode) == 0
        return {
            'status': 'success' if is_success else 'command_failed',
            'adapter': 'ssh',
            'host': host,
            'command': command[:200],
            'returncode': int(completed.returncode),
            'stdout': stdout_text[:500],
            'stderr': stderr_text[:500],
        }, None if is_success else 'command_failed'

    @staticmethod
    def _run_ssh_subprocess(command: list[str], timeout_seconds: int):
        """SSH subprocess boundary — isolated for mocking in tests."""
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=False,
        )

    @staticmethod
    def _execute_linux_test_double(
        host: str,
        command: str,
        command_outputs: dict[str, Any],
    ) -> tuple[dict[str, Any], str | None]:
        """Resolve output from deterministic test-double map keyed by ``host:command``."""
        key = f"{host}:{command}"
        raw_output = command_outputs.get(key, '')

        if isinstance(raw_output, dict):
            output_data = raw_output
        else:
            output_data = {
                'returncode': 0,
                'stdout': str(raw_output),
                'stderr': '',
            }

        return {
            'status': 'success',
            'adapter': 'linux_test_double',
            'host': host,
            'command': command[:200],
            'returncode': int(output_data.get('returncode', 0)),
            'stdout': str(output_data.get('stdout', ''))[:500],
            'stderr': str(output_data.get('stderr', ''))[:500],
            'source': 'configured_test_double',
        }, None
