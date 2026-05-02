"""Notification delivery service for alert dispatch channels."""

from __future__ import annotations

import json
import logging
import smtplib
from email.message import EmailMessage
from typing import Any
from urllib import request as urllib_request


class NotificationService:
    """Deliver alert notifications to email and webhook channels with retries."""

    logger = logging.getLogger('server.notification')

    @classmethod
    def dispatch_notifications(
        cls,
        alerts: list[dict[str, Any]],
        config: dict[str, Any],
        channels: list[str] | None = None,
        email_retries: int | None = None,
        webhook_retries: int | None = None,
        deduplicate: bool | None = None,
        escalation_threshold: int | None = None,
    ) -> dict[str, Any]:
        channels = channels or ['email', 'webhook']
        email_retries = int(email_retries if email_retries is not None else config.get('email_retries', 2))
        webhook_retries = int(webhook_retries if webhook_retries is not None else config.get('webhook_retries', 2))
        deduplicate = bool(config.get('dedup_enabled', True) if deduplicate is None else deduplicate)
        escalation_threshold = int(
            escalation_threshold
            if escalation_threshold is not None
            else config.get('escalation_repeat_threshold', 3)
        )

        if not alerts:
            return {
                'status': 'success',
                'alerts_count': 0,
                'raw_alerts_count': 0,
                'deduplicated_count': 0,
                'escalated_count': 0,
                'delivered_channels': [],
                'failure_count': 0,
                'failures': [],
            }

        prepared_alerts, deduplicated_count, escalated_count = cls._prepare_alerts(
            alerts,
            deduplicate=deduplicate,
            escalation_threshold=escalation_threshold,
        )

        failures = []
        delivered_channels = []

        if 'email' in channels and config.get('email_enabled'):
            sent, attempts, error = cls._attempt_email(prepared_alerts, config, email_retries)
            if sent:
                delivered_channels.append('email')
            else:
                failures.append({'channel': 'email', 'attempts': attempts, 'error': error})

        if 'webhook' in channels and config.get('webhook_enabled'):
            sent, attempts, error = cls._attempt_webhook(prepared_alerts, config, webhook_retries)
            if sent:
                delivered_channels.append('webhook')
            else:
                failures.append({'channel': 'webhook', 'attempts': attempts, 'error': error})

        return {
            'status': 'success' if not failures else 'partial_failure',
            'alerts_count': len(prepared_alerts),
            'raw_alerts_count': len(alerts),
            'deduplicated_count': deduplicated_count,
            'escalated_count': escalated_count,
            'delivered_channels': delivered_channels,
            'failure_count': len(failures),
            'failures': failures,
        }

    @classmethod
    def _prepare_alerts(
        cls,
        alerts: list[dict[str, Any]],
        deduplicate: bool,
        escalation_threshold: int,
    ) -> tuple[list[dict[str, Any]], int, int]:
        grouped = {}

        for alert in alerts:
            dedup_key = (
                alert.get('rule_id'),
                alert.get('system_id'),
                alert.get('metric'),
                alert.get('operator'),
                alert.get('threshold'),
            )
            if dedup_key not in grouped:
                grouped[dedup_key] = dict(alert)
                grouped[dedup_key]['occurrence_count'] = 1
            else:
                grouped[dedup_key]['occurrence_count'] += 1

                incoming_ts = alert.get('triggered_at') or ''
                existing_ts = grouped[dedup_key].get('triggered_at') or ''
                if incoming_ts > existing_ts:
                    grouped[dedup_key]['triggered_at'] = incoming_ts

        if deduplicate:
            processed = list(grouped.values())
            deduplicated_count = len(alerts) - len(processed)
        else:
            processed = []
            for alert in alerts:
                enriched = dict(alert)
                dedup_key = (
                    alert.get('rule_id'),
                    alert.get('system_id'),
                    alert.get('metric'),
                    alert.get('operator'),
                    alert.get('threshold'),
                )
                enriched['occurrence_count'] = grouped[dedup_key].get('occurrence_count', 1)
                processed.append(enriched)
            deduplicated_count = 0

        escalated_count = cls._apply_escalation(processed, escalation_threshold)
        return processed, deduplicated_count, escalated_count

    @staticmethod
    def _apply_escalation(alerts: list[dict[str, Any]], escalation_threshold: int) -> int:
        escalated = 0
        escalation_threshold = max(1, int(escalation_threshold))

        for alert in alerts:
            count = int(alert.get('occurrence_count', 1))
            if count < escalation_threshold:
                alert['escalated'] = False
                continue

            severity = (alert.get('severity') or 'warning').lower()
            new_severity = severity
            if severity == 'info':
                new_severity = 'warning'
            elif severity == 'warning':
                new_severity = 'critical'

            alert['escalated'] = new_severity != severity
            if alert['escalated']:
                alert['severity'] = new_severity
                escalated += 1

        return escalated

    @classmethod
    def _attempt_email(cls, alerts: list[dict[str, Any]], config: dict[str, Any], retries: int) -> tuple[bool, int, str | None]:
        recipients = [item.strip() for item in (config.get('email_to') or '').split(',') if item.strip()]
        if not recipients:
            return False, 0, 'No recipients configured'

        attempts = 0
        while attempts <= retries:
            attempts += 1
            try:
                cls.send_email_notification(alerts, config, recipients)
                return True, attempts, None
            except Exception as exc:
                if attempts > retries:
                    return False, attempts, str(exc)
        return False, attempts, 'Unknown email delivery error'

    @classmethod
    def _attempt_webhook(cls, alerts: list[dict[str, Any]], config: dict[str, Any], retries: int) -> tuple[bool, int, str | None]:
        webhook_url = config.get('webhook_url') or ''
        if not webhook_url:
            return False, 0, 'No webhook URL configured'

        attempts = 0
        while attempts <= retries:
            attempts += 1
            try:
                cls.send_webhook_notification(alerts, webhook_url)
                return True, attempts, None
            except Exception as exc:
                if attempts > retries:
                    return False, attempts, str(exc)
        return False, attempts, 'Unknown webhook delivery error'

    @staticmethod
    def send_email_notification(alerts: list[dict[str, Any]], config: dict[str, Any], recipients: list[str]):
        """Send a summarized alert email."""
        message = EmailMessage()
        message['Subject'] = f"AADITECH Alert Dispatch ({len(alerts)} alerts)"
        message['From'] = config.get('email_from')
        message['To'] = ', '.join(recipients)

        lines = []
        for alert in alerts:
            lines.append(
                f"- [{alert.get('severity')}] {alert.get('rule_name')} on {alert.get('hostname')}: "
                f"{alert.get('metric')} {alert.get('operator')} {alert.get('threshold')} "
                f"(actual {alert.get('actual_value')})"
            )
        message.set_content('\n'.join(lines))

        try:
            with smtplib.SMTP(config.get('smtp_host'), int(config.get('smtp_port'))) as smtp:
                # Intentionally no auth in initial foundation; can be added in hardening.
                smtp.send_message(message)
            NotificationService.logger.info(
                'Email notification sent to %s (alerts=%d)', recipients, len(alerts)
            )
        except Exception:
            NotificationService.logger.exception('Failed to send email notification')
            raise

    @staticmethod
    def send_webhook_notification(alerts: list[dict[str, Any]], webhook_url: str):
        """Post alert payload to configured webhook."""
        payload = json.dumps({'alerts': alerts}).encode('utf-8')
        req = urllib_request.Request(
            webhook_url,
            data=payload,
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        try:
            with urllib_request.urlopen(req, timeout=5) as resp:
                # read response to ensure any network errors surface
                _ = resp.read()
            NotificationService.logger.info('Webhook notification posted to %s (alerts=%d)', webhook_url, len(alerts))
        except Exception:
            NotificationService.logger.exception('Failed to post webhook notification to %s', webhook_url)
            raise
