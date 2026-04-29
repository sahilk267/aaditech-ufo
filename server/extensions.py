"""Flask Extensions Initialization.

Centralizes all Flask extension setup. Includes a graceful Redis fallback for
the rate limiter so the platform keeps running even when REDIS_URL is unset
or temporarily unreachable.
"""

import logging
import os

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

logger = logging.getLogger(__name__)


db = SQLAlchemy()
migrate = Migrate()
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
)


def _resolve_limiter_storage(app) -> str:
    """Pick the best rate-limiter storage URI without crashing the app.

    Priority:
      1. ``RATELIMIT_STORAGE_URL`` (explicit override)
      2. ``REDIS_URL`` (only when it points at a reachable Redis instance)
      3. ``memory://`` (always works, instance-local)
    """
    explicit = (app.config.get('RATELIMIT_STORAGE_URL') or '').strip()
    redis_url = (os.getenv('REDIS_URL') or app.config.get('REDIS_URL') or '').strip()

    candidate = explicit or (redis_url if redis_url else 'memory://')

    if candidate.startswith(('redis://', 'rediss://')):
        if not _ping_redis(candidate):
            logger.warning(
                "Rate limiter Redis backend %s unreachable; falling back to in-memory storage. "
                "Set REDIS_URL to a reachable instance for multi-instance deployments.",
                _safe_url(candidate),
            )
            return 'memory://'
        logger.info("Rate limiter using Redis backend %s", _safe_url(candidate))
        return candidate

    if candidate != 'memory://':
        logger.info("Rate limiter using non-Redis backend %s", _safe_url(candidate))
    return candidate


def _ping_redis(url: str, timeout: float = 1.0) -> bool:
    """Best-effort Redis liveness probe. Returns False on any error."""
    try:
        import redis  # type: ignore
    except Exception:
        return False
    try:
        client = redis.Redis.from_url(url, socket_connect_timeout=timeout, socket_timeout=timeout)
        client.ping()
        try:
            client.close()
        except Exception:
            pass
        return True
    except Exception as exc:  # pragma: no cover - network sensitive
        logger.debug("Redis ping failed for %s: %s", _safe_url(url), exc)
        return False


def _safe_url(url: str) -> str:
    """Strip credentials from a URL for log output."""
    if '@' in url:
        scheme, _, rest = url.partition('://')
        _, _, host = rest.rpartition('@')
        return f"{scheme}://***@{host}"
    return url


def init_extensions(app):
    """Initialize all Flask extensions with app context."""
    db.init_app(app)
    migrate.init_app(app, db)

    storage_uri = _resolve_limiter_storage(app)
    app.config['RATELIMIT_STORAGE_URL'] = storage_uri
    app.config['_LIMITER_STORAGE_RESOLVED'] = storage_uri
    limiter.init_app(app)
