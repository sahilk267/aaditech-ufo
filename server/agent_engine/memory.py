"""Short-term in-process memory for a single agent run.

Each Orchestrator invocation gets its own ShortTermMemory instance.
The memory provides:
  - Named slots: key/value pairs any component may read or write
  - Step output history: ordered list of every tool result
  - Context snapshot: serialisable dict consumed by the Planner/Synthesizer
  - DB persistence: one-shot flush to an AgentSession ORM row
"""

from __future__ import annotations

from datetime import datetime, UTC
from typing import Any


class ShortTermMemory:
    """Named context store for one orchestration session."""

    def __init__(self, session_id: str, organization_id: int) -> None:
        self._session_id = session_id
        self._organization_id = organization_id
        self._slots: dict[str, Any] = {}
        self._step_outputs: list[dict[str, Any]] = []
        self._created_at: str = datetime.now(UTC).isoformat()

    # ------------------------------------------------------------------ #
    # Named slots                                                          #
    # ------------------------------------------------------------------ #

    def set(self, key: str, value: Any) -> None:
        """Store an arbitrary value under *key*."""
        self._slots[str(key)] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve a value; returns *default* if absent."""
        return self._slots.get(str(key), default)

    def delete(self, key: str) -> None:
        """Remove a slot if it exists."""
        self._slots.pop(str(key), None)

    def all_slots(self) -> dict[str, Any]:
        """Return a shallow copy of all named slots."""
        return dict(self._slots)

    # ------------------------------------------------------------------ #
    # Step output history                                                  #
    # ------------------------------------------------------------------ #

    def push_step_output(
        self,
        step_index: int,
        tool: str,
        description: str,
        result: Any,
        error: str | None = None,
        retries: int = 0,
    ) -> None:
        """Append the outcome of one executed step."""
        self._step_outputs.append({
            "step_index": step_index,
            "tool": tool,
            "description": description,
            "result": result,
            "error": error,
            "retries": retries,
            "status": "error" if error else "success",
            "recorded_at": datetime.now(UTC).isoformat(),
        })

    def get_step_outputs(self) -> list[dict[str, Any]]:
        """Return the full ordered list of step outcomes."""
        return list(self._step_outputs)

    def last_step_result(self) -> dict[str, Any] | None:
        """Return the most-recently recorded step outcome, or None."""
        return self._step_outputs[-1] if self._step_outputs else None

    def successful_results(self) -> list[dict[str, Any]]:
        """Return only step outputs that completed without error."""
        return [s for s in self._step_outputs if s.get("status") == "success"]

    def failed_results(self) -> list[dict[str, Any]]:
        """Return only step outputs that ended in error."""
        return [s for s in self._step_outputs if s.get("status") == "error"]

    def step_summary(self) -> dict[str, int]:
        return {
            "total": len(self._step_outputs),
            "success": len(self.successful_results()),
            "failed": len(self.failed_results()),
        }

    # ------------------------------------------------------------------ #
    # Context snapshot (for Planner / Synthesizer)                        #
    # ------------------------------------------------------------------ #

    def to_context_snapshot(self) -> dict[str, Any]:
        """Return a JSON-serialisable dict summarising current memory state."""
        return {
            "session_id": self._session_id,
            "organization_id": self._organization_id,
            "created_at": self._created_at,
            "slots": self.all_slots(),
            "step_summary": self.step_summary(),
            "last_step": self.last_step_result(),
        }

    # ------------------------------------------------------------------ #
    # DB persistence                                                       #
    # ------------------------------------------------------------------ #

    def persist_to_session(self, session_row: Any) -> None:
        """Flush current state into an AgentSession ORM row (no commit)."""
        session_row.step_outputs = self.get_step_outputs()
        session_row.metadata_payload = {
            "slots": self.all_slots(),
            "step_summary": self.step_summary(),
        }

    # ------------------------------------------------------------------ #
    # Properties                                                           #
    # ------------------------------------------------------------------ #

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def organization_id(self) -> int:
        return self._organization_id
