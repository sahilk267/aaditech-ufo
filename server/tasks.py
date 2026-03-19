"""Background maintenance tasks for queue workers."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any
from flask import current_app

from .extensions import db
from .models import AuditEvent, RevokedToken


logger = logging.getLogger(__name__)


def cleanup_expired_revoked_tokens():
    """Delete expired revoked-token entries to keep revocation table small."""
    now = datetime.utcnow()
    deleted = (
        RevokedToken.query
        .filter(RevokedToken.expires_at.isnot(None), RevokedToken.expires_at < now)
        .delete(synchronize_session=False)
    )
    db.session.commit()
    logger.info("Queue maintenance: cleaned %s expired revoked tokens", deleted)
    return {'deleted': deleted, 'checked_before': now.isoformat()}


def purge_old_audit_events(retention_days=90):
    """Purge old audit events according to retention policy."""
    retention_days = int(retention_days)
    cutoff = datetime.utcnow() - timedelta(days=retention_days)
    deleted = (
        AuditEvent.query
        .filter(AuditEvent.created_at < cutoff)
        .delete(synchronize_session=False)
    )
    db.session.commit()
    logger.info(
        "Queue maintenance: purged %s audit events older than %s days",
        deleted,
        retention_days,
    )
    return {
        'deleted': deleted,
        'retention_days': retention_days,
        'cutoff': cutoff.isoformat(),
    }


def dispatch_alert_notifications(
    organization_id: int,
    alerts: list[dict[str, Any]] | None = None,
    channels: list[str] | None = None,
    email_retries: int | None = None,
    webhook_retries: int | None = None,
    deduplicate: bool | None = None,
    escalation_threshold: int | None = None,
):
    """Dispatch alert notifications via email/webhook channels."""
    from .services import AlertService, NotificationService

    if alerts is None:
        alerts = AlertService.evaluate_rules_for_tenant(organization_id)

    config = {
        'email_enabled': bool(current_app.config.get('ALERT_EMAIL_ENABLED', False)),
        'email_from': current_app.config.get('ALERT_EMAIL_FROM'),
        'email_to': current_app.config.get('ALERT_EMAIL_TO', ''),
        'smtp_host': current_app.config.get('ALERT_SMTP_HOST', 'localhost'),
        'smtp_port': int(current_app.config.get('ALERT_SMTP_PORT', 25)),
        'webhook_enabled': bool(current_app.config.get('ALERT_WEBHOOK_ENABLED', False)),
        'webhook_url': current_app.config.get('ALERT_WEBHOOK_URL', ''),
        'email_retries': int(current_app.config.get('ALERT_NOTIFICATION_EMAIL_RETRIES', 2)),
        'webhook_retries': int(current_app.config.get('ALERT_NOTIFICATION_WEBHOOK_RETRIES', 2)),
        'dedup_enabled': bool(current_app.config.get('ALERT_DEDUP_ENABLED', True)),
        'escalation_repeat_threshold': int(current_app.config.get('ALERT_ESCALATION_REPEAT_THRESHOLD', 3)),
    }

    return NotificationService.dispatch_notifications(
        alerts=alerts,
        config=config,
        channels=channels,
        email_retries=email_retries,
        webhook_retries=webhook_retries,
        deduplicate=deduplicate,
        escalation_threshold=escalation_threshold,
    )


def execute_automation_workflow(
    organization_id: int,
    workflow_id: int,
    payload: dict[str, Any] | None = None,
    dry_run: bool | None = None,
):
    """Execute automation workflow by id."""
    from .services import AutomationService

    if dry_run is None:
        dry_run = bool(current_app.config.get('AUTOMATION_DEFAULT_DRY_RUN', True))

    allowed_services_raw = current_app.config.get('AUTOMATION_ALLOWED_SERVICES', '')
    allowed_services = [
        item.strip()
        for item in str(allowed_services_raw).split(',')
        if item.strip()
    ]

    runtime_config = {
        'allowed_services': allowed_services,
        'restart_binary': current_app.config.get('AUTOMATION_SERVICE_RESTART_BINARY', 'systemctl'),
        'command_timeout_seconds': int(current_app.config.get('AUTOMATION_COMMAND_TIMEOUT_SECONDS', 8)),
    }

    result, error = AutomationService.execute_workflow(
        organization_id=organization_id,
        workflow_id=workflow_id,
        payload=payload,
        dry_run=bool(dry_run),
        runtime_config=runtime_config,
    )

    if error:
        return {
            'status': 'failed',
            'reason': error,
            'workflow_id': workflow_id,
        }

    return {
        'status': 'success',
        'result': result,
    }


def get_background_job_handlers():
    """Return named maintenance job handlers for queue or inline execution."""
    return {
        'cleanup_revoked_tokens': cleanup_expired_revoked_tokens,
        'purge_audit_events': purge_old_audit_events,
        'dispatch_alert_notifications': dispatch_alert_notifications,
        'execute_automation_workflow': execute_automation_workflow,
    }


def register_background_tasks(app, celery_app):
    """Register Celery tasks used by production maintenance workflows."""
    handlers = get_background_job_handlers()

    @celery_app.task(name='maintenance.cleanup_revoked_tokens')
    def cleanup_revoked_tokens_task():
        with app.app_context():
            return handlers['cleanup_revoked_tokens']()

    @celery_app.task(name='maintenance.purge_audit_events')
    def purge_audit_events_task(retention_days=90):
        with app.app_context():
            return handlers['purge_audit_events'](retention_days=retention_days)

    @celery_app.task(name='alerts.dispatch_notifications')
    def dispatch_alert_notifications_task(
        organization_id,
        alerts=None,
        channels=None,
        email_retries=None,
        webhook_retries=None,
        deduplicate=None,
        escalation_threshold=None,
    ):
        with app.app_context():
            return handlers['dispatch_alert_notifications'](
                organization_id=organization_id,
                alerts=alerts,
                channels=channels,
                email_retries=email_retries,
                webhook_retries=webhook_retries,
                deduplicate=deduplicate,
                escalation_threshold=escalation_threshold,
            )

    @celery_app.task(name='automation.execute_workflow')
    def execute_automation_workflow_task(
        organization_id,
        workflow_id,
        payload=None,
        dry_run=None,
    ):
        with app.app_context():
            return handlers['execute_automation_workflow'](
                organization_id=organization_id,
                workflow_id=workflow_id,
                payload=payload,
                dry_run=dry_run,
            )

    return {
        'cleanup_revoked_tokens': 'maintenance.cleanup_revoked_tokens',
        'purge_audit_events': 'maintenance.purge_audit_events',
        'dispatch_alert_notifications': 'alerts.dispatch_notifications',
        'execute_automation_workflow': 'automation.execute_workflow',
    }
