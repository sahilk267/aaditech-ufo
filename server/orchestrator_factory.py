"""Build the runtime_config dict consumed by all agent engine components.

Pulls from Flask app.config so blueprint and service code have a single
place to retrieve adapter settings, timeouts, and feature flags.
"""

from __future__ import annotations

from typing import Any

from flask import current_app


def build_runtime_config(
    overrides: dict[str, Any] | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Assemble a runtime_config dict from Flask config + caller overrides.

    The returned dict is passed to Planner, Executor, and every Tool.
    Callers may supply overrides to activate real adapters during testing
    or when specific credentials are available.
    """
    cfg = current_app.config

    base: dict[str, Any] = {
        # AI / Ollama
        "adapter": cfg.get("OLLAMA_ADAPTER", "linux_test_double"),
        "model": cfg.get("OLLAMA_DEFAULT_MODEL", "llama3.2"),
        "endpoint": cfg.get("OLLAMA_ENDPOINT", "http://localhost:11434/api/generate"),
        "allowed_models": [m.strip() for m in cfg.get("OLLAMA_ALLOWED_MODELS", "llama3.2").split(",") if m.strip()],
        "allowed_hosts": [h.strip() for h in cfg.get("OLLAMA_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()],
        "timeout_seconds": cfg.get("OLLAMA_TIMEOUT_SECONDS", 8),
        "prompt_max_chars": cfg.get("OLLAMA_PROMPT_MAX_CHARS", 4000),
        "response_max_chars": cfg.get("OLLAMA_RESPONSE_MAX_CHARS", 4000),

        # Automation
        "dry_run": dry_run,
        "allowed_services": [s.strip() for s in cfg.get("AUTOMATION_ALLOWED_SERVICES", "").split(",") if s.strip()],
        "allowed_script_roots": [r.strip() for r in cfg.get("AUTOMATION_ALLOWED_SCRIPT_ROOTS", "").split(",") if r.strip()],
        "allowed_webhook_hosts": [h.strip() for h in cfg.get("AUTOMATION_ALLOWED_WEBHOOK_HOSTS", "").split(",") if h.strip()],
        "command_timeout_seconds": cfg.get("AUTOMATION_COMMAND_TIMEOUT_SECONDS", 8),
        "service_restart_binary": cfg.get("AUTOMATION_SERVICE_RESTART_BINARY", "systemctl"),

        # Log search
        "log_search_adapter": cfg.get("LOG_SEARCH_ADAPTER", "linux_test_double"),
        "search_adapter": cfg.get("LOG_SEARCH_ADAPTER", "linux_test_double"),

        # Remote exec
        "remote_exec_adapter": cfg.get("REMOTE_EXEC_ADAPTER", "linux_test_double"),
        "ssh_adapter": cfg.get("REMOTE_EXEC_ADAPTER", "linux_test_double"),
        "ssh_timeout_seconds": cfg.get("REMOTE_EXEC_TIMEOUT_SECONDS", 10),

        # Agent engine limits
        "max_plan_steps": cfg.get("AGENT_ENGINE_MAX_STEPS", 10),
        "max_retries": cfg.get("AGENT_ENGINE_MAX_RETRIES", 2),
        "step_timeout_seconds": cfg.get("AGENT_ENGINE_STEP_TIMEOUT_SECONDS", 30),
    }

    if overrides:
        base.update(overrides)

    return base
