"""Tool: automation_trigger — execute or dry-run an AutomationWorkflow.

Params:
    workflow_id    (int | None)  — target workflow; if None, lists available ones
    dry_run        (bool, True)  — step-level dry-run flag (see guard hierarchy)
    payload        (dict)        — forwarded to execute_workflow in live mode
    runtime_config (dict)        — merged with base runtime_config if provided

Dry-run guard hierarchy
-----------------------
The tool enforces a two-level guard so that a live workflow execution can
never be triggered accidentally through the agent engine:

  1. Orchestrator-level guard  — runtime_config["dry_run"] is True
     Set by the blueprint from the POST /run request body.  Wins over
     everything.  dry_run_guard = "orchestrator".

  2. Step-level guard          — params["dry_run"] is True (default)
     Set by the Planner in the step's params dict.  Applies when the
     orchestrator-level flag is False.  dry_run_guard = "step_params".

  3. Live execution            — both guards are False
     Calls AutomationService.execute_workflow and tags the result with
     live_execution = True.

Dry-run preview (when either guard fires)
-----------------------------------------
Instead of calling AutomationService, the tool:
  - Fetches the AutomationWorkflow record from the DB
  - Returns a structured "would_trigger" preview containing:
      workflow_id, workflow_name, trigger_type, action_type,
      action_config_preview (secrets redacted),
      estimated_impact (human-readable description of the action),
      would_update_last_triggered_at (always False in dry-run),
      payload_preview, dry_run_guard
  This makes the effect of the step visible to the operator and to
  downstream ai_analysis steps without performing any real work.

List mode (workflow_id is None)
--------------------------------
Returns the first 10 active workflows for the tenant with their key
fields, plus a dry_run_mode flag.  Never calls execute_workflow.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..memory import ShortTermMemory

logger = logging.getLogger(__name__)

# Keys in action_config that may contain secrets and must be redacted in previews.
_SENSITIVE_KEYS: frozenset[str] = frozenset({
    "token", "secret", "password", "passwd", "api_key", "apikey",
    "auth", "authorization", "credential", "private_key", "signing_key",
})

# Human-readable impact description by action_type.
_IMPACT_BY_ACTION_TYPE: dict[str, str] = {
    "service_restart": (
        "Will restart the named system service via systemctl; "
        "causes a brief service interruption."
    ),
    "script_execute": (
        "Will execute the configured shell script on the target host; "
        "side-effects depend on script content."
    ),
    "webhook_call": (
        "Will send an HTTP POST request to the configured URL; "
        "triggers an external system action."
    ),
}
_IMPACT_UNKNOWN = "Will execute the configured action (action_type not recognised)."


class AutomationTriggerTool:
    """Trigger an AutomationWorkflow via AutomationService, with a dry-run guard."""

    @staticmethod
    def run(
        params: dict[str, Any],
        memory: "ShortTermMemory",
        organization_id: int,
        runtime_config: dict[str, Any],
    ) -> tuple[dict[str, Any], str | None]:
        """Execute or dry-run an automation workflow.

        Returns (result_dict, error_key | None).  Never raises.
        """
        from ...models import AutomationWorkflow
        from ...services.automation_service import AutomationService

        try:
            workflow_id_raw = params.get("workflow_id")

            # ── List mode (no workflow_id) ─────────────────────────────── #
            if workflow_id_raw is None:
                return AutomationTriggerTool._list_workflows(
                    organization_id, runtime_config, memory
                )

            workflow_id = int(workflow_id_raw)

            # ── Resolve dry-run guard (orchestrator wins) ─────────────── #
            orch_dry_run = bool(runtime_config.get("dry_run", True))
            step_dry_run = bool(params.get("dry_run", True))

            if orch_dry_run:
                dry_run_active = True
                dry_run_guard: str = "orchestrator"
            elif step_dry_run:
                dry_run_active = True
                dry_run_guard = "step_params"
            else:
                dry_run_active = False
                dry_run_guard = "none"

            logger.info(
                "AutomationTriggerTool: workflow_id=%d  dry_run_active=%s  guard=%s  org=%d",
                workflow_id, dry_run_active, dry_run_guard, organization_id,
            )

            # ── Dry-run path: preview without executing ────────────────── #
            if dry_run_active:
                return AutomationTriggerTool._dry_run_preview(
                    workflow_id=workflow_id,
                    organization_id=organization_id,
                    dry_run_guard=dry_run_guard,
                    payload=params.get("payload") or {},
                    memory=memory,
                )

            # ── Live execution path ────────────────────────────────────── #
            merged_runtime = dict(runtime_config)
            if isinstance(params.get("runtime_config"), dict):
                merged_runtime.update(params["runtime_config"])

            result, error_key = AutomationService.execute_workflow(
                organization_id=organization_id,
                workflow_id=workflow_id,
                payload=params.get("payload") or {},
                dry_run=False,
                runtime_config=merged_runtime,
                execution_context={"trigger_source": "agent_engine"},
            )

            if error_key:
                logger.error(
                    "AutomationTriggerTool: live execute failed: %s (workflow=%d org=%d)",
                    error_key, workflow_id, organization_id,
                )
                return {
                    "status": "error",
                    "tool": "automation_trigger",
                    "workflow_id": workflow_id,
                    "dry_run": False,
                    "live_execution": True,
                    "error_key": error_key,
                }, error_key

            memory.set(f"workflow_{workflow_id}_result", result)
            return {
                "status": "success",
                "tool": "automation_trigger",
                "workflow_id": workflow_id,
                "dry_run": False,
                "live_execution": True,
                "result": result,
            }, None

        except Exception as exc:
            logger.error("AutomationTriggerTool.run failed: %s", exc)
            return {
                "status": "error",
                "tool": "automation_trigger",
                "error": str(exc)[:300],
            }, "automation_trigger_error"

    # ------------------------------------------------------------------ #
    # Dry-run preview                                                      #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _dry_run_preview(
        workflow_id: int,
        organization_id: int,
        dry_run_guard: str,
        payload: dict[str, Any],
        memory: "ShortTermMemory",
    ) -> tuple[dict[str, Any], str | None]:
        """Fetch the workflow record and return a rich would_trigger preview.

        Never calls AutomationService.  Returns (result_dict, None).
        Returns an error dict if the workflow is not found or inactive.
        """
        from ...models import AutomationWorkflow

        workflow = AutomationWorkflow.query.filter_by(
            id=workflow_id,
            organization_id=organization_id,
        ).first()

        if workflow is None:
            logger.warning(
                "AutomationTriggerTool: dry-run preview — workflow %d not found for org %d",
                workflow_id, organization_id,
            )
            result = {
                "status": "error",
                "tool": "automation_trigger",
                "dry_run": True,
                "dry_run_guard": dry_run_guard,
                "would_trigger": False,
                "workflow_id": workflow_id,
                "error": "Workflow not found or does not belong to this organisation.",
            }
            memory.set(f"workflow_{workflow_id}_preview", result)
            return result, "workflow_not_found"

        action_config: dict[str, Any] = workflow.action_config or {}
        action_type: str = str(workflow.action_type or "unknown")

        preview = {
            "status": "success",
            "tool": "automation_trigger",
            "dry_run": True,
            "dry_run_guard": dry_run_guard,
            "would_trigger": True,
            "live_execution": False,
            "would_update_last_triggered_at": False,
            # Workflow identity
            "workflow_id": workflow.id,
            "workflow_name": workflow.name,
            "trigger_type": workflow.trigger_type,
            "action_type": action_type,
            "is_active": workflow.is_active,
            # Human-readable impact statement
            "estimated_impact": _IMPACT_BY_ACTION_TYPE.get(action_type, _IMPACT_UNKNOWN),
            # Sanitised config — secrets redacted
            "action_config_preview": AutomationTriggerTool._redact_config(action_config),
            # Payload that would be forwarded to execute_workflow
            "payload_preview": payload,
            # Timestamps for operator awareness
            "last_triggered_at": (
                workflow.last_triggered_at.isoformat()
                if workflow.last_triggered_at else None
            ),
        }

        memory.set(f"workflow_{workflow_id}_preview", preview)
        logger.info(
            "AutomationTriggerTool: dry-run preview built for workflow '%s' "
            "(id=%d  guard=%s  impact=%r)",
            workflow.name, workflow_id, dry_run_guard, preview["estimated_impact"],
        )
        return preview, None

    # ------------------------------------------------------------------ #
    # List mode                                                            #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _list_workflows(
        organization_id: int,
        runtime_config: dict[str, Any],
        memory: "ShortTermMemory",
    ) -> tuple[dict[str, Any], str | None]:
        """Return the first 10 active workflows for the tenant."""
        from ...models import AutomationWorkflow

        workflows = (
            AutomationWorkflow.query
            .filter_by(organization_id=organization_id, is_active=True)
            .order_by(AutomationWorkflow.created_at.desc())
            .limit(10)
            .all()
        )
        listing = [w.to_dict() for w in workflows]
        orch_dry_run = bool(runtime_config.get("dry_run", True))
        memory.set("available_workflows", listing)
        return {
            "status": "success",
            "tool": "automation_trigger",
            "mode": "list",
            "dry_run_mode": orch_dry_run,
            "workflow_count": len(listing),
            "workflows": listing,
        }, None

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _redact_config(config: dict[str, Any]) -> dict[str, Any]:
        """Return a copy of config with sensitive values replaced by '***REDACTED***'."""
        redacted: dict[str, Any] = {}
        for key, value in config.items():
            if key.lower() in _SENSITIVE_KEYS:
                redacted[key] = "***REDACTED***"
            elif isinstance(value, dict):
                redacted[key] = AutomationTriggerTool._redact_config(value)
            else:
                redacted[key] = value
        return redacted
