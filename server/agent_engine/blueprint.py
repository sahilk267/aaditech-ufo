"""Agent Engine Flask blueprint — exposes orchestration endpoints.

Routes
------
POST /api/agent_engine/run
    Submit a natural-language request to the agent.
    Body: { "request": str, "dry_run": bool, "runtime_config": dict }
    Returns: full orchestration result (session_id, plan, step_results, summary).

GET /api/agent_engine/sessions
    List recent AgentSession rows for the current tenant.
    Query params: ?limit=20&status=completed

GET /api/agent_engine/sessions/<session_id>
    Fetch a specific session by its UUID.

GET /api/agent_engine/tools
    List all registered tool names and their descriptions.
"""

from __future__ import annotations

import logging
from datetime import datetime, UTC

from flask import Blueprint, g, jsonify, request

from ..auth import require_jwt_auth, require_permission
from ..extensions import limiter

logger = logging.getLogger(__name__)

agent_engine_bp = Blueprint("agent_engine", __name__, url_prefix="/api/agent_engine")


# ------------------------------------------------------------------ #
# POST /api/agent_engine/run                                          #
# ------------------------------------------------------------------ #

@agent_engine_bp.route("/run", methods=["POST"])
@require_jwt_auth
@require_permission("automation.manage")
@limiter.limit("30/minute")
def run_agent():
    """Submit a natural-language request to the agent orchestrator."""
    from ..orchestrator_factory import build_runtime_config
    from . import Orchestrator

    body = request.get_json(silent=True) or {}
    raw_request = str(body.get("request") or "").strip()
    dry_run = bool(body.get("dry_run", True))
    extra_runtime = body.get("runtime_config") or {}

    if not raw_request:
        return jsonify({"error": "request field is required and must not be empty"}), 400

    if len(raw_request) > 2000:
        return jsonify({"error": "request exceeds 2000-character limit"}), 400

    organization_id = g.tenant.id
    runtime_config = build_runtime_config(extra_runtime, dry_run=dry_run)

    result = Orchestrator.run(
        request=raw_request,
        organization_id=organization_id,
        runtime_config=runtime_config,
    )

    http_status = 200 if result.get("status") in {"completed", "partial"} else 422
    return jsonify(result), http_status


# ------------------------------------------------------------------ #
# GET /api/agent_engine/sessions                                      #
# ------------------------------------------------------------------ #

@agent_engine_bp.route("/sessions", methods=["GET"])
@require_jwt_auth
@require_permission("automation.manage")
@limiter.limit("60/minute")
def list_sessions():
    """List recent AgentSession rows for the current tenant."""
    from ..models import AgentSession

    limit = min(int(request.args.get("limit") or 20), 100)
    status_filter = request.args.get("status") or None

    query = AgentSession.query.filter_by(organization_id=g.tenant.id)
    if status_filter:
        query = query.filter(AgentSession.status == status_filter)

    rows = query.order_by(AgentSession.created_at.desc()).limit(limit).all()

    return jsonify({
        "sessions": [r.to_dict() for r in rows],
        "count": len(rows),
    }), 200


# ------------------------------------------------------------------ #
# GET /api/agent_engine/sessions/<session_id>                         #
# ------------------------------------------------------------------ #

@agent_engine_bp.route("/sessions/<string:session_id>", methods=["GET"])
@require_jwt_auth
@require_permission("automation.manage")
@limiter.limit("60/minute")
def get_session(session_id: str):
    """Fetch a specific AgentSession by its UUID."""
    from ..models import AgentSession

    row = AgentSession.query.filter_by(
        organization_id=g.tenant.id,
        session_id=session_id,
    ).first()

    if row is None:
        return jsonify({"error": "Session not found"}), 404

    return jsonify(row.to_dict()), 200


# ------------------------------------------------------------------ #
# GET /api/agent_engine/tools                                         #
# ------------------------------------------------------------------ #

@agent_engine_bp.route("/tools", methods=["GET"])
@require_jwt_auth
@limiter.limit("60/minute")
def list_tools():
    """Return the registry of available agent tools."""
    from .tools import TOOL_REGISTRY

    tool_info = [
        {
            "name": name,
            "class": cls.__name__,
            "doc": (cls.__doc__ or "").strip().split("\n")[0][:120],
        }
        for name, cls in TOOL_REGISTRY.items()
    ]

    return jsonify({
        "tools": tool_info,
        "count": len(tool_info),
    }), 200
