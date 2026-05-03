"""Executor: dispatches Steps to tools with retry and structured result passing.

Design:
  - Processes steps in dependency-respecting order (simple topological pass).
  - Each step is executed with up to step.retry_limit retries.
  - Retry backoff: 0.3 s, then 0.6 s (cheap — no real LLM or network in test).
  - Results are written into ShortTermMemory after every step.
  - The executor never raises; all errors are captured and returned.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from .memory import ShortTermMemory
from .planner import Step
from .tools import TOOL_REGISTRY

logger = logging.getLogger(__name__)

_RETRY_DELAYS = (0.3, 0.6, 1.2)


class Executor:
    """Runs an ordered plan of Steps against the tool registry."""

    @classmethod
    def execute_plan(
        cls,
        steps: list[Step],
        memory: ShortTermMemory,
        organization_id: int,
        runtime_config: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Execute all steps in dependency order.

        Returns an ordered list of step result dicts. Never raises.
        """
        if not steps:
            return []

        ordered = cls._resolve_order(steps)
        results: list[dict[str, Any]] = []

        for step in ordered:
            step_result = cls._execute_step_with_retry(
                step=step,
                memory=memory,
                organization_id=organization_id,
                runtime_config=runtime_config,
            )
            results.append(step_result)

            # Abort the entire plan on a step marked as fatal error?
            # Current policy: continue unless the tool signalled hard stop.
            # (Reserved for future policy enforcement via step.params.)

        return results

    # ------------------------------------------------------------------ #
    # Retry wrapper                                                        #
    # ------------------------------------------------------------------ #

    @classmethod
    def _execute_step_with_retry(
        cls,
        step: Step,
        memory: ShortTermMemory,
        organization_id: int,
        runtime_config: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute one Step with up to step.retry_limit retries.

        The result dict always contains:
            step_index, tool, description, status, result, error, retries
        """
        tool_cls = TOOL_REGISTRY.get(step.tool)
        if tool_cls is None:
            error_msg = f"Unknown tool: {step.tool!r}"
            logger.error("Executor: %s", error_msg)
            step_result = cls._build_step_result(step, None, error_msg, retries=0)
            memory.push_step_output(
                step_index=step.index,
                tool=step.tool,
                description=step.description,
                result=None,
                error=error_msg,
                retries=0,
            )
            return step_result

        last_result: dict[str, Any] | None = None
        last_error: str | None = None
        attempts = 0
        max_attempts = max(1, step.retry_limit + 1)

        for attempt in range(max_attempts):
            attempts = attempt + 1
            try:
                tool_result, error_key = tool_cls.run(
                    params=step.params,
                    memory=memory,
                    organization_id=organization_id,
                    runtime_config=runtime_config,
                )
                last_result = tool_result
                last_error = error_key

                if not error_key:
                    # Success — no retry needed
                    break

                # Transient error — retry if attempts remain
                if attempt < max_attempts - 1:
                    delay = _RETRY_DELAYS[min(attempt, len(_RETRY_DELAYS) - 1)]
                    logger.warning(
                        "Executor: step %d (%s) attempt %d/%d failed with %r — retrying in %.1fs",
                        step.index, step.tool, attempt + 1, max_attempts, error_key, delay,
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        "Executor: step %d (%s) exhausted %d attempts, last error: %r",
                        step.index, step.tool, max_attempts, error_key,
                    )

            except Exception as exc:
                last_error = str(exc)[:300]
                last_result = {"status": "error", "exception": last_error}
                logger.exception(
                    "Executor: step %d (%s) raised exception on attempt %d: %s",
                    step.index, step.tool, attempt + 1, exc,
                )
                if attempt < max_attempts - 1:
                    delay = _RETRY_DELAYS[min(attempt, len(_RETRY_DELAYS) - 1)]
                    time.sleep(delay)

        step_result = cls._build_step_result(step, last_result, last_error, retries=attempts - 1)

        memory.push_step_output(
            step_index=step.index,
            tool=step.tool,
            description=step.description,
            result=last_result,
            error=last_error,
            retries=attempts - 1,
        )

        return step_result

    # ------------------------------------------------------------------ #
    # Dependency resolution                                                #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _resolve_order(steps: list[Step]) -> list[Step]:
        """Return steps in a dependency-respecting execution order.

        Steps with depends_on are moved after their dependencies.
        Steps with no depends_on (or whose dependencies are all already
        satisfied) are executed first. This is a simple stable topological
        sort — cycles are broken by falling back to original index order.
        """
        index_map: dict[int, Step] = {s.index: s for s in steps}
        visited: set[int] = set()
        ordered: list[Step] = []

        def visit(step: Step, depth: int = 0) -> None:
            if step.index in visited:
                return
            if depth > len(steps):
                # Cycle guard
                return
            for dep_idx in step.depends_on:
                dep = index_map.get(dep_idx)
                if dep:
                    visit(dep, depth + 1)
            visited.add(step.index)
            ordered.append(step)

        for step in steps:
            visit(step)

        return ordered

    # ------------------------------------------------------------------ #
    # Result builder                                                       #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _build_step_result(
        step: Step,
        tool_result: dict[str, Any] | None,
        error: str | None,
        retries: int,
    ) -> dict[str, Any]:
        return {
            "step_index": step.index,
            "tool": step.tool,
            "description": step.description,
            "params": step.params,
            "status": "error" if error else "success",
            "result": tool_result,
            "error": error,
            "retries": retries,
        }
