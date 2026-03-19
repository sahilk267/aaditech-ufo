"""Advanced dashboard aggregator service for Phase 2 Week 16.4 foundation."""

from __future__ import annotations

import re
from typing import Any

from .reliability_service import ReliabilityService
from .update_service import UpdateService
from .confidence_service import ConfidenceService


class DashboardService:
    """Business logic for aggregating Week 15 + Week 16 outputs into unified status surface."""

    SAFE_HOST_PATTERN = re.compile(r'^[a-zA-Z0-9_.-]{1,64}$')

    @classmethod
    def get_aggregate_dashboard_status(
        cls,
        host_name: str,
        runtime_config: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], str | None]:
        """Aggregate all reliability, crash, update, and AI outputs into unified dashboard.
        
        This endpoint orchestrates calls to:
        - ReliabilityService: reliability score, trend, prediction, patterns, crash history
        - UpdateService: pending updates, update status
        - ConfidenceService: AI-scored confidence in the reliability impact
        
        Returns unified status surface with all metrics for operator consumption.
        """
        runtime_config = runtime_config or {}

        host_name = str(host_name or '').strip()
        if not host_name:
            return {'status': 'validation_failed', 'reason': 'host_name_missing'}, 'host_name_missing'

        if not cls.SAFE_HOST_PATTERN.fullmatch(host_name):
            return {'status': 'policy_blocked', 'reason': 'host_name_invalid'}, 'host_name_invalid'

        allowed_hosts = runtime_config.get('allowed_hosts') or []
        if allowed_hosts:
            allowed_set = {str(value).strip() for value in allowed_hosts if str(value).strip()}
            if host_name not in allowed_set:
                return {
                    'status': 'policy_blocked',
                    'reason': 'host_not_allowlisted',
                    'host_name': host_name,
                }, 'host_not_allowlisted'

        # Collect reliability data (Week 15)
        reliability_result, reliability_error = ReliabilityService.score_reliability(
            host_name,
            runtime_config=runtime_config.get('reliability_config') or {},
        )
        if reliability_error and reliability_error != 'command_failed':
            # Don't fail the whole dashboard on individual metric failures
            reliability_result = {
                'status': 'unavailable',
                'reason': reliability_error,
                'reliability_score': {'current_score': 0.0, 'health_band': 'unknown'},
            }

        reliability_score = (reliability_result.get('reliability_score') or {}).get('current_score', 0.0)
        try:
            reliability_score = float(reliability_score)
        except (TypeError, ValueError):
            reliability_score = 0.0
        health_band = (reliability_result.get('reliability_score') or {}).get('health_band', 'unknown')

        # Collect reliability trend (Week 15)
        trend_result, trend_error = ReliabilityService.analyze_reliability_trend(
            host_name,
            runtime_config=runtime_config.get('reliability_config') or {},
        )
        if trend_error:
            trend_result = {'trend': {'direction': 'unknown', 'point_count': 0}}

        trend_data = trend_result.get('trend') or {}

        # Collect reliability prediction (Week 15)
        prediction_result, prediction_error = ReliabilityService.predict_reliability(
            host_name,
            runtime_config=runtime_config.get('reliability_config') or {},
        )
        if prediction_error:
            prediction_result = {'prediction': {'direction': 'unknown', 'predicted_score': reliability_score}}

        prediction_data = prediction_result.get('prediction') or {}

        # Collect pattern detection (Week 15)
        pattern_result, pattern_error = ReliabilityService.detect_reliability_patterns(
            host_name,
            runtime_config=runtime_config.get('reliability_config') or {},
        )
        if pattern_error:
            pattern_result = {'patterns': {'primary_pattern': 'unknown', 'pattern_count': 0}}

        pattern_data = pattern_result.get('patterns') or {}

        # Collect crash history stats (Week 15) - inferred from reliability history
        history_result, history_error = ReliabilityService.collect_reliability_history(
            host_name,
            runtime_config=runtime_config.get('reliability_config') or {},
        )
        if history_error:
            history_result = {'records': [], 'record_count': 0}

        history_records = history_result.get('records') or []
        crash_count = cls._count_crashes_from_history(history_records)
        latest_crash = cls._get_latest_crash_from_history(history_records)

        # Collect pending updates (Week 16.2)
        updates_result, updates_error = UpdateService.monitor_windows_updates(
            host_name,
            runtime_config=runtime_config.get('update_config') or {},
        )
        if updates_error:
            updates_result = {
                'status': 'unavailable',
                'updates': [],
                'update_count': 0,
                'latest_installed_on': '',
            }

        updates_list = updates_result.get('updates') or []
        update_count = len(updates_list)
        latest_installed_on = updates_result.get('latest_installed_on') or ''

        # Score update reliability impact with AI (Week 16.3)
        confidence_result, confidence_error = ConfidenceService.score_update_reliability_impact(
            host_name,
            updates_list=updates_list,
            reliability_score=reliability_score,
            runtime_config=runtime_config.get('confidence_config') or {},
        )
        if confidence_error:
            confidence_result = {
                'status': 'unavailable',
                'confidence_score': 0.5,
                'risk_factors': [],
                'impact_summary': '',
            }

        confidence_score = confidence_result.get('confidence_score', 0.5)
        try:
            confidence_score = float(confidence_score)
        except (TypeError, ValueError):
            confidence_score = 0.5
        risk_factors = confidence_result.get('risk_factors') or []
        impact_summary = confidence_result.get('impact_summary') or ''

        # Determine update risk classification
        update_risk = cls._classify_update_risk(confidence_score, reliability_score, update_count)

        # Determine overall aggregate health status
        aggregate_status = cls._compute_aggregate_health(
            reliability_score,
            crash_count,
            trend_data.get('direction'),
            update_count,
            confidence_score,
        )

        return {
            'status': 'success',
            'host_name': host_name,
            'aggregate_health': {
                'overall_status': aggregate_status,
                'health_band': health_band,
                'last_updated': cls._current_iso_timestamp(),
            },
            'reliability': {
                'current_score': reliability_score,
                'health_band': health_band,
                'adapter': reliability_result.get('adapter', 'unknown'),
            },
            'crash_analysis': {
                'crash_count': crash_count,
                'latest_crash': latest_crash,
                'pattern': pattern_data.get('primary_pattern', 'unknown'),
                'pattern_count': pattern_data.get('pattern_count', 0),
            },
            'trend': {
                'direction': trend_data.get('direction', 'unknown'),
                'point_count': trend_data.get('point_count', 0),
            },
            'prediction': {
                'direction': prediction_data.get('direction', 'unknown'),
                'predicted_score': prediction_data.get('predicted_score', reliability_score),
            },
            'updates': {
                'pending_count': update_count,
                'latest_installed_date': latest_installed_on,
                'update_risk': update_risk,
                'impact_summary': impact_summary,
            },
            'ai_confidence': {
                'confidence_score': confidence_score,
                'risk_factors': risk_factors[:3],
                'adapter': confidence_result.get('adapter', 'unknown'),
            },
            'dashboard_version': 'aggregator-v1',
        }, None

    @staticmethod
    def _count_crashes_from_history(records: list[dict[str, Any]]) -> int:
        """Count crash entries from reliability history records."""
        crash_count = 0
        for record in records:
            source_text = str(record.get('source') or '').lower()
            message_text = str(record.get('message') or '').lower()
            product_text = str(record.get('product') or '').lower()
            type_text = str(record.get('type') or '').lower()
            combined = ' '.join([source_text, message_text, product_text, type_text])
            if 'crash' in combined or 'error' in combined or 'fault' in combined:
                crash_count += 1
        return crash_count

    @staticmethod
    def _get_latest_crash_from_history(records: list[dict[str, Any]]) -> str:
        """Extract latest crash timestamp from reliability history."""
        for record in records:
            source_text = str(record.get('source') or '').lower()
            message_text = str(record.get('message') or '').lower()
            product_text = str(record.get('product') or '').lower()
            type_text = str(record.get('type') or '').lower()
            combined = ' '.join([source_text, message_text, product_text, type_text])
            if 'crash' in combined or 'error' in combined or 'fault' in combined:
                return str(record.get('timestamp') or record.get('date') or '')
        return ''

    @staticmethod
    def _classify_update_risk(confidence_score: float, reliability_score: float, update_count: int) -> str:
        """Classify overall update risk based on confidence score, reliability, and update count."""
        if confidence_score < 0.3 or reliability_score < 0.4:
            return 'critical'
        if confidence_score < 0.5 or (reliability_score < 0.6 and update_count > 3):
            return 'high'
        if confidence_score < 0.7 or (reliability_score < 0.7 and update_count > 0):
            return 'medium'
        return 'low'

    @staticmethod
    def _compute_aggregate_health(
        reliability_score: float,
        crash_count: int,
        trend_direction: str | None,
        update_count: int,
        confidence_score: float,
    ) -> str:
        """Compute overall aggregate health status across all metrics."""
        if reliability_score < 0.3 and crash_count > 0:
            return 'critical'
        if reliability_score < 0.5:
            return 'poor'
        if reliability_score < 0.7:
            if trend_direction == 'declining' and update_count > 3:
                return 'at-risk'
            if crash_count > 2 or confidence_score < 0.4:
                return 'degraded'
            return 'moderate'
        if reliability_score < 0.85:
            if trend_direction == 'declining':
                return 'stable-but-declining'
            if update_count > 5:
                return 'stable-updates-pending'
            return 'good'
        return 'excellent'

    @staticmethod
    def _current_iso_timestamp() -> str:
        """Return current timestamp in ISO 8601 format."""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()
