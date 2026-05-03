"""Tool: automation_trigger — execute or dry-run an AutomationWorkflow.

Params:
    workflow_id (int | None)   — target workflow; if None, lists available ones
    dry_run     (bool, True)   — must be explicitly False to live-execute
    runtime_config (dict)      — forwarded to AutomationService
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..memory import ShortTermMemory

logger = logging.getLogger(__name__)


class AutomationTriggerTool:
    """Trigger an AutomationWorkflow via AutomationService."""

    @staticmethod
    def run(
        params: dict[str, Any],
        memory: "ShortTermMemory",
        organization_id: int,
        runtime_config: dict[str, Any],
    ) -> tuple[dict[str, Any], str | None]:
        """Execute or list workflows. Returns (result_dict, error_key | None)."""
        from ...services.automation_service import AutomationService
        from ...models import AutomationWorkflow

        try:
            workflow_id_raw = params.get("workflow_id")
            dry_run = bool(params.get("dry_run", True))

            # If no workflow_id supplied, list the first 10 active workflows
            if workflow_id_raw is None:
                workflows = (
                    AutomationWorkflow.query
                    .filter_by(organization_id=organization_id, is_active=True)
                    .order_by(AutomationWorkflow.created_at.desc())
                    .limit(10)
                    .all()
                )
                listing = [w.to_dict() for w in workflows]
                memory.set("available_workflows", listing)
                return {
                    "status": "success",
                    "tool": "automation_trigger",
                    "mode": "list",
                    "workflow_count": len(listing),
                    "workflows": listing,
                }, None

            workflow_id = int(workflow_id_raw)

            # Merge any runtime_config from params with base runtime_config
            merged_runtime = dict(runtime_config)
            if isinstance(params.get("runtime_config"), dict):
                merged_runtime.update(params["runtime_config"])

            result, error_key = AutomationService.execute_workflow(
                organization_id=organization_id,
                workflow_id=workflow_id,
                payload=params.get("payload") or {},
                dry_run=dry_run,
                runtime_config=merged_runtime,
                execution_context={"trigger_source": "agent_engine"},
            )

            if error_key:
                return {
                    "status": "error",
                    "tool": "automation_trigger",
                    "workflow_id": workflow_id,
                    "dry_run": dry_run,
                    "error_key": error_key,
                }, error_key

            memory.set(f"workflow_{workflow_id}_result", result)

            return {
                "status": "success",
                "tool": "automation_trigger",
                "workflow_id": workflow_id,
                "dry_run": dry_run,
                "result": result,
            }, None

        except Exception as exc:
            logger.error("AutomationTriggerTool.run failed: %s", exc)
            return {
                "status": "error",
                "tool": "automation_trigger",
                "error": str(exc)[:300],
            }, "automation_trigger_error"
