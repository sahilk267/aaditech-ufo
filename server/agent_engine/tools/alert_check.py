"""Tool: alert_check — query active alert rules and evaluate recent metrics.

Params:
    metric  (str, optional)  — filter rules by metric name
    limit   (int, default 20) — max rules to return
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..memory import ShortTermMemory

logger = logging.getLogger(__name__)


class AlertCheckTool:
    """Query AlertRule table and evaluate current system metrics against thresholds."""

    @staticmethod
    def run(
        params: dict[str, Any],
        memory: "ShortTermMemory",
        organization_id: int,
        runtime_config: dict[str, Any],
    ) -> tuple[dict[str, Any], str | None]:
        """Return active alert rules and any current threshold breaches.

        Returns (result_dict, error_key | None).
        """
        from ...models import AlertRule, SystemData

        try:
            limit = max(1, min(int(params.get("limit") or 20), 100))
            metric_filter = str(params.get("metric") or "").strip() or None

            query = AlertRule.query.filter_by(
                organization_id=organization_id,
                is_active=True,
            )
            if metric_filter:
                query = query.filter(AlertRule.metric == metric_filter)

            rules = query.order_by(AlertRule.created_at.desc()).limit(limit).all()
            rules_data = [r.to_dict() for r in rules]

            # Evaluate rules against the most recent system snapshot
            latest_row = (
                SystemData.query
                .filter_by(organization_id=organization_id)
                .order_by(SystemData.timestamp.desc())
                .first()
            )

            breaches: list[dict[str, Any]] = []
            if latest_row:
                metric_values: dict[str, float | None] = {
                    "cpu_usage": getattr(latest_row, "cpu_usage", None),
                    "ram_usage": getattr(latest_row, "ram_usage", None),
                    "storage_usage": getattr(latest_row, "storage_usage", None),
                    "software_benchmark": getattr(latest_row, "software_benchmark", None),
                    "hardware_benchmark": getattr(latest_row, "hardware_benchmark", None),
                    "overall_benchmark": getattr(latest_row, "overall_benchmark", None),
                }

                for rule in rules:
                    current_value = metric_values.get(rule.metric)
                    if current_value is None:
                        continue
                    if _evaluate_threshold(current_value, rule.operator, rule.threshold):
                        breaches.append({
                            "rule_id": rule.id,
                            "rule_name": rule.name,
                            "metric": rule.metric,
                            "operator": rule.operator,
                            "threshold": rule.threshold,
                            "current_value": current_value,
                            "severity": rule.severity,
                        })

            # Store findings in memory for downstream steps
            memory.set("alert_rules", rules_data)
            memory.set("alert_breaches", breaches)
            memory.set("alert_breach_count", len(breaches))

            return {
                "status": "success",
                "tool": "alert_check",
                "rule_count": len(rules_data),
                "breach_count": len(breaches),
                "metric_filter": metric_filter,
                "rules": rules_data,
                "breaches": breaches,
                "latest_snapshot_host": getattr(latest_row, "hostname", None),
            }, None

        except Exception as exc:
            logger.error("AlertCheckTool.run failed: %s", exc)
            return {
                "status": "error",
                "tool": "alert_check",
                "error": str(exc)[:300],
            }, "alert_check_error"


def _evaluate_threshold(value: float, operator: str, threshold: float) -> bool:
    """Evaluate *value* against *threshold* using *operator*. Safe."""
    try:
        ops = {
            ">": value > threshold,
            ">=": value >= threshold,
            "<": value < threshold,
            "<=": value <= threshold,
            "==": abs(value - threshold) < 1e-9,
            "!=": abs(value - threshold) >= 1e-9,
        }
        return ops.get(operator, False)
    except Exception:
        return False
