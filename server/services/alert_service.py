"""Alerting domain service for threshold rule management and evaluation."""

from __future__ import annotations

from datetime import datetime, UTC
from statistics import mean, pstdev
from typing import Any

from ..extensions import db
from ..models import AlertRule, SystemData


class AlertService:
    """Business logic for tenant-scoped alert rules."""

    ALLOWED_METRICS = {
        'cpu_usage',
        'ram_usage',
        'storage_usage',
        'software_benchmark',
        'hardware_benchmark',
        'overall_benchmark',
    }
    ALLOWED_OPERATORS = {'>', '>=', '<', '<=', '==', '!='}
    ALLOWED_SEVERITIES = {'info', 'warning', 'critical'}

    @staticmethod
    def list_rules(organization_id: int) -> list[AlertRule]:
        """Return all alert rules for a tenant."""
        return (
            AlertRule.query
            .filter_by(organization_id=organization_id)
            .order_by(AlertRule.created_at.desc())
            .all()
        )

    @classmethod
    def create_rule(cls, organization_id: int, payload: dict[str, Any]) -> tuple[AlertRule | None, dict[str, list[str]]]:
        """Create alert rule if payload is valid."""
        errors = cls._validate_payload(payload, partial=False)
        if errors:
            return None, errors

        rule = AlertRule(
            organization_id=organization_id,
            name=payload['name'].strip(),
            metric=payload['metric'],
            operator=payload['operator'],
            threshold=float(payload['threshold']),
            severity=payload.get('severity', 'warning'),
            is_active=bool(payload.get('is_active', True)),
        )
        db.session.add(rule)
        db.session.commit()
        return rule, {}

    @classmethod
    def update_rule(
        cls,
        organization_id: int,
        rule_id: int,
        payload: dict[str, Any],
    ) -> tuple[AlertRule | None, dict[str, list[str]], str | None]:
        """Update existing tenant rule and return (rule, errors, not_found_reason)."""
        rule = AlertRule.query.filter_by(id=rule_id, organization_id=organization_id).first()
        if not rule:
            return None, {}, 'not_found'

        errors = cls._validate_payload(payload, partial=True)
        if errors:
            return None, errors, None

        if 'name' in payload:
            rule.name = payload['name'].strip()
        if 'metric' in payload:
            rule.metric = payload['metric']
        if 'operator' in payload:
            rule.operator = payload['operator']
        if 'threshold' in payload:
            rule.threshold = float(payload['threshold'])
        if 'severity' in payload:
            rule.severity = payload['severity']
        if 'is_active' in payload:
            rule.is_active = bool(payload['is_active'])

        db.session.commit()
        return rule, {}, None

    @classmethod
    def evaluate_rules_for_tenant(cls, organization_id: int) -> list[dict[str, Any]]:
        """Evaluate active alert rules against latest active systems in tenant."""
        rules = AlertRule.query.filter_by(organization_id=organization_id, is_active=True).all()
        if not rules:
            return []

        systems = (
            SystemData.query
            .filter_by(organization_id=organization_id, deleted=False)
            .order_by(SystemData.last_update.desc())
            .all()
        )
        if not systems:
            return []

        triggered = []
        evaluated_at = datetime.now(UTC).isoformat()

        for system in systems:
            for rule in rules:
                metric_value = getattr(system, rule.metric, None)
                if metric_value is None:
                    continue

                if cls._compare(float(metric_value), rule.operator, float(rule.threshold)):
                    triggered.append({
                        'rule_id': rule.id,
                        'rule_name': rule.name,
                        'severity': rule.severity,
                        'metric': rule.metric,
                        'operator': rule.operator,
                        'threshold': rule.threshold,
                        'actual_value': float(metric_value),
                        'system_id': system.id,
                        'hostname': system.hostname,
                        'serial_number': system.serial_number,
                        'triggered_at': evaluated_at,
                    })

        return triggered

    @classmethod
    def evaluate_anomalies_for_tenant(
        cls,
        organization_id: int,
        z_score_threshold: float = 2.5,
        min_samples: int = 8,
        window_size: int = 50,
    ) -> list[dict[str, Any]]:
        """Detect statistical anomalies on latest system rows for supported metrics."""
        history_rows = (
            SystemData.query
            .filter_by(organization_id=organization_id, deleted=False)
            .order_by(SystemData.last_update.desc())
            .limit(window_size)
            .all()
        )
        if len(history_rows) < min_samples:
            return []

        metric_baselines: dict[str, tuple[float, float]] = {}
        for metric in cls.ALLOWED_METRICS:
            values = [float(getattr(row, metric)) for row in history_rows if getattr(row, metric) is not None]
            if len(values) < min_samples:
                continue
            sigma = pstdev(values)
            if sigma <= 0:
                continue
            metric_baselines[metric] = (mean(values), sigma)

        if not metric_baselines:
            return []

        anomalies = []
        evaluated_at = datetime.now(UTC).isoformat()
        for row in history_rows:
            for metric, (mu, sigma) in metric_baselines.items():
                value = getattr(row, metric)
                if value is None:
                    continue
                z_score = abs((float(value) - mu) / sigma)
                if z_score < float(z_score_threshold):
                    continue

                anomalies.append({
                    'alert_type': 'anomaly',
                    'rule_id': None,
                    'rule_name': f'Anomaly on {metric}',
                    'severity': 'warning' if z_score < (float(z_score_threshold) + 1.0) else 'critical',
                    'metric': metric,
                    'operator': 'z-score>=',
                    'threshold': float(z_score_threshold),
                    'actual_value': float(value),
                    'baseline_mean': mu,
                    'baseline_stddev': sigma,
                    'z_score': z_score,
                    'system_id': row.id,
                    'hostname': row.hostname,
                    'serial_number': row.serial_number,
                    'triggered_at': evaluated_at,
                })

        return anomalies

    @staticmethod
    def correlate_alerts(alerts: list[dict[str, Any]], min_group_size: int = 2) -> list[dict[str, Any]]:
        """Correlate alerts by host/system into grouped incidents."""
        groups: dict[tuple[Any, Any], list[dict[str, Any]]] = {}
        for alert in alerts:
            key = (alert.get('hostname'), alert.get('system_id'))
            groups.setdefault(key, []).append(alert)

        correlated = []
        for (hostname, system_id), items in groups.items():
            metrics = sorted({item.get('metric') for item in items if item.get('metric')})
            if len(metrics) < min_group_size:
                continue

            severities = {item.get('severity') for item in items}
            correlation_severity = 'critical' if 'critical' in severities else 'warning'

            correlated.append({
                'hostname': hostname,
                'system_id': system_id,
                'alert_count': len(items),
                'metric_count': len(metrics),
                'metrics': metrics,
                'correlation_severity': correlation_severity,
                'sample_alerts': items[:3],
            })

        return correlated

    @classmethod
    def _validate_payload(cls, payload: dict[str, Any], partial: bool) -> dict[str, list[str]]:
        errors: dict[str, list[str]] = {}

        required_fields = ['name', 'metric', 'operator', 'threshold']
        if not partial:
            for field in required_fields:
                if field not in payload:
                    errors.setdefault(field, []).append('Field required.')

        if 'name' in payload and not str(payload.get('name', '')).strip():
            errors.setdefault('name', []).append('Name cannot be empty.')

        metric = payload.get('metric')
        if metric is not None and metric not in cls.ALLOWED_METRICS:
            errors.setdefault('metric', []).append('Unsupported metric for threshold alerting.')

        operator = payload.get('operator')
        if operator is not None and operator not in cls.ALLOWED_OPERATORS:
            errors.setdefault('operator', []).append('Unsupported operator.')

        if 'threshold' in payload:
            try:
                float(payload['threshold'])
            except (TypeError, ValueError):
                errors.setdefault('threshold', []).append('Threshold must be a number.')

        severity = payload.get('severity')
        if severity is not None and severity not in cls.ALLOWED_SEVERITIES:
            errors.setdefault('severity', []).append('Severity must be one of info, warning, critical.')

        return errors

    @staticmethod
    def _compare(actual: float, operator: str, threshold: float) -> bool:
        if operator == '>':
            return actual > threshold
        if operator == '>=':
            return actual >= threshold
        if operator == '<':
            return actual < threshold
        if operator == '<=':
            return actual <= threshold
        if operator == '==':
            return actual == threshold
        if operator == '!=':
            return actual != threshold
        return False