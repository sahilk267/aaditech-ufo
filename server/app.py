"""
Aaditech UFO - Agent Monitoring System
Main Flask application bootstrap.
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from urllib.parse import urlparse

from dotenv import load_dotenv
from flask import Flask, g
from flask_migrate import upgrade as run_db_upgrade
from werkzeug.middleware.proxy_fix import ProxyFix

from .auth import init_auth_context
from .blueprints import api_bp, web_bp
from .config import get_config
from .extensions import db, init_extensions
from .queue import init_queue
from .services import PerformanceService
from .tenant_context import init_tenant_context

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def _check_redis_health(app: Flask) -> tuple[str, str | None]:
    """Return Redis connectivity state for deployment health visibility."""
    redis_url = str(app.config.get("REDIS_URL") or "").strip()
    if not redis_url:
        return "not_configured", None

    parsed = urlparse(redis_url)
    if parsed.scheme not in {"redis", "rediss"}:
        return "misconfigured", "unsupported_scheme"

    try:
        import redis

        client = redis.Redis.from_url(redis_url, socket_connect_timeout=1, socket_timeout=1)
        client.ping()
        return "connected", None
    except Exception as exc:  # pragma: no cover - defensive safety
        logger.warning("Redis health check failed: %s", exc)
        return "disconnected", str(exc)[:200]


def _register_request_hooks(app: Flask) -> None:
    @app.before_request
    def bind_request_context_headers():
        """Bind gateway-friendly request metadata to request context."""
        from flask import request

        g.request_started_at = time.time()
        g.request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

    @app.after_request
    def apply_gateway_response_headers(response):
        """Add traceability and transformation headers for gateway compatibility."""
        request_id = getattr(g, "request_id", None)
        if request_id:
            response.headers["X-Request-ID"] = request_id

        started_at = getattr(g, "request_started_at", None)
        if started_at is not None:
            elapsed_ms = int((time.time() - started_at) * 1000)
            response.headers["X-Response-Time-Ms"] = str(elapsed_ms)

        response.headers["X-API-Gateway-Ready"] = "true"
        if app.config.get("CDN_ENABLED", False):
            response.headers["X-Static-Asset-Base"] = app.config.get("CDN_STATIC_BASE_URL", "")
        return response


def _register_template_helpers(app: Flask) -> None:
    @app.template_filter("ist_format")
    def ist_format(value):
        """Format datetime to IST string."""
        if not value:
            return "N/A"

        from datetime import datetime

        import pytz

        ist = pytz.timezone("Asia/Kolkata")

        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return "N/A"

        if value.tzinfo is None:
            value = ist.localize(value)
        else:
            value = value.astimezone(ist)

        return value.strftime("%d-%m-%Y %I:%M:%S %p")

    @app.context_processor
    def inject_template_globals():
        """
        Inject global variables and functions into all templates.

        Makes the following available in Jinja2 templates:
        - is_active(last_update, now): Check if system is active
        - get_current_time(): Get current time in IST
        """
        from .services import SystemService

        def asset_url(asset_path: str) -> str:
            return PerformanceService.build_static_asset_url(asset_path, app.config)

        return {
            "is_active": SystemService.is_active,
            "current_time": SystemService.get_current_time,
            "current_user": getattr(g, "current_user", None),
            "current_tenant": getattr(g, "tenant", None),
            "is_authenticated": getattr(g, "current_user", None) is not None,
            "asset_url": asset_url,
        }


def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(404)
    def not_found(error):
        """Handle 404 errors."""
        from flask import jsonify

        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(500)
    def server_error(error):
        """Handle 500 errors."""
        from flask import jsonify

        logger.error("Server error: %s", error)
        return jsonify({"error": "Internal server error"}), 500

    @app.errorhandler(429)
    def ratelimit_handler(error):
        """Handle rate limit errors."""
        from flask import jsonify

        return jsonify({"error": "Rate limit exceeded", "message": str(error.description)}), 429


def _register_healthcheck(app: Flask) -> None:
    @app.route("/health", methods=["GET"])
    def health_check():
        """Health check endpoint."""
        from flask import jsonify
        from sqlalchemy import text

        try:
            db.session.execute(text("SELECT 1"))
            redis_state, redis_error = _check_redis_health(app)
            payload = {
                "status": "healthy" if redis_state in {"connected", "not_configured"} else "degraded",
                "database": "connected",
                "redis": redis_state,
            }
            if redis_error:
                payload["redis_error"] = redis_error
            return jsonify(payload), 200
        except Exception as exc:  # pragma: no cover - defensive safety
            logger.error("Health check failed: %s", exc)
            return jsonify({"status": "unhealthy", "database": "disconnected"}), 503


def create_app(config_object=None) -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(config_object or get_config())

    if app.config.get("ENABLE_PROXY_FIX", True):
        app.wsgi_app = ProxyFix(
            app.wsgi_app,
            x_for=app.config.get("PROXY_FIX_X_FOR", 1),
            x_proto=app.config.get("PROXY_FIX_X_PROTO", 1),
            x_host=app.config.get("PROXY_FIX_X_HOST", 1),
            x_port=app.config.get("PROXY_FIX_X_PORT", 1),
            x_prefix=app.config.get("PROXY_FIX_X_PREFIX", 1),
        )

    init_tenant_context(app)
    init_auth_context(app)
    init_queue(app)
    init_extensions(app)
    PerformanceService.init_cache(app)

    app.register_blueprint(api_bp)
    app.register_blueprint(web_bp)

    # Import models during app creation so metadata is registered for
    # migrations, tests, and explicit create_all() calls.
    from . import models  # noqa: F401

    _register_request_hooks(app)
    _register_template_helpers(app)
    _register_error_handlers(app)
    _register_healthcheck(app)

    return app


def apply_database_migrations(app: Flask) -> None:
    """Apply Alembic migrations using the active Flask app configuration."""
    with app.app_context():
        run_db_upgrade()
        logger.info("Database migrations applied")


app = create_app()


if __name__ == "__main__":
    apply_database_migrations(app)
    app.run(
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 5000)),
        debug=os.getenv("FLASK_DEBUG", False),
    )
