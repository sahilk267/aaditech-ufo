"""Tool: ai_analysis — call AIService methods for analysis and recommendations.

Params:
    mode             (str)        — "root_cause" | "recommendations" | "troubleshoot"
    symptom_summary  (str)        — brief description of the problem (root_cause / recommendations)
    probable_cause   (str)        — probable cause string (recommendations mode)
    evidence_points  (list[str])  — supporting evidence items
    question         (str)        — operator question (troubleshoot mode)
    context_items    (list[str])  — context list (troubleshoot mode)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..memory import ShortTermMemory

logger = logging.getLogger(__name__)

_VALID_MODES = frozenset({"root_cause", "recommendations", "troubleshoot"})


class AIAnalysisTool:
    """Run AIService analysis and store the result in memory."""

    @staticmethod
    def run(
        params: dict[str, Any],
        memory: "ShortTermMemory",
        organization_id: int,
        runtime_config: dict[str, Any],
    ) -> tuple[dict[str, Any], str | None]:
        """Route to the correct AIService method. Returns (result, error | None)."""
        from ...services.ai_service import AIService

        mode = str(params.get("mode") or "troubleshoot").strip()
        if mode not in _VALID_MODES:
            return {
                "status": "error",
                "tool": "ai_analysis",
                "error": f"unknown mode: {mode}",
            }, "ai_analysis_invalid_mode"

        try:
            if mode == "root_cause":
                return AIAnalysisTool._root_cause(params, memory, runtime_config, AIService)
            if mode == "recommendations":
                return AIAnalysisTool._recommendations(params, memory, runtime_config, AIService)
            return AIAnalysisTool._troubleshoot(params, memory, runtime_config, AIService)

        except Exception as exc:
            logger.error("AIAnalysisTool.run failed: %s", exc)
            return {
                "status": "error",
                "tool": "ai_analysis",
                "mode": mode,
                "error": str(exc)[:300],
            }, "ai_analysis_error"

    # ------------------------------------------------------------------ #
    # Mode handlers                                                        #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _root_cause(
        params: dict[str, Any],
        memory: "ShortTermMemory",
        runtime_config: dict[str, Any],
        AIService: Any,
    ) -> tuple[dict[str, Any], str | None]:
        symptom_summary = str(params.get("symptom_summary") or "").strip()
        if not symptom_summary:
            # Pull from memory if available
            snapshots = memory.get("system_snapshots") or []
            if snapshots:
                snap = snapshots[0]
                cpu = snap.get("cpu_usage")
                ram = snap.get("ram_usage")
                symptom_summary = f"System metrics: CPU={cpu}%, RAM={ram}%" if cpu or ram else "System anomaly detected"
            else:
                symptom_summary = "System anomaly requiring investigation"

        evidence_points = list(params.get("evidence_points") or [])
        # Enrich evidence from memory
        aggregates = memory.get("system_snapshots")
        if aggregates and isinstance(aggregates, list):
            for snap in aggregates[:3]:
                cpu = snap.get("cpu_usage")
                ram = snap.get("ram_usage")
                host = snap.get("hostname", "unknown")
                if cpu is not None:
                    evidence_points.append(f"{host}: CPU={cpu}%")
                if ram is not None:
                    evidence_points.append(f"{host}: RAM={ram}%")

        if not evidence_points:
            evidence_points = ["No direct evidence available — analysis based on symptoms"]

        result, error = AIService.analyze_root_cause(
            symptom_summary=symptom_summary,
            evidence_points=evidence_points[:8],
            runtime_config=runtime_config,
        )
        memory.set("ai_root_cause", result.get("root_cause") or {})
        return {
            "status": "success" if not error else "error",
            "tool": "ai_analysis",
            "mode": "root_cause",
            "result": result,
            "error": error,
        }, error

    @staticmethod
    def _recommendations(
        params: dict[str, Any],
        memory: "ShortTermMemory",
        runtime_config: dict[str, Any],
        AIService: Any,
    ) -> tuple[dict[str, Any], str | None]:
        symptom_summary = str(params.get("symptom_summary") or "System anomaly detected").strip()
        probable_cause = str(
            params.get("probable_cause")
            or (memory.get("ai_root_cause") or {}).get("probable_cause")
            or "Root cause under investigation"
        ).strip()
        evidence_points = list(params.get("evidence_points") or [])

        result, error = AIService.generate_recommendations(
            symptom_summary=symptom_summary,
            probable_cause=probable_cause,
            evidence_points=evidence_points[:8],
            runtime_config=runtime_config,
        )
        memory.set("ai_recommendations", result.get("recommendations") or {})
        return {
            "status": "success" if not error else "error",
            "tool": "ai_analysis",
            "mode": "recommendations",
            "result": result,
            "error": error,
        }, error

    @staticmethod
    def _troubleshoot(
        params: dict[str, Any],
        memory: "ShortTermMemory",
        runtime_config: dict[str, Any],
        AIService: Any,
    ) -> tuple[dict[str, Any], str | None]:
        question = str(params.get("question") or "What should I investigate first?").strip()
        context_items = list(params.get("context_items") or [])

        # Enrich context from memory
        step_outputs = memory.get_step_outputs()
        for step in step_outputs[-4:]:
            desc = step.get("description", "")
            if desc:
                context_items.append(desc)

        result, error = AIService.assist_troubleshooting(
            question=question,
            context_items=context_items[:10],
            runtime_config=runtime_config,
        )
        memory.set("ai_guidance", result.get("guidance") or {})
        return {
            "status": "success" if not error else "error",
            "tool": "ai_analysis",
            "mode": "troubleshoot",
            "result": result,
            "error": error,
        }, error
