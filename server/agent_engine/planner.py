"""Planner: decomposes a natural-language request into an ordered Step list.

Two-stage approach:
  1. Ask the AI to return a JSON step array (best-effort).
  2. If the AI response cannot be parsed, fall back to a deterministic
     keyword-matcher that always produces at least one actionable Step.

Design constraints:
  - Never raises; always returns (steps, error_key | None).
  - Maximum MAX_PLAN_STEPS steps to prevent unbounded execution.
  - All tool names are validated against KNOWN_TOOLS.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from ..services.ai_service import AIService

logger = logging.getLogger(__name__)

KNOWN_TOOLS: frozenset[str] = frozenset({
    "system_query",
    "automation_trigger",
    "ai_analysis",
    "alert_check",
    "log_search",
    "remote_exec",
})

MAX_PLAN_STEPS = 10


@dataclass
class Step:
    """A single unit of work in an agent plan."""

    index: int
    tool: str
    description: str
    params: dict[str, Any]
    retry_limit: int = 2
    depends_on: list[int] = field(default_factory=list)
    timeout_seconds: int = 30

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "tool": self.tool,
            "description": self.description,
            "params": self.params,
            "retry_limit": self.retry_limit,
            "depends_on": self.depends_on,
            "timeout_seconds": self.timeout_seconds,
        }


_PLANNING_PROMPT = """\
You are an infrastructure automation planner for a production monitoring system.
Decompose the operator's request into a concise JSON array of steps.

Each step object must have exactly these keys:
  "tool"        : one of system_query | automation_trigger | ai_analysis | alert_check | log_search | remote_exec
  "description" : short human-readable description (< 120 chars)
  "params"      : object with tool-specific parameters

Return ONLY a valid JSON array. No prose. No markdown fences.

Available tools and their key params:
  system_query       : {limit: int, metric: str}
  automation_trigger : {workflow_id: int, dry_run: bool}
  ai_analysis        : {mode: "root_cause"|"recommendations"|"troubleshoot", symptom_summary: str, evidence_points: list, question: str, context_items: list}
  alert_check        : {metric: str, limit: int}
  log_search         : {source_name: str, query_text: str}
  remote_exec        : {host: str, command: str}

Operator request: {request}

Current context summary: {context}
"""


class Planner:
    """Converts a user request string into an ordered list of Steps."""

    @classmethod
    def plan(
        cls,
        request: str,
        context: dict[str, Any],
        runtime_config: dict[str, Any],
    ) -> tuple[list[Step], str | None]:
        """Return (steps, error_key | None). Never raises."""
        request = str(request or "").strip()
        if not request:
            return [], "request_empty"

        # Stage 1 — ask the AI for a structured plan
        steps = cls._try_ai_plan(request, context, runtime_config)

        # Stage 2 — deterministic fallback
        if not steps:
            logger.info("Planner: AI plan empty or unparseable; using rule-based fallback.")
            steps = cls._rule_based_plan(request)

        if not steps:
            return [], "plan_empty"

        # Enforce cap and re-index
        steps = steps[:MAX_PLAN_STEPS]
        for i, step in enumerate(steps):
            step.index = i

        return steps, None

    # ------------------------------------------------------------------ #
    # AI planning                                                          #
    # ------------------------------------------------------------------ #

    @classmethod
    def _try_ai_plan(
        cls,
        request: str,
        context: dict[str, Any],
        runtime_config: dict[str, Any],
    ) -> list[Step]:
        """Ask the AI to produce a step plan. Returns [] if unparseable."""
        try:
            context_text = json.dumps(context, default=str)[:600]
            prompt = _PLANNING_PROMPT.format(
                request=request[:600],
                context=context_text,
            )
            result, error = AIService.run_ollama_inference(prompt, runtime_config=runtime_config)
            if error:
                return []

            response_text = str(
                (result.get("inference") or {}).get("response_text") or ""
            ).strip()

            return cls._parse_ai_response(response_text)
        except Exception as exc:
            logger.warning("Planner._try_ai_plan failed: %s", exc)
            return []

    @staticmethod
    def _parse_ai_response(response_text: str) -> list[Step]:
        """Try to extract a JSON step array from the AI response."""
        match = re.search(r"\[.*?\]", response_text, re.DOTALL)
        if not match:
            return []
        try:
            raw_steps = json.loads(match.group(0))
            if not isinstance(raw_steps, list):
                return []
        except (json.JSONDecodeError, ValueError):
            return []

        steps: list[Step] = []
        for i, raw in enumerate(raw_steps):
            if not isinstance(raw, dict):
                continue
            tool = str(raw.get("tool") or "").strip()
            if tool not in KNOWN_TOOLS:
                continue
            steps.append(Step(
                index=i,
                tool=tool,
                description=str(raw.get("description") or tool)[:255],
                params=raw.get("params") or {},
                retry_limit=max(0, min(int(raw.get("retry_limit") or 2), 5)),
                depends_on=list(raw.get("depends_on") or []),
                timeout_seconds=max(5, min(int(raw.get("timeout_seconds") or 30), 120)),
            ))
        return steps

    # ------------------------------------------------------------------ #
    # Rule-based fallback                                                  #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _rule_based_plan(request: str) -> list[Step]:
        """Keyword-match fallback that always produces at least one Step."""
        lower = request.lower()
        steps: list[Step] = []
        idx = 0

        def add(tool: str, description: str, params: dict[str, Any]) -> None:
            nonlocal idx
            steps.append(Step(index=idx, tool=tool, description=description, params=params))
            idx += 1

        # System metrics check
        if any(kw in lower for kw in ("cpu", "memory", "ram", "disk", "storage", "metric", "system", "benchmark", "performance")):
            add("system_query", "Query recent system metrics snapshot", {"limit": 10})

        # Alert check
        if any(kw in lower for kw in ("alert", "threshold", "rule", "trigger", "breach", "violation")):
            add("alert_check", "Check active alert rules and current status", {"limit": 20})

        # Log search
        if any(kw in lower for kw in ("log", "event", "search", "audit", "journal", "error", "warning")):
            source = "System" if "system" in lower else "Application"
            query = "error" if "error" in lower else "warning"
            add("log_search", f"Search {source} logs for relevant events", {
                "source_name": source,
                "query_text": query,
            })

        # Automation trigger
        if any(kw in lower for kw in ("automat", "workflow", "restart", "service", "remediat", "run", "trigger")):
            add("automation_trigger", "Trigger automation workflow (dry-run mode)", {
                "dry_run": True,
                "workflow_id": None,
            })

        # Remote execution
        if any(kw in lower for kw in ("remote", "ssh", "host", "server", "connect")):
            add("remote_exec", "Execute remote diagnostic command", {
                "host": "localhost",
                "command": "uptime",
            })

        # AI analysis — always add if we gathered data
        if steps and not any(s.tool == "ai_analysis" for s in steps):
            add("ai_analysis", "Synthesize findings into actionable recommendations", {
                "mode": "recommendations",
                "symptom_summary": request[:500],
                "evidence_points": [],
            })
        elif any(kw in lower for kw in ("analyze", "diagnose", "root cause", "explain", "why", "cause", "recommend", "fix", "suggest")):
            add("ai_analysis", "Perform AI root cause analysis", {
                "mode": "root_cause",
                "symptom_summary": request[:500],
                "evidence_points": [],
            })

        # Nothing matched at all — produce a safe default plan
        if not steps:
            add("system_query", "Gather system overview", {"limit": 5})
            add("ai_analysis", "Analyse request and provide operator guidance", {
                "mode": "troubleshoot",
                "question": request[:500],
                "context_items": [],
            })

        return steps
