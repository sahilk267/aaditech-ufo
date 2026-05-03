"""Tool: remote_exec — run a remote command via RemoteExecutorService.

Params:
    host           (str)   — target hostname
    command        (str)   — command to execute (must pass allowlist)
    runtime_config (dict)  — forwarded to RemoteExecutorService
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..memory import ShortTermMemory

logger = logging.getLogger(__name__)


class RemoteExecTool:
    """Execute a remote command through the RemoteExecutorService boundary."""

    @staticmethod
    def run(
        params: dict[str, Any],
        memory: "ShortTermMemory",
        organization_id: int,
        runtime_config: dict[str, Any],
    ) -> tuple[dict[str, Any], str | None]:
        """Execute a remote command. Returns (result_dict, error_key | None)."""
        from ...services.remote_executor_service import RemoteExecutorService

        try:
            host = str(params.get("host") or "").strip()
            command = str(params.get("command") or "").strip()

            if not host:
                return {
                    "status": "error",
                    "tool": "remote_exec",
                    "error": "host parameter is required",
                }, "remote_exec_host_missing"

            if not command:
                return {
                    "status": "error",
                    "tool": "remote_exec",
                    "error": "command parameter is required",
                }, "remote_exec_command_missing"

            # Merge runtime configs
            merged_runtime = dict(runtime_config)
            if isinstance(params.get("runtime_config"), dict):
                merged_runtime.update(params["runtime_config"])

            # Default to linux_test_double adapter
            if not merged_runtime.get("ssh_adapter"):
                merged_runtime["ssh_adapter"] = runtime_config.get(
                    "remote_exec_adapter", "linux_test_double"
                )

            result, error = RemoteExecutorService.execute_remote_command(
                host=host,
                command=command,
                runtime_config=merged_runtime,
            )

            if error:
                return {
                    "status": "error",
                    "tool": "remote_exec",
                    "host": host,
                    "command": command,
                    "error_key": error,
                    "detail": result,
                }, error

            memory.set(f"remote_exec_{host}", result)

            return {
                "status": "success",
                "tool": "remote_exec",
                "host": host,
                "command": command,
                "result": result,
            }, None

        except Exception as exc:
            logger.error("RemoteExecTool.run failed: %s", exc)
            return {
                "status": "error",
                "tool": "remote_exec",
                "error": str(exc)[:300],
            }, "remote_exec_error"
