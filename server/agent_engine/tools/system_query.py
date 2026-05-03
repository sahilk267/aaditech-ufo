"""Tool: system_query — query recent system metric snapshots from the DB.

Params:
    limit   (int, default 10)  — max number of SystemData rows to fetch
    metric  (str, optional)    — filter by specific metric name
    host    (str, optional)    — filter by hostname
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..memory import ShortTermMemory

logger = logging.getLogger(__name__)


class SystemQueryTool:
    """Query recent system metrics from the SystemData table."""

    @staticmethod
    def run(
        params: dict[str, Any],
        memory: "ShortTermMemory",
        organization_id: int,
        runtime_config: dict[str, Any],
    ) -> tuple[dict[str, Any], str | None]:
        """Return recent metric snapshots for the tenant.

        Returns (result_dict, error_key | None).
        """
        from ...models import SystemData

        try:
            limit = max(1, min(int(params.get("limit") or 10), 100))
            metric_filter = str(params.get("metric") or "").strip() or None
            host_filter = str(params.get("host") or "").strip() or None

            query = SystemData.query.filter_by(organization_id=organization_id)

            if host_filter:
                query = query.filter(SystemData.hostname == host_filter)

            rows = (
                query.order_by(SystemData.last_update.desc())
                .limit(limit)
                .all()
            )

            snapshots: list[dict[str, Any]] = []
            for row in rows:
                snap: dict[str, Any] = {
                    "id": row.id,
                    "hostname": getattr(row, "hostname", None),
                    "timestamp": row.last_update.isoformat() if row.last_update else None,
                    "cpu_usage": getattr(row, "cpu_usage", None),
                    "ram_usage": getattr(row, "ram_usage", None),
                    "storage_usage": getattr(row, "storage_usage", None),
                    "overall_benchmark": getattr(row, "overall_benchmark", None),
                    "software_benchmark": getattr(row, "software_benchmark", None),
                    "hardware_benchmark": getattr(row, "hardware_benchmark", None),
                }
                if metric_filter and metric_filter in snap:
                    snapshots.append({
                        "hostname": snap["hostname"],
                        "timestamp": snap["timestamp"],
                        metric_filter: snap.get(metric_filter),
                    })
                else:
                    snapshots.append(snap)

            # Store in memory so downstream steps can reference it
            memory.set("system_snapshots", snapshots)
            memory.set("system_snapshot_count", len(snapshots))

            # Compute lightweight aggregates for the AI synthesizer
            cpu_values = [s["cpu_usage"] for s in snapshots if s.get("cpu_usage") is not None]
            ram_values = [s["ram_usage"] for s in snapshots if s.get("ram_usage") is not None]

            aggregates: dict[str, Any] = {}
            if cpu_values:
                aggregates["cpu_avg"] = round(sum(cpu_values) / len(cpu_values), 2)
                aggregates["cpu_max"] = round(max(cpu_values), 2)
            if ram_values:
                aggregates["ram_avg"] = round(sum(ram_values) / len(ram_values), 2)
                aggregates["ram_max"] = round(max(ram_values), 2)

            return {
                "status": "success",
                "tool": "system_query",
                "count": len(snapshots),
                "limit": limit,
                "metric_filter": metric_filter,
                "host_filter": host_filter,
                "snapshots": snapshots,
                "aggregates": aggregates,
            }, None

        except Exception as exc:
            logger.error("SystemQueryTool.run failed: %s", exc)
            return {
                "status": "error",
                "tool": "system_query",
                "error": str(exc)[:300],
            }, "system_query_error"
