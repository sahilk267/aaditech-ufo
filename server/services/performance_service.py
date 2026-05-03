"""Performance service for Phase 4 optimization features.

Provides:
- Redis/memory cache layer
- Query optimization helpers for dashboard pages
- Database optimization routines
- CDN-aware static asset URL generation
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from urllib.parse import urljoin

from sqlalchemy import func, case, text
from sqlalchemy.orm import load_only

from ..extensions import db
from ..models import SystemData

logger = logging.getLogger(__name__)


class PerformanceService:
    """Centralized performance and optimization utilities."""

    _redis_client = None
    _memory_cache: dict[str, tuple[datetime, Any]] = {}
    _cache_enabled = False
    _cache_backend = 'memory'
    _cache_default_ttl = 60
    _cache_prefix = 'aaditech:ufo'

    @classmethod
    def init_cache(cls, app) -> None:
        """Initialize cache backend based on runtime configuration."""
        cls._cache_enabled = bool(app.config.get('CACHE_ENABLED', True))
        cls._cache_backend = str(app.config.get('CACHE_BACKEND', 'memory')).strip().lower()
        cls._cache_default_ttl = int(app.config.get('CACHE_DEFAULT_TTL_SECONDS', 60))
        cls._cache_prefix = str(app.config.get('CACHE_KEY_PREFIX', 'aaditech:ufo')).strip() or 'aaditech:ufo'

        if not cls._cache_enabled:
            cls._redis_client = None
            logger.info('Performance cache disabled by configuration')
            return

        if cls._cache_backend != 'redis':
            cls._redis_client = None
            logger.info('Performance cache backend initialized: memory')
            return

        try:
            import redis

            redis_url = str(app.config.get('REDIS_URL', 'redis://localhost:6379/0'))
            client = redis.Redis.from_url(redis_url, decode_responses=True, socket_timeout=1)
            client.ping()
            cls._redis_client = client
            logger.info('Performance cache backend initialized: redis (%s)', redis_url)
        except Exception as exc:
            cls._redis_client = None
            cls._cache_backend = 'memory'
            logger.warning('Redis cache unavailable, falling back to memory cache: %s', exc)

    @classmethod
    def cache_backend(cls) -> str:
        """Return active cache backend name."""
        if not cls._cache_enabled:
            return 'disabled'
        if cls._cache_backend == 'redis' and cls._redis_client is not None:
            return 'redis'
        return 'memory'

    @classmethod
    def cache_status(cls) -> dict[str, Any]:
        """Return non-sensitive cache health/status details."""
        return {
            'enabled': cls._cache_enabled,
            'backend': cls.cache_backend(),
            'default_ttl_seconds': cls._cache_default_ttl,
            'memory_entries': len(cls._memory_cache),
            'prefix': cls._cache_prefix,
        }

    @classmethod
    def _normalize_key(cls, cache_key: str) -> str:
        key = str(cache_key or '').strip()
        return f'{cls._cache_prefix}:{key}' if key else f'{cls._cache_prefix}:default'

    @classmethod
    def get_cache(cls, cache_key: str) -> Any | None:
        """Get a cached JSON-serializable payload or None."""
        if not cls._cache_enabled:
            return None

        key = cls._normalize_key(cache_key)
        if cls.cache_backend() == 'redis' and cls._redis_client is not None:
            try:
                raw_value = cls._redis_client.get(key)
                if raw_value is None:
                    return None
                return json.loads(raw_value)
            except Exception as exc:
                logger.warning('Redis cache read failed for key=%s: %s', key, exc)
                return None

        entry = cls._memory_cache.get(key)
        if not entry:
            return None

        expires_at, value = entry
        if datetime.now(timezone.utc) >= expires_at:
            cls._memory_cache.pop(key, None)
            return None
        return value

    @classmethod
    def set_cache(cls, cache_key: str, value: Any, ttl_seconds: int | None = None) -> None:
        """Store a cached payload with TTL."""
        if not cls._cache_enabled:
            return

        key = cls._normalize_key(cache_key)
        ttl = cls._cache_default_ttl if ttl_seconds is None else int(ttl_seconds)
        ttl = max(1, min(ttl, 3600))

        if cls.cache_backend() == 'redis' and cls._redis_client is not None:
            try:
                cls._redis_client.setex(key, ttl, json.dumps(value))
                return
            except Exception as exc:
                logger.warning('Redis cache write failed for key=%s: %s', key, exc)

        cls._memory_cache[key] = (datetime.now(timezone.utc) + timedelta(seconds=ttl), value)

    @classmethod
    def get_or_compute(
        cls,
        cache_key: str,
        loader: Callable[[], Any],
        ttl_seconds: int | None = None,
    ) -> tuple[Any, bool]:
        """Return cached value if present, else compute and cache it.

        Returns (value, cache_hit).
        """
        cached = cls.get_cache(cache_key)
        if cached is not None:
            return cached, True

        value = loader()
        cls.set_cache(cache_key, value, ttl_seconds=ttl_seconds)
        return value, False

    @staticmethod
    def get_recent_system_rows(organization_id: int, limit: int = 10):
        """Return recent system rows with a slim column projection."""
        limit = max(1, min(int(limit), 100))
        return (
            SystemData.query
            .options(
                load_only(
                    SystemData.id,
                    SystemData.organization_id,
                    SystemData.hostname,
                    SystemData.serial_number,
                    SystemData.status,
                    SystemData.last_update,
                )
            )
            .filter_by(organization_id=organization_id)
            .order_by(SystemData.last_update.desc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_dashboard_counts(organization_id: int) -> dict[str, int]:
        """Return optimized dashboard counts in one aggregate query."""
        active_cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=5)
        total_count, active_count = (
            db.session.query(
                func.count(SystemData.id),
                func.coalesce(
                    func.sum(
                        case(
                            (SystemData.last_update >= active_cutoff, 1),
                            else_=0,
                        )
                    ),
                    0,
                ),
            )
            .filter(SystemData.organization_id == organization_id)
            .one()
        )
        return {
            'total_systems': int(total_count or 0),
            'active_systems': int(active_count or 0),
        }

    @staticmethod
    def build_static_asset_url(asset_path: str, config: dict[str, Any]) -> str:
        """Build CDN-aware static asset URL for templates."""
        clean_path = str(asset_path or '').lstrip('/')
        cdn_enabled = bool(config.get('CDN_ENABLED', False))
        cdn_base = str(config.get('CDN_STATIC_BASE_URL', '')).strip()
        cdn_version = str(config.get('CDN_STATIC_VERSION', '')).strip()

        if not clean_path:
            return '/static/'

        if cdn_enabled and cdn_base:
            base_url = cdn_base.rstrip('/') + '/'
            full_url = urljoin(base_url, clean_path)
            if cdn_version:
                separator = '&' if '?' in full_url else '?'
                full_url = f'{full_url}{separator}v={cdn_version}'
            return full_url

        return f'/static/{clean_path}'

    @staticmethod
    def optimize_database(database_uri: str) -> dict[str, Any]:
        """Run lightweight DB optimizer commands depending on backend."""
        database_uri = str(database_uri or '').lower()
        actions: list[str] = []
        backend = 'unknown'

        if database_uri.startswith('sqlite'):
            backend = 'sqlite'
            db.session.execute(text('PRAGMA optimize'))
            actions.append('PRAGMA optimize')
            db.session.execute(text('ANALYZE'))
            actions.append('ANALYZE')
        elif database_uri.startswith('postgresql'):
            backend = 'postgresql'
            db.session.execute(text('ANALYZE'))
            actions.append('ANALYZE')
        elif database_uri.startswith('mysql'):
            backend = 'mysql'
            db.session.execute(text('ANALYZE TABLE system_data'))
            actions.append('ANALYZE TABLE system_data')
        else:
            return {
                'status': 'skipped',
                'backend': backend,
                'actions': actions,
                'reason': 'unsupported_database_backend',
            }

        db.session.commit()
        return {
            'status': 'success',
            'backend': backend,
            'actions': actions,
        }
