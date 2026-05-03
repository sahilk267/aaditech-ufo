"""Tool layer for the agent engine.

Each tool is a thin adapter that calls an existing service and returns
a normalised dict.  All tools follow the same signature:

    run(params: dict, memory: ShortTermMemory, organization_id: int,
        runtime_config: dict) -> tuple[dict, str | None]

The second element of the return tuple is an error key (str) or None.
"""

from .system_query import SystemQueryTool
from .automation_trigger import AutomationTriggerTool
from .ai_analysis import AIAnalysisTool
from .alert_check import AlertCheckTool
from .log_search import LogSearchTool
from .remote_exec import RemoteExecTool

TOOL_REGISTRY: dict = {
    "system_query": SystemQueryTool,
    "automation_trigger": AutomationTriggerTool,
    "ai_analysis": AIAnalysisTool,
    "alert_check": AlertCheckTool,
    "log_search": LogSearchTool,
    "remote_exec": RemoteExecTool,
}

__all__ = [
    "TOOL_REGISTRY",
    "SystemQueryTool",
    "AutomationTriggerTool",
    "AIAnalysisTool",
    "AlertCheckTool",
    "LogSearchTool",
    "RemoteExecTool",
]
