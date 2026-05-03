"""Tool: ai_analysis — call AIService methods for analysis and recommendations.

Params:
    mode             (str)        — "root_cause" | "recommendations" | "troubleshoot"
    symptom_summary  (str)        — brief description of the problem (root_cause / recommendations)
    probable_cause   (str)        — probable cause string (recommendations mode)
    evidence_points  (list[str])  — supporting evidence items (merged with upstream)
    question         (str)        — operator question (troubleshoot mode)
    context_items    (list[str])  — context list (troubleshoot mode, merged with upstream)
    upstream_results (list[dict]) — injected by the Executor from depends_on steps;
                                    each dict has: step_index, tool, description, status, result

Upstream evidence extraction:
    When upstream_results is present (i.e. this step depends_on others),
    _extract_upstream_evidence() unpacks each upstream result and adds
    structured findings to evidence_points / context_items:
      - system_query  → per-host CPU/RAM lines + aggregate summary
      - log_search    → log entry messages/sources
      - alert_check   → violated rule names and breached metrics
      - remote_exec   → stdout/stderr excerpt
    This ensures the AI synthesis call is grounded in the actual data
    collected by preceding steps rather than relying on operator-supplied
    static strings.
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
    # Upstream evidence extraction                                         #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _extract_upstream_evidence(
        params: dict[str, Any],
        memory: "ShortTermMemory",
    ) -> tuple[list[str], list[str]]:
        """Build evidence_points and context_items from upstream_results.

        Returns (evidence_points, context_items) — both are plain string lists
        suitable for the AIService calls.

        Sources (in priority order):
          1. params["upstream_results"]  — injected by Executor from depends_on
          2. ShortTermMemory             — written by each tool after its run
        """
        evidence: list[str] = []
        context: list[str] = []

        upstream_results: list[dict[str, Any]] = list(
            params.get("upstream_results") or []
        )

        for item in upstream_results:
            tool = str(item.get("tool") or "")
            status = str(item.get("status") or "unknown")
            result = item.get("result") or {}
            desc = str(item.get("description") or tool)

            if status != "success" or not result:
                context.append(f"[{tool}] {desc} — {status} (no usable data)")
                continue

            # ── system_query ──────────────────────────────────────────── #
            if tool == "system_query":
                aggs = result.get("aggregates") or {}
                if aggs.get("cpu_avg") is not None:
                    evidence.append(
                        f"CPU avg={aggs['cpu_avg']}% max={aggs.get('cpu_max', '?')}%"
                    )
                if aggs.get("ram_avg") is not None:
                    evidence.append(
                        f"RAM avg={aggs['ram_avg']}% max={aggs.get('ram_max', '?')}%"
                    )
                for snap in (result.get("snapshots") or [])[:5]:
                    host = snap.get("hostname", "?")
                    cpu = snap.get("cpu_usage")
                    ram = snap.get("ram_usage")
                    if cpu is not None or ram is not None:
                        parts = []
                        if cpu is not None:
                            parts.append(f"CPU={cpu}%")
                        if ram is not None:
                            parts.append(f"RAM={ram}%")
                        evidence.append(f"{host}: {', '.join(parts)}")
                count = result.get("count", 0)
                context.append(f"system_query returned {count} snapshot(s)")

            # ── log_search ────────────────────────────────────────────── #
            elif tool == "log_search":
                entries = result.get("entries") or []
                for entry in entries[:10]:
                    msg = str(
                        entry.get("message")
                        or entry.get("raw_line")
                        or entry.get("event")
                        or ""
                    ).strip()
                    source = entry.get("source_name") or entry.get("source") or ""
                    level = entry.get("level") or entry.get("severity") or ""
                    if msg:
                        tag = f"[{source}/{level}] " if (source or level) else ""
                        evidence.append(f"log: {tag}{msg[:120]}")
                count = result.get("count", len(entries))
                context.append(f"log_search matched {count} event(s)")

            # ── alert_check ───────────────────────────────────────────── #
            elif tool == "alert_check":
                violations = result.get("violations") or []
                for v in violations[:8]:
                    rule = v.get("rule_name") or v.get("name") or "unnamed rule"
                    metric = v.get("metric") or ""
                    val = v.get("current_value") or v.get("value")
                    thresh = v.get("threshold")
                    parts = [f"alert: {rule}"]
                    if metric:
                        parts.append(f"metric={metric}")
                    if val is not None:
                        parts.append(f"value={val}")
                    if thresh is not None:
                        parts.append(f"threshold={thresh}")
                    evidence.append(" ".join(parts))
                total = result.get("total_rules", 0)
                viol_count = result.get("violation_count", len(violations))
                context.append(
                    f"alert_check: {viol_count} violation(s) out of {total} rule(s)"
                )

            # ── remote_exec ───────────────────────────────────────────── #
            elif tool == "remote_exec":
                inner = result.get("result") or {}
                host = result.get("host") or inner.get("host") or "?"
                cmd = result.get("command") or inner.get("command") or "?"
                stdout = str(inner.get("stdout") or "").strip()[:300]
                stderr = str(inner.get("stderr") or "").strip()[:200]
                rc = inner.get("returncode")
                if stdout:
                    evidence.append(f"remote [{host}] {cmd}: {stdout}")
                if stderr:
                    evidence.append(f"remote [{host}] stderr: {stderr}")
                if rc is not None:
                    context.append(f"remote_exec on {host} exit_code={rc}")

            # ── generic fallback ──────────────────────────────────────── #
            else:
                context.append(f"[{tool}] {desc}: {str(result)[:200]}")

        # Fall back to memory snapshots if upstream_results had nothing useful.
        if not evidence:
            snapshots = memory.get("system_snapshots") or []
            for snap in snapshots[:3]:
                host = snap.get("hostname", "?")
                cpu = snap.get("cpu_usage")
                ram = snap.get("ram_usage")
                if cpu is not None:
                    evidence.append(f"{host}: CPU={cpu}%")
                if ram is not None:
                    evidence.append(f"{host}: RAM={ram}%")

        if not context:
            step_outputs = memory.get_step_outputs()
            for step in step_outputs[-4:]:
                desc = step.get("description", "")
                if desc:
                    context.append(desc)

        return evidence, context

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
        upstream_evidence, upstream_context = AIAnalysisTool._extract_upstream_evidence(
            params, memory
        )

        symptom_summary = str(params.get("symptom_summary") or "").strip()
        if not symptom_summary:
            if upstream_evidence:
                symptom_summary = "; ".join(upstream_evidence[:3])
            else:
                symptom_summary = "System anomaly requiring investigation"

        # Merge caller-supplied evidence with upstream findings.
        evidence_points: list[str] = list(params.get("evidence_points") or [])
        evidence_points = upstream_evidence + evidence_points
        if not evidence_points:
            evidence_points = ["No direct evidence available — analysis based on symptoms"]

        # Surface upstream context into the memory for later troubleshoot steps.
        if upstream_context:
            memory.set("upstream_context", upstream_context)

        result, error = AIService.analyze_root_cause(
            symptom_summary=symptom_summary,
            evidence_points=evidence_points[:12],
            runtime_config=runtime_config,
        )
        memory.set("ai_root_cause", result.get("root_cause") or {})
        return {
            "status": "success" if not error else "error",
            "tool": "ai_analysis",
            "mode": "root_cause",
            "upstream_evidence_count": len(upstream_evidence),
            "evidence_points_used": evidence_points[:12],
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
        upstream_evidence, upstream_context = AIAnalysisTool._extract_upstream_evidence(
            params, memory
        )

        symptom_summary = str(
            params.get("symptom_summary") or "System anomaly detected"
        ).strip()
        probable_cause = str(
            params.get("probable_cause")
            or (memory.get("ai_root_cause") or {}).get("probable_cause")
            or "Root cause under investigation"
        ).strip()

        evidence_points: list[str] = upstream_evidence + list(
            params.get("evidence_points") or []
        )

        result, error = AIService.generate_recommendations(
            symptom_summary=symptom_summary,
            probable_cause=probable_cause,
            evidence_points=evidence_points[:12],
            runtime_config=runtime_config,
        )
        memory.set("ai_recommendations", result.get("recommendations") or {})
        return {
            "status": "success" if not error else "error",
            "tool": "ai_analysis",
            "mode": "recommendations",
            "upstream_evidence_count": len(upstream_evidence),
            "evidence_points_used": evidence_points[:12],
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
        upstream_evidence, upstream_context = AIAnalysisTool._extract_upstream_evidence(
            params, memory
        )

        question = str(
            params.get("question") or "What should I investigate first?"
        ).strip()

        # Build context items: caller-supplied first, then upstream context.
        context_items: list[str] = list(params.get("context_items") or [])
        context_items = context_items + upstream_context + upstream_evidence

        result, error = AIService.assist_troubleshooting(
            question=question,
            context_items=context_items[:14],
            runtime_config=runtime_config,
        )
        memory.set("ai_guidance", result.get("guidance") or {})
        return {
            "status": "success" if not error else "error",
            "tool": "ai_analysis",
            "mode": "troubleshoot",
            "upstream_evidence_count": len(upstream_evidence),
            "context_items_used": context_items[:14],
            "result": result,
            "error": error,
        }, error
