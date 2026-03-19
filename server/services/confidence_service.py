"""AI confidence scorer service for Phase 2 Week 16.3 foundation."""

from __future__ import annotations

import re
from typing import Any

from .ai_service import AIService


class ConfidenceService:
    """Business logic for AI confidence scoring of system reliability updates."""

    SAFE_HOST_PATTERN = re.compile(r'^[a-zA-Z0-9_.-]{1,64}$')
    ALLOWED_ADAPTERS = {'ollama_http', 'linux_test_double'}

    # Risk factor classifications
    RISK_FACTOR_MAPPINGS = {
        'crash-history': 'System has recent crash history',
        'reliability-trend-negative': 'Reliability trending downward',
        'driver-errors': 'Driver errors detected',
        'system-unstable': 'System stability compromised',
        'pending-critical-updates': 'Critical updates pending',
    }

    @classmethod
    def score_update_reliability_impact(
        cls,
        host_name: str,
        updates_list: list[dict[str, Any]] | None = None,
        reliability_score: float | None = None,
        ollama_model: str = 'llama3.2',
        runtime_config: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], str | None]:
        """Score the reliability impact of OS updates using AI analysis."""
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

        adapter = str(runtime_config.get('confidence_adapter') or 'linux_test_double').strip()
        if adapter not in cls.ALLOWED_ADAPTERS:
            return {'status': 'policy_blocked', 'reason': 'adapter_not_allowed'}, 'adapter_not_allowed'

        # Normalize inputs
        if updates_list is None:
            updates_list = []
        if not isinstance(updates_list, list):
            updates_list = []

        if reliability_score is None:
            reliability_score = 0.0
        try:
            reliability_score = float(reliability_score)
        except (TypeError, ValueError):
            reliability_score = 0.0
        reliability_score = max(0.0, min(reliability_score, 1.0))

        ollama_model = str(ollama_model or 'llama3.2').strip()
        if not ollama_model:
            ollama_model = 'llama3.2'

        allowed_models = runtime_config.get('confidence_allowed_models') or []
        if allowed_models:
            allowed_set = {str(m).strip() for m in allowed_models if str(m).strip()}
            if ollama_model not in allowed_set:
                return {
                    'status': 'policy_blocked',
                    'reason': 'model_not_allowlisted',
                    'model': ollama_model,
                }, 'model_not_allowlisted'

        if adapter == 'ollama_http':
            return cls._score_with_ollama_analysis(
                host_name,
                updates_list,
                reliability_score,
                ollama_model,
                runtime_config,
            )

        scores_map = runtime_config.get('linux_test_double_confidence_scores') or {}
        return cls._score_with_test_double(
            host_name,
            updates_list,
            reliability_score,
            scores_map,
        )

    @classmethod
    def _score_with_ollama_analysis(
        cls,
        host_name: str,
        updates_list: list[dict[str, Any]],
        reliability_score: float,
        ollama_model: str,
        runtime_config: dict[str, Any],
    ) -> tuple[dict[str, Any], str | None]:
        """Use Ollama to analyze update reliability impact."""
        # Build update summary text
        update_descriptions = []
        for update in updates_list[:8]:
            update_desc = str(update.get('hotfix_id') or update.get('id') or 'unknown')
            if update.get('description'):
                update_desc += f" ({update['description'][:50]})"
            update_descriptions.append(update_desc)

        updates_summary = '; '.join(update_descriptions) if update_descriptions else 'no updates provided'
        health_band = cls._reliability_score_to_band(reliability_score)

        # Build prompt for Ollama
        prompt = (
            f"Analyze the estimated reliability impact of these Windows updates for a system with {health_band} health:\n"
            f"Updates: {updates_summary}\n"
            f"Current reliability score: {reliability_score:.2f}\n"
            f"Provide a confidence score (0.0-1.0), list 2-3 key risk factors, and a brief impact summary."
        )

        # Prepare Ollama runtime config
        ollama_config = {
            'adapter': runtime_config.get('ollama_adapter', 'ollama_http'),
            'endpoint': runtime_config.get('ollama_endpoint', 'http://localhost:11434/api/generate'),
            'model': ollama_model,
            'allowed_models': runtime_config.get('confidence_allowed_models') or [],
            'linux_test_double_responses': runtime_config.get('linux_test_double_responses') or {},
            'timeout_seconds': int(runtime_config.get('command_timeout_seconds', 8)),
            'prompt_max_chars': int(runtime_config.get('prompt_max_chars', 4000)),
            'response_max_chars': int(runtime_config.get('response_max_chars', 4000)),
        }

        inference_result, error = AIService.run_ollama_inference(prompt, runtime_config=ollama_config)
        if error:
            return {
                'status': 'command_failed',
                'adapter': 'ollama_http',
                'host_name': host_name,
                'error_type': error,
                'details': inference_result,
            }, 'command_failed'

        # Parse response
        inference = inference_result.get('inference') or {}
        response_text = str(inference.get('response_text') or '').strip().lower()

        # Extract confidence score from response (heuristic parsing)
        confidence_score = cls._extract_confidence_from_response(response_text, reliability_score)

        # Extract risk factors
        risk_factors = cls._extract_risk_factors_from_response(response_text)
        if not risk_factors:
            # Fallback: determine risk factors based on reliability score and update count
            risk_factors = cls._infer_risk_factors(reliability_score, len(updates_list))

        return {
            'status': 'success',
            'adapter': 'ollama_http',
            'host_name': host_name,
            'confidence_score': confidence_score,
            'risk_factors': risk_factors,
            'impact_summary': response_text[:300],
            'reliability_input_score': reliability_score,
            'updates_analyzed_count': len(updates_list),
            'ollama_model': ollama_model,
            'inference': inference,
            'scoring_version': 'foundation-v1',
        }, None

    @classmethod
    def _score_with_test_double(
        cls,
        host_name: str,
        updates_list: list[dict[str, Any]],
        reliability_score: float,
        scores_map: dict[str, Any],
    ) -> tuple[dict[str, Any], str | None]:
        """Resolve deterministic confidence score for tests/dev on Linux."""
        raw_value = scores_map.get(host_name, '0.75|medium-reliability-impact')
        parts = str(raw_value).split('|')
        confidence_score = 0.75
        if parts and parts[0]:
            try:
                confidence_score = float(parts[0])
            except (TypeError, ValueError):
                confidence_score = 0.75
        confidence_score = max(0.0, min(confidence_score, 1.0))

        risk_factors = []
        if reliability_score < 0.4:
            risk_factors.append('system-unstable')
            risk_factors.append('reliability-trend-negative')
        elif reliability_score < 0.6:
            risk_factors.append('crash-history')
        if len(updates_list) > 5:
            risk_factors.append('pending-critical-updates')

        impact_summary = (
            f"Updates may have moderate impact on system with {cls._reliability_score_to_band(reliability_score)} health. "
            f"{len(updates_list)} updates pending. Recommend staged rollout."
        )

        return {
            'status': 'success',
            'adapter': 'linux_test_double',
            'host_name': host_name,
            'confidence_score': confidence_score,
            'risk_factors': risk_factors[:3],
            'impact_summary': impact_summary,
            'reliability_input_score': reliability_score,
            'updates_analyzed_count': len(updates_list),
            'source': 'configured_test_double',
            'scoring_version': 'foundation-v1',
        }, None

    @staticmethod
    def _reliability_score_to_band(score: float) -> str:
        """Convert numeric reliability score to health band."""
        if score < 0.3:
            return 'critical'
        if score < 0.5:
            return 'poor'
        if score < 0.7:
            return 'moderate'
        if score < 0.85:
            return 'good'
        return 'excellent'

    @staticmethod
    def _extract_confidence_from_response(response_text: str, baseline_score: float) -> float:
        """Extract confidence score from Ollama response using heuristics."""
        response_lower = str(response_text).lower()

        # Look for explicit numeric patterns like "0.75", "75%", etc.
        import re
        patterns = [
            r'confidence[:\s]+([0-1]\.[0-9]{1,2})',
            r'([0-1]\.[0-9]{1,2})\s*(?:confidence|score)',
            r'(\d{1,3})%\s*confidence',
        ]

        for pattern in patterns:
            match = re.search(pattern, response_lower)
            if match:
                try:
                    value = float(match.group(1))
                    if value > 1:
                        value = value / 100.0  # Convert percentage to decimal
                    return max(0.0, min(value, 1.0))
                except (ValueError, IndexError):
                    pass

        # Fallback: infer from sentiment keywords
        negative_keywords = ['risk', 'vulnerab', 'critical', 'high', 'unstable', 'concern']
        positive_keywords = ['low risk', 'stable', 'safe', 'routine', 'standard', 'low concern']

        negative_count = sum(1 for kw in negative_keywords if kw in response_lower)
        positive_count = sum(1 for kw in positive_keywords if kw in response_lower)

        if negative_count > positive_count:
            return max(baseline_score - 0.15, 0.0)
        if positive_count > negative_count:
            return min(baseline_score + 0.1, 1.0)

        return baseline_score

    @staticmethod
    def _extract_risk_factors_from_response(response_text: str) -> list[str]:
        """Extract risk factor mentions from Ollama response."""
        response_lower = str(response_text).lower()
        detected_factors = []

        risk_keywords = {
            'crash-history': ['crash', 'crash history', 'unstable'],
            'reliability-trend-negative': ['trending down', 'declining', 'deteriored', 'worse'],
            'driver-errors': ['driver error', 'driver', 'hardware'],
            'system-unstable': ['unstable', 'unreliable', 'problematic'],
            'pending-critical-updates': ['critical', 'security patch', 'urgent'],
        }

        for factor, keywords in risk_keywords.items():
            for keyword in keywords:
                if keyword in response_lower:
                    if factor not in detected_factors:
                        detected_factors.append(factor)
                    break

        return detected_factors[:3]

    @staticmethod
    def _infer_risk_factors(reliability_score: float, update_count: int) -> list[str]:
        """Infer risk factors based on inputs when response parsing fails."""
        factors = []

        if reliability_score < 0.4:
            factors.append('system-unstable')
            factors.append('reliability-trend-negative')
        elif reliability_score < 0.6:
            factors.append('crash-history')

        if update_count > 5:
            factors.append('pending-critical-updates')

        return factors[:3] if factors else ['routine-updates']
