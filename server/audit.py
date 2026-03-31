"""Structured audit logging helpers for sensitive operational actions."""

import json
import logging
from datetime import datetime, UTC

from flask import g, has_request_context, request


audit_logger = logging.getLogger('audit')


def _safe_str(value):
    if value is None:
        return None
    try:
        return str(value)
    except Exception:
        return '<unserializable>'


def _safe_int(value):
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None


def _persist_audit_event(action, outcome, method, path, remote_addr, tenant_id, user_id, metadata):
    """Insert audit event row using engine-level transaction isolation."""
    try:
        from .extensions import db
        from .models import AuditEvent

        insert_stmt = AuditEvent.__table__.insert().values(
            action=action,
            outcome=outcome,
            method=method,
            path=path,
            remote_addr=remote_addr,
            tenant_id=tenant_id,
            user_id=user_id,
            event_metadata=metadata,
        )
        with db.engine.begin() as connection:
            connection.execute(insert_stmt)
    except Exception as exc:
        # Audit logging should never break request handling.
        audit_logger.warning('AUDIT_DB_PERSIST_FAILED action=%s error=%s', action, _safe_str(exc))


def log_audit_event(action: str, outcome: str = 'success', **metadata):
    """Emit a structured audit event for auth/admin operations."""
    event = {
        'ts_utc': datetime.now(UTC).isoformat(),
        'action': action,
        'outcome': outcome,
    }

    if has_request_context():
        tenant = getattr(g, 'tenant', None)
        user = getattr(g, 'current_user', None)

        event['method'] = request.method
        event['path'] = request.path
        event['remote_addr'] = request.remote_addr
        event['tenant_id'] = getattr(tenant, 'id', None)
        event['tenant_slug'] = getattr(tenant, 'slug', None)
        event['user_id'] = getattr(user, 'id', None)
        event['user_email'] = getattr(user, 'email', None)

    explicit_context_keys = {
        'method',
        'path',
        'remote_addr',
        'tenant_id',
        'tenant_slug',
        'user_id',
        'user_email',
    }

    for key, value in metadata.items():
        safe_value = _safe_str(value)
        if key in explicit_context_keys and event.get(key) is None:
            event[key] = safe_value
        else:
            event[key] = safe_value

    _persist_audit_event(
        action=action,
        outcome=outcome,
        method=event.get('method'),
        path=event.get('path'),
        remote_addr=event.get('remote_addr'),
        tenant_id=_safe_int(event.get('tenant_id')),
        user_id=_safe_int(event.get('user_id')),
        metadata={k: v for k, v in event.items() if k not in {'method', 'path', 'remote_addr', 'tenant_id', 'user_id'}},
    )

    audit_logger.info('AUDIT %s', json.dumps(event, sort_keys=True))
