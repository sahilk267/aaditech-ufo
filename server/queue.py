"""Queue foundation for Phase 1 Week 8 (Redis/Celery readiness)."""

import logging

from .tasks import register_background_tasks, get_background_job_handlers


logger = logging.getLogger(__name__)


def init_queue(app):
    """Initialize Celery queue app if dependency is available.

    The app keeps running even when Celery is unavailable so local/test workflows
    do not break.
    """
    try:
        from celery import Celery
        from celery.schedules import crontab
    except Exception as exc:
        logger.warning("Celery unavailable; queue disabled: %s", exc)
        app.extensions['celery'] = None
        app.extensions['queue_tasks'] = {
            'cleanup_revoked_tokens': 'maintenance.cleanup_revoked_tokens',
            'purge_audit_events': 'maintenance.purge_audit_events',
            'dispatch_alert_notifications': 'alerts.dispatch_notifications',
            'execute_automation_workflow': 'automation.execute_workflow',
        }
        app.extensions['queue_handlers'] = get_background_job_handlers()
        return None

    broker_url = app.config.get('CELERY_BROKER_URL') or app.config.get('REDIS_URL')
    result_backend = app.config.get('CELERY_RESULT_BACKEND') or broker_url

    celery_app = Celery(
        app.import_name,
        broker=broker_url,
        backend=result_backend,
    )
    celery_app.conf.update(
        task_serializer='json',
        result_serializer='json',
        accept_content=['json'],
        timezone='UTC',
        enable_utc=True,
        task_always_eager=bool(app.config.get('TESTING', False)),
    )

    queue_tasks = register_background_tasks(app, celery_app)

    if app.config.get('QUEUE_ENABLE_BEAT', True):
        celery_app.conf.beat_schedule = {
            'cleanup-revoked-tokens-daily': {
                'task': queue_tasks['cleanup_revoked_tokens'],
                'schedule': crontab(hour=2, minute=0),
            },
            'purge-audit-events-daily': {
                'task': queue_tasks['purge_audit_events'],
                'schedule': crontab(hour=3, minute=0),
                'args': (int(app.config.get('AUDIT_RETENTION_DAYS', 90)),),
            },
        }

    app.extensions['celery'] = celery_app
    app.extensions['queue_tasks'] = queue_tasks
    app.extensions['queue_handlers'] = get_background_job_handlers()
    logger.info("Celery queue initialized with broker=%s", broker_url)
    return celery_app


def enqueue_maintenance_job(app, job_name, **kwargs):
    """Queue a named maintenance workflow and return task metadata."""
    return _enqueue_named_job(app, job_name, **kwargs)


def enqueue_alert_notification_job(app, **kwargs):
    """Queue alert-notification dispatch workflow and return task metadata."""
    return _enqueue_named_job(app, 'dispatch_alert_notifications', **kwargs)


def enqueue_automation_workflow_job(app, **kwargs):
    """Queue automation workflow execution and return task metadata."""
    return _enqueue_named_job(app, 'execute_automation_workflow', **kwargs)


def _enqueue_named_job(app, job_name, **kwargs):
    """Queue a named workflow using Celery or inline fallback in tests."""
    celery_app = app.extensions.get('celery')
    queue_tasks = app.extensions.get('queue_tasks', {})
    queue_handlers = app.extensions.get('queue_handlers', {})

    task_name = queue_tasks.get(job_name)
    if not task_name:
        raise ValueError(f"Unknown maintenance job: {job_name}")

    if celery_app is None:
        if not app.config.get('TESTING', False):
            return {
                'accepted': False,
                'reason': 'queue_disabled',
            }

        handler = queue_handlers.get(job_name)
        if handler is None:
            raise RuntimeError(f"Job handler not registered: {job_name}")

        result_payload = handler(**kwargs)
        return {
            'accepted': True,
            'task_id': None,
            'job_name': job_name,
            'task_name': task_name,
            'eager': True,
            'inline': True,
            'result': result_payload,
        }

    task = celery_app.tasks.get(task_name)
    if task is None:
        raise RuntimeError(f"Task not registered: {task_name}")

    result = task.apply_async(kwargs=kwargs)
    return {
        'accepted': True,
        'task_id': getattr(result, 'id', None),
        'job_name': job_name,
        'task_name': task_name,
        'eager': bool(celery_app.conf.task_always_eager),
    }


def get_queue_status(app):
    """Return queue health details for API/status visibility."""
    celery_app = app.extensions.get('celery')
    if celery_app is None:
        return {
            'enabled': False,
            'state': 'degraded' if app.config.get('TESTING', False) else 'disabled',
            'broker_url': app.config.get('CELERY_BROKER_URL') or app.config.get('REDIS_URL'),
            'tasks': list(app.extensions.get('queue_tasks', {}).keys()),
            'inline_fallback': bool(app.config.get('TESTING', False)),
        }

    try:
        inspect = celery_app.control.inspect(timeout=1)
        ping = inspect.ping() if inspect else None
        return {
            'enabled': True,
            'state': 'healthy' if ping else 'degraded',
            'broker_url': celery_app.conf.broker_url,
            'workers': list((ping or {}).keys()),
            'tasks': list(app.extensions.get('queue_tasks', {}).keys()),
        }
    except Exception as exc:
        return {
            'enabled': True,
            'state': 'degraded',
            'broker_url': celery_app.conf.broker_url,
            'tasks': list(app.extensions.get('queue_tasks', {}).keys()),
            'error': str(exc),
        }
