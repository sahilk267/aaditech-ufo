"""Alerting domain service for threshold rule management and evaluation."""

from __future__ import annotations

from datetime import datetime, UTC
import logging
from statistics import mean, pstdev
from typing import Any

from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from ..extensions import db
from ..models import AlertRule, AlertSilence, SystemData


class AlertService:
    """Business logic for tenant-scoped alert rules."""

    logger = logging.getLogger('server.alert')

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
    def _commit_with_rollback(
        duplicate_field: str | None = None,
        duplicate_message: str | None = None,
        generic_message: str = 'Database operation failed.',
    ) -> dict[str, list[str]]:
        try:
            db.session.commit()
            return {}
        except IntegrityError:
            db.session.rollback()
            if duplicate_field and duplicate_message:
                return {duplicate_field: [duplicate_message]}
            return {'database': ['Constraint violation.']}
        except SQLAlchemyError:
            db.session.rollback()
            return {'database': [generic_message]}

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
        commit_errors = cls._commit_with_rollback(
            duplicate_field='name',
            duplicate_message='Alert rule name already exists for this tenant.',
            generic_message='Failed to persist alert rule.',
        )
        if commit_errors:
            return None, commit_errors
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

        commit_errors = cls._commit_with_rollback(
            duplicate_field='name',
            duplicate_message='Alert rule name already exists for this tenant.',
            generic_message='Failed to update alert rule.',
        )
        if commit_errors:
            return None, commit_errors, None
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

    # ------------------------------------------------------------------
    # Alert Silence (Suppression) management
    # ------------------------------------------------------------------

    @staticmethod
    def list_silences(organization_id: int) -> list[AlertSilence]:
        """Return all active+pending silences for a tenant (not yet expired)."""
        now = datetime.now(UTC)
        return (
            AlertSilence.query
            .filter_by(organization_id=organization_id)
            .filter(AlertSilence.ends_at > now.replace(tzinfo=None))
            .order_by(AlertSilence.starts_at.asc())
            .all()
        )

    @classmethod
    def create_silence(
        cls,
        organization_id: int,
        payload: dict[str, Any],
    ) -> tuple[AlertSilence | None, dict[str, list[str]]]:
        """Create an alert silence window. At least one of rule_id or metric required."""
        errors: dict[str, list[str]] = {}

        rule_id = payload.get('rule_id')
        metric = payload.get('metric')
        ends_at_raw = payload.get('ends_at')

        if not rule_id and not metric:
            errors['rule_id'] = ['At least one of rule_id or metric is required.']

        if metric is not None and metric not in cls.ALLOWED_METRICS:
            errors.setdefault('metric', []).append('Unsupported metric name.')

        if rule_id is not None:
            try:
                rule_id = int(rule_id)
                if not AlertRule.query.filter_by(id=rule_id, organization_id=organization_id).first():
                    errors.setdefault('rule_id', []).append('Alert rule not found for this tenant.')
            except (TypeError, ValueError):
                errors.setdefault('rule_id', []).append('rule_id must be an integer.')

        if not ends_at_raw:
            errors['ends_at'] = ['ends_at is required (ISO 8601 datetime).']
        else:
            try:
                ends_at = datetime.fromisoformat(str(ends_at_raw).replace('Z', '+00:00'))
                if ends_at.tzinfo is not None:
                    ends_at = ends_at.replace(tzinfo=None)
                if ends_at <= datetime.now(UTC).replace(tzinfo=None):
                    errors.setdefault('ends_at', []).append('ends_at must be a future datetime.')
            except ValueError:
                errors.setdefault('ends_at', []).append('ends_at must be a valid ISO 8601 datetime.')

        if errors:
            return None, errors

        reason = str(payload.get('reason', '')).strip()[:255] or None
        starts_at_raw = payload.get('starts_at')
        starts_at = datetime.now(UTC).replace(tzinfo=None)
        if starts_at_raw:
            try:
                parsed = datetime.fromisoformat(str(starts_at_raw).replace('Z', '+00:00'))
                starts_at = parsed.replace(tzinfo=None)
            except ValueError:
                AlertService.logger.debug('Failed to parse starts_at=%r; using now', starts_at_raw)

        silence = AlertSilence(
            organization_id=organization_id,
            rule_id=rule_id,
            metric=metric,
            reason=reason,
            starts_at=starts_at,
            ends_at=ends_at,
        )
        db.session.add(silence)
        commit_errors = cls._commit_with_rollback(generic_message='Failed to persist alert silence.')
        if commit_errors:
            return None, commit_errors
        return silence, {}

    @staticmethod
    def delete_silence(organization_id: int, silence_id: int) -> bool:
        """Delete a specific silence. Returns True if deleted, False if not found."""
        silence = AlertSilence.query.filter_by(id=silence_id, organization_id=organization_id).first()
        if not silence:
            return False
        db.session.delete(silence)
        return not bool(AlertService._commit_with_rollback(generic_message='Failed to delete alert silence.'))

    @staticmethod
    def filter_silenced_alerts(
        organization_id: int,
        alerts: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Split alerts into (active, suppressed) based on silence windows.

        Returns (active_alerts, silenced_alerts).
        """
        now = datetime.now(UTC).replace(tzinfo=None)
        silences = (
            AlertSilence.query
            .filter_by(organization_id=organization_id)
            .filter(AlertSilence.starts_at <= now, AlertSilence.ends_at > now)
            .all()
        )
        if not silences:
            return alerts, []

        silenced_rule_ids = {s.rule_id for s in silences if s.rule_id is not None}
        silenced_metrics = {s.metric for s in silences if s.metric is not None}

        active: list[dict[str, Any]] = []
        suppressed: list[dict[str, Any]] = []
        for alert in alerts:
            if alert.get('rule_id') in silenced_rule_ids:
                suppressed.append(alert)
            elif alert.get('metric') in silenced_metrics:
                suppressed.append(alert)
            else:
                active.append(alert)

        return active, suppressed

    # ------------------------------------------------------------------
    # Pattern-Based Alerts
    # ------------------------------------------------------------------

    @classmethod
    def evaluate_patterns_for_tenant(
        cls,
        organization_id: int,
        min_occurrences: int = 3,
        window_size: int = 10,
    ) -> list[dict[str, Any]]:
        """Detect repeating-threshold pattern alerts.

        A pattern alert fires when a metric from an alert rule has
        *min_occurrences* or more violations within the last *window_size*
        data rows, indicating persistent rather than one-off spikes.
        """
        rules = AlertRule.query.filter_by(organization_id=organization_id, is_active=True).all()
        if not rules:
            return []

        history_rows = (
            SystemData.query
            .filter_by(organization_id=organization_id, deleted=False)
            .order_by(SystemData.last_update.desc())
            .limit(window_size)
            .all()
        )
        if not history_rows:
            return []

        detected_at = datetime.now(UTC).isoformat()
        pattern_alerts: list[dict[str, Any]] = []

        for rule in rules:
            values = [
                float(getattr(row, rule.metric))
                for row in history_rows
                if getattr(row, rule.metric, None) is not None
            ]
            if not values:
                continue

            violation_count = sum(
                1 for v in values if cls._compare(v, rule.operator, float(rule.threshold))
            )
            if violation_count < min_occurrences:
                continue

            violation_rate = round(violation_count / len(values), 3)
            pattern_alerts.append({
                'alert_type': 'pattern',
                'rule_id': rule.id,
                'rule_name': rule.name,
                'severity': rule.severity,
                'metric': rule.metric,
                'operator': rule.operator,
                'threshold': rule.threshold,
                'window_size': len(values),
                'violation_count': violation_count,
                'violation_rate': violation_rate,
                'min_occurrences': min_occurrences,
                'detected_at': detected_at,
            })

        return pattern_alerts

    # ------------------------------------------------------------------
    # AI Alert Prioritization (Phase 2 remaining item)
    # ------------------------------------------------------------------

    # Severity score weights
    _SEVERITY_WEIGHTS: dict[str, float] = {'critical': 3.0, 'warning': 1.5, 'info': 0.5}
    # Alert type score boosts
    _ALERT_TYPE_BOOSTS: dict[str, float] = {'threshold': 0.0, 'anomaly': 0.5, 'pattern': 1.0}

    @classmethod
    def prioritize_alerts(
        cls,
        alerts: list[dict[str, Any]],
        top_n: int | None = None,
    ) -> list[dict[str, Any]]:
        """Score and rank alerts by urgency.

        Scoring formula:
          priority_score = severity_weight + alert_type_boost + z_score_bonus
        Returns alerts sorted highest-priority first, each enriched with
        a ``priority_score`` and ``priority_rank`` field.
        """
        if not alerts:
            return []

        scored: list[dict[str, Any]] = []
        for alert in alerts:
            severity = str(alert.get('severity') or 'info').lower()
            alert_type = str(alert.get('alert_type') or 'threshold').lower()
            z_score = alert.get('z_score') or 0.0
            violation_rate = alert.get('violation_rate') or 0.0

            severity_weight = cls._SEVERITY_WEIGHTS.get(severity, 0.5)
            type_boost = cls._ALERT_TYPE_BOOSTS.get(alert_type, 0.0)
            # Cap z_score bonus at 2.0 to avoid single anomaly dominating
            z_bonus = min(float(z_score) * 0.15, 2.0)
            # Pattern violation rate adds up to 1.0
            pattern_bonus = min(float(violation_rate), 1.0)

            priority_score = round(severity_weight + type_boost + z_bonus + pattern_bonus, 3)

            scored.append({
                **alert,
                'priority_score': priority_score,
                'priority_rank': 0,  # assigned after sorting
            })

        scored.sort(key=lambda x: x['priority_score'], reverse=True)
        for rank, alert in enumerate(scored, start=1):
            alert['priority_rank'] = rank

        if top_n is not None:
            try:
                top_n = int(top_n)
            except (TypeError, ValueError):
                top_n = None
            if top_n and top_n > 0:
                scored = scored[:top_n]

        return scored

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
