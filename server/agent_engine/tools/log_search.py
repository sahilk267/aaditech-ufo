"""Tool: log_search — search logs via LogService adapter boundary.

Params:
    source_name   (str)           — log source identifier (e.g. "System")
    query_text    (str)           — search query string
    runtime_config (dict)         — forwarded to LogService
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..memory import ShortTermMemory

logger = logging.getLogger(__name__)


class LogSearchTool:
    """Search logs using LogService and store results in memory."""

    @staticmethod
    def run(
        params: dict[str, Any],
        memory: "ShortTermMemory",
        organization_id: int,
        runtime_config: dict[str, Any],
    ) -> tuple[dict[str, Any], str | None]:
        """Return log search results. Returns (result_dict, error_key | None)."""
        from ...services.log_service import LogService

        try:
            source_name = str(params.get("source_name") or "System").strip()
            query_text = str(params.get("query_text") or "error").strip()

            # Build a runtime config that merges engine config with param overrides
            merged_runtime = dict(runtime_config)
            if isinstance(params.get("runtime_config"), dict):
                merged_runtime.update(params["runtime_config"])

            # Default to linux_test_double if not configured
            if not merged_runtime.get("search_adapter"):
                merged_runtime["search_adapter"] = runtime_config.get(
                    "log_search_adapter", "linux_test_double"
                )

            result, error = LogService.search_and_index_logs(
                source_name=source_name,
                query_text=query_text,
                runtime_config=merged_runtime,
            )

            if error:
                return {
                    "status": "error",
                    "tool": "log_search",
                    "source_name": source_name,
                    "query_text": query_text,
                    "error_key": error,
                    "detail": result,
                }, error

            # Cache log results in memory for AI synthesis
            log_entries = result.get("entries") or result.get("results") or []
            memory.set("log_search_results", log_entries)
            memory.set("log_search_query", query_text)
            memory.set("log_search_source", source_name)

            return {
                "status": "success",
                "tool": "log_search",
                "source_name": source_name,
                "query_text": query_text,
                "result": result,
            }, None

        except Exception as exc:
            logger.error("LogSearchTool.run failed: %s", exc)
            return {
                "status": "error",
                "tool": "log_search",
                "error": str(exc)[:300],
            }, "log_search_error"
