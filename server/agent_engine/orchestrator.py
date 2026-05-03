"""Orchestrator: top-level controller for one complete agent run.

Lifecycle
---------
1. Validate and normalise the incoming request.
2. Create an AgentSession DB row (status = "running").
3. Initialise ShortTermMemory for this session.
4. Call Planner.plan() to decompose the request into Steps.
5. Call Executor.execute_plan() to dispatch each Step to its tool.
6. Synthesise a final human-readable summary via AIService.
7. Persist results to the AgentSession row (status = "completed" / "failed").
8. Return the full structured response dict to the caller.

All failures are captured and returned as structured error responses — the
Orchestrator never propagates raw exceptions to its caller.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, UTC
from typing import Any

from .memory import ShortTermMemory
from .planner import Planner
from .executor import Executor

logger = logging.getLogger(__name__)

_MAX_REQUEST_CHARS = 2000


class Orchestrator:
    """Runs one complete agent request lifecycle."""

    @classmethod
    def run(
        cls,
        request: str,
        organization_id: int,
        runtime_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute an agent request end-to-end.

        Returns a structured dict — never raises.
        """
        runtime_config = runtime_config or {}
        session_id = str(uuid.uuid4())
        started_at = datetime.now(UTC)

        # --- basic validation ---
        request = str(request or "").strip()
        if not request:
            return cls._error_response(session_id, "request_empty", "Request must not be empty.", started_at)

        if len(request) > _MAX_REQUEST_CHARS:
            request = request[:_MAX_REQUEST_CHARS]
            logger.warning("Orchestrator: request truncated to %d chars for session %s", _MAX_REQUEST_CHARS, session_id)

        # --- create DB session row ---
        session_row = cls._create_session(session_id, organization_id, request)

        # --- initialise memory ---
        memory = ShortTermMemory(session_id=session_id, organization_id=organization_id)

        try:
            # --- planning ---
            logger.info("Orchestrator: planning session=%s org=%d", session_id, organization_id)
            context = memory.to_context_snapshot()
            steps, plan_error = Planner.plan(request, context, runtime_config)

            if plan_error or not steps:
                return cls._fail_session(
                    session_row, session_id, organization_id,
                    plan_error or "plan_empty",
                    "Planner could not decompose request into steps.",
                    memory, started_at,
                )

            plan_dicts = [s.to_dict() for s in steps]
            logger.info("Orchestrator: plan has %d steps for session=%s", len(steps), session_id)

            if session_row:
                session_row.plan_steps = plan_dicts
                cls._commit_session(session_row)

            # --- execution ---
            logger.info("Orchestrator: executing plan for session=%s", session_id)
            step_results = Executor.execute_plan(
                steps=steps,
                memory=memory,
                organization_id=organization_id,
                runtime_config=runtime_config,
            )

            # --- synthesis ---
            final_summary = cls._synthesise(request, memory, runtime_config)

            # --- persist results ---
            finished_at = datetime.now(UTC)
            duration_ms = int((finished_at - started_at).total_seconds() * 1000)

            step_summary = memory.step_summary()
            status = "completed" if step_summary["failed"] == 0 else "partial"

            if session_row:
                memory.persist_to_session(session_row)
                session_row.final_result = {
                    "summary": final_summary,
                    "step_summary": step_summary,
                }
                session_row.status = status
                session_row.duration_ms = duration_ms
                cls._commit_session(session_row)

            return {
                "status": status,
                "session_id": session_id,
                "organization_id": organization_id,
                "request": request,
                "plan": plan_dicts,
                "step_results": step_results,
                "step_summary": step_summary,
                "final_summary": final_summary,
                "duration_ms": duration_ms,
                "started_at": started_at.isoformat(),
                "finished_at": finished_at.isoformat(),
            }

        except Exception as exc:
            logger.exception("Orchestrator: unhandled exception in session=%s: %s", session_id, exc)
            return cls._fail_session(
                session_row, session_id, organization_id,
                "orchestrator_exception",
                str(exc)[:300],
                memory, started_at,
            )

    # ------------------------------------------------------------------ #
    # Synthesis                                                            #
    # ------------------------------------------------------------------ #

    @classmethod
    def _synthesise(
        cls,
        request: str,
        memory: ShortTermMemory,
        runtime_config: dict[str, Any],
    ) -> dict[str, Any]:
        """Ask the AI to summarise all step findings into a final answer."""
        from ..services.ai_service import AIService

        step_outputs = memory.get_step_outputs()
        context_items: list[str] = []

        for step in step_outputs:
            desc = step.get("description", "")
            status = step.get("status", "")
            tool = step.get("tool", "")
            if desc:
                context_items.append(f"[{tool}] {desc}: {status}")

        # Add key AI findings if available
        root_cause = memory.get("ai_root_cause") or {}
        if root_cause.get("probable_cause"):
            context_items.append(f"Root cause: {root_cause['probable_cause']}")

        recommendations = memory.get("ai_recommendations") or {}
        if recommendations.get("items"):
            items_text = "; ".join(str(i) for i in recommendations["items"][:3])
            context_items.append(f"Recommendations: {items_text}")

        breaches = memory.get("alert_breaches") or []
        if breaches:
            context_items.append(f"Alert breaches: {len(breaches)} threshold(s) crossed")

        question = (
            f"Summarise findings from this infrastructure investigation: {request[:300]}"
        )

        result, error = AIService.assist_troubleshooting(
            question=question,
            context_items=context_items[:10],
            runtime_config=runtime_config,
        )

        if error:
            return {
                "status": "synthesis_failed",
                "error": error,
                "context_item_count": len(context_items),
            }

        return {
            "status": "success",
            "guidance": result.get("guidance") or {},
            "adapter": result.get("adapter"),
            "context_item_count": len(context_items),
        }

    # ------------------------------------------------------------------ #
    # DB helpers                                                           #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _create_session(
        session_id: str,
        organization_id: int,
        request: str,
    ) -> Any:
        """Create and persist a new AgentSession row. Returns None on failure."""
        try:
            from ..models import AgentSession
            from ..extensions import db

            row = AgentSession(
                session_id=session_id,
                organization_id=organization_id,
                request_text=request[:2000],
                status="running",
                plan_steps=[],
                step_outputs=[],
                final_result={},
                metadata_payload={},
            )
            db.session.add(row)
            db.session.commit()
            return row
        except Exception as exc:
            logger.warning("Orchestrator: could not create AgentSession row: %s", exc)
            try:
                from ..extensions import db
                db.session.rollback()
            except Exception:
                pass
            return None

    @staticmethod
    def _commit_session(session_row: Any) -> None:
        """Commit pending changes to the session row."""
        try:
            from ..extensions import db
            db.session.commit()
        except Exception as exc:
            logger.warning("Orchestrator: commit failed: %s", exc)
            try:
                from ..extensions import db
                db.session.rollback()
            except Exception:
                pass

    @classmethod
    def _fail_session(
        cls,
        session_row: Any,
        session_id: str,
        organization_id: int,
        error_key: str,
        error_detail: str,
        memory: ShortTermMemory,
        started_at: datetime,
    ) -> dict[str, Any]:
        """Mark a session as failed and return a structured error response."""
        finished_at = datetime.now(UTC)
        duration_ms = int((finished_at - started_at).total_seconds() * 1000)

        if session_row:
            try:
                memory.persist_to_session(session_row)
                session_row.status = "failed"
                session_row.error_reason = error_key[:64]
                session_row.duration_ms = duration_ms
                cls._commit_session(session_row)
            except Exception as exc:
                logger.warning("Orchestrator: could not update failed session: %s", exc)

        return {
            "status": "failed",
            "session_id": session_id,
            "organization_id": organization_id,
            "error_key": error_key,
            "error_detail": error_detail,
            "step_summary": memory.step_summary(),
            "duration_ms": duration_ms,
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
        }

    @staticmethod
    def _error_response(
        session_id: str,
        error_key: str,
        error_detail: str,
        started_at: datetime,
    ) -> dict[str, Any]:
        """Return a structured error without touching the DB."""
        finished_at = datetime.now(UTC)
        return {
            "status": "failed",
            "session_id": session_id,
            "error_key": error_key,
            "error_detail": error_detail,
            "step_summary": {"total": 0, "success": 0, "failed": 0},
            "duration_ms": int((finished_at - started_at).total_seconds() * 1000),
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
        }
