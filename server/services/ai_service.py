"""AI service wrapper for Phase 2 Week 16 Ollama foundation."""

from __future__ import annotations

import re
from typing import Any

import requests


class AIService:
    """Business logic for safe Ollama wrapper boundaries."""

    SAFE_MODEL_PATTERN = re.compile(r'^[a-zA-Z0-9_.:-]{1,64}$')
    SAFE_ENDPOINT_PATTERN = re.compile(r'^https?://[a-zA-Z0-9_.:-]{1,255}/[a-zA-Z0-9_./-]{1,255}$')
    ALLOWED_ADAPTERS = {'ollama_http', 'linux_test_double'}

    @classmethod
    def assist_troubleshooting(
        cls,
        question: str,
        context_items: list[str] | None = None,
        runtime_config: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], str | None]:
        """Provide structured troubleshooting guidance via Ollama wrapper."""
        runtime_config = runtime_config or {}

        question = str(question or '').strip()
        if not question:
            return {'status': 'validation_failed', 'reason': 'question_missing'}, 'question_missing'
        if cls._contains_unsafe_control_characters(question):
            return {'status': 'policy_blocked', 'reason': 'question_invalid'}, 'question_invalid'

        max_question_chars = runtime_config.get('max_question_chars', 1200)
        try:
            max_question_chars = int(max_question_chars)
        except (TypeError, ValueError):
            max_question_chars = 1200
        max_question_chars = max(50, min(max_question_chars, 4000))
        if len(question) > max_question_chars:
            return {
                'status': 'policy_blocked',
                'reason': 'question_too_long',
                'max_question_chars': max_question_chars,
            }, 'question_too_long'

        if context_items is None:
            context_items = []
        if not isinstance(context_items, list):
            return {'status': 'validation_failed', 'reason': 'context_items_invalid'}, 'context_items_invalid'

        max_context_items = runtime_config.get('max_context_items', 10)
        try:
            max_context_items = int(max_context_items)
        except (TypeError, ValueError):
            max_context_items = 10
        max_context_items = max(0, min(max_context_items, 25))

        normalized_context: list[str] = []
        for item in context_items:
            normalized = str(item or '').strip()
            if not normalized:
                continue
            if cls._contains_unsafe_control_characters(normalized):
                return {'status': 'policy_blocked', 'reason': 'context_item_invalid'}, 'context_item_invalid'
            normalized_context.append(normalized)
        normalized_context = normalized_context[:max_context_items]

        max_steps = runtime_config.get('max_steps', 5)
        try:
            max_steps = int(max_steps)
        except (TypeError, ValueError):
            max_steps = 5
        max_steps = max(1, min(max_steps, 12))

        prompt_text = cls._build_troubleshooting_prompt(question, normalized_context, max_steps)
        inference_result, error = cls.run_ollama_inference(prompt_text, runtime_config=runtime_config)
        if error:
            return inference_result, error

        inference = inference_result.get('inference') or {}
        response_text = str(inference.get('response_text') or '').strip()
        guidance = cls._parse_troubleshooting_response(response_text, max_steps)

        return {
            'status': 'success',
            'adapter': inference_result.get('adapter'),
            'model': inference_result.get('model'),
            'question': question,
            'context_count': len(normalized_context),
            'guidance': guidance,
            'inference': inference,
        }, None

    @classmethod
    def learn_from_resolution(
        cls,
        issue_summary: str,
        resolution_summary: str,
        outcome: str = 'resolved',
        tags: list[str] | None = None,
        runtime_config: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], str | None]:
        """Extract reusable lessons from operator feedback via Ollama wrapper."""
        runtime_config = runtime_config or {}

        issue_summary = str(issue_summary or '').strip()
        if not issue_summary:
            return {'status': 'validation_failed', 'reason': 'issue_summary_missing'}, 'issue_summary_missing'
        if cls._contains_unsafe_control_characters(issue_summary):
            return {'status': 'policy_blocked', 'reason': 'issue_summary_invalid'}, 'issue_summary_invalid'

        resolution_summary = str(resolution_summary or '').strip()
        if not resolution_summary:
            return {'status': 'validation_failed', 'reason': 'resolution_summary_missing'}, 'resolution_summary_missing'
        if cls._contains_unsafe_control_characters(resolution_summary):
            return {'status': 'policy_blocked', 'reason': 'resolution_summary_invalid'}, 'resolution_summary_invalid'

        outcome = str(outcome or 'resolved').strip().lower()
        if outcome not in {'resolved', 'mitigated', 'unresolved'}:
            return {'status': 'validation_failed', 'reason': 'outcome_invalid'}, 'outcome_invalid'

        if tags is None:
            tags = []
        if not isinstance(tags, list):
            return {'status': 'validation_failed', 'reason': 'tags_invalid'}, 'tags_invalid'

        max_tags = runtime_config.get('max_tags', 8)
        try:
            max_tags = int(max_tags)
        except (TypeError, ValueError):
            max_tags = 8
        max_tags = max(0, min(max_tags, 20))

        normalized_tags: list[str] = []
        for item in tags:
            normalized = str(item or '').strip()
            if not normalized:
                continue
            if cls._contains_unsafe_control_characters(normalized):
                return {'status': 'policy_blocked', 'reason': 'tag_invalid'}, 'tag_invalid'
            normalized_tags.append(normalized)
        normalized_tags = normalized_tags[:max_tags]

        prompt_text = cls._build_learning_prompt(
            issue_summary,
            resolution_summary,
            outcome,
            normalized_tags,
        )
        inference_result, error = cls.run_ollama_inference(prompt_text, runtime_config=runtime_config)
        if error:
            return inference_result, error

        inference = inference_result.get('inference') or {}
        response_text = str(inference.get('response_text') or '').strip()
        learning = cls._parse_learning_response(response_text)

        return {
            'status': 'success',
            'adapter': inference_result.get('adapter'),
            'model': inference_result.get('model'),
            'issue_summary': issue_summary,
            'outcome': outcome,
            'tag_count': len(normalized_tags),
            'learning': learning,
            'inference': inference,
        }, None

    @classmethod
    def generate_recommendations(
        cls,
        symptom_summary: str,
        probable_cause: str,
        evidence_points: list[str] | None = None,
        runtime_config: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], str | None]:
        """Generate remediation recommendations via Ollama wrapper."""
        runtime_config = runtime_config or {}

        symptom_summary = str(symptom_summary or '').strip()
        if not symptom_summary:
            return {'status': 'validation_failed', 'reason': 'symptom_summary_missing'}, 'symptom_summary_missing'
        if cls._contains_unsafe_control_characters(symptom_summary):
            return {'status': 'policy_blocked', 'reason': 'symptom_summary_invalid'}, 'symptom_summary_invalid'

        probable_cause = str(probable_cause or '').strip()
        if not probable_cause:
            return {'status': 'validation_failed', 'reason': 'probable_cause_missing'}, 'probable_cause_missing'
        if cls._contains_unsafe_control_characters(probable_cause):
            return {'status': 'policy_blocked', 'reason': 'probable_cause_invalid'}, 'probable_cause_invalid'

        if evidence_points is None:
            evidence_points = []
        if not isinstance(evidence_points, list):
            return {'status': 'validation_failed', 'reason': 'evidence_points_invalid'}, 'evidence_points_invalid'

        max_evidence_points = runtime_config.get('max_evidence_points', 8)
        try:
            max_evidence_points = int(max_evidence_points)
        except (TypeError, ValueError):
            max_evidence_points = 8
        max_evidence_points = max(0, min(max_evidence_points, 20))

        normalized_evidence: list[str] = []
        for item in evidence_points:
            normalized = str(item or '').strip()
            if not normalized:
                continue
            if cls._contains_unsafe_control_characters(normalized):
                return {'status': 'policy_blocked', 'reason': 'evidence_point_invalid'}, 'evidence_point_invalid'
            normalized_evidence.append(normalized)
        normalized_evidence = normalized_evidence[:max_evidence_points]

        max_recommendations = runtime_config.get('max_recommendations', 3)
        try:
            max_recommendations = int(max_recommendations)
        except (TypeError, ValueError):
            max_recommendations = 3
        max_recommendations = max(1, min(max_recommendations, 10))

        prompt_text = cls._build_recommendation_prompt(
            symptom_summary,
            probable_cause,
            normalized_evidence,
            max_recommendations,
        )
        inference_result, error = cls.run_ollama_inference(prompt_text, runtime_config=runtime_config)
        if error:
            return inference_result, error

        inference = inference_result.get('inference') or {}
        response_text = str(inference.get('response_text') or '').strip()
        recommendation_data = cls._parse_recommendation_response(response_text, max_recommendations)

        return {
            'status': 'success',
            'adapter': inference_result.get('adapter'),
            'model': inference_result.get('model'),
            'symptom_summary': symptom_summary,
            'probable_cause': probable_cause,
            'recommendations': recommendation_data,
            'inference': inference,
        }, None

    @classmethod
    def analyze_root_cause(
        cls,
        symptom_summary: str,
        evidence_points: list[str] | None = None,
        runtime_config: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], str | None]:
        """Analyze probable root cause from symptoms/evidence via Ollama wrapper."""
        runtime_config = runtime_config or {}

        symptom_summary = str(symptom_summary or '').strip()
        if not symptom_summary:
            return {'status': 'validation_failed', 'reason': 'symptom_summary_missing'}, 'symptom_summary_missing'

        if cls._contains_unsafe_control_characters(symptom_summary):
            return {'status': 'policy_blocked', 'reason': 'symptom_summary_invalid'}, 'symptom_summary_invalid'

        max_summary_chars = runtime_config.get('max_summary_chars', 1000)
        try:
            max_summary_chars = int(max_summary_chars)
        except (TypeError, ValueError):
            max_summary_chars = 1000
        max_summary_chars = max(50, min(max_summary_chars, 4000))

        if len(symptom_summary) > max_summary_chars:
            return {
                'status': 'policy_blocked',
                'reason': 'symptom_summary_too_long',
                'max_summary_chars': max_summary_chars,
            }, 'symptom_summary_too_long'

        max_evidence_points = runtime_config.get('max_evidence_points', 8)
        try:
            max_evidence_points = int(max_evidence_points)
        except (TypeError, ValueError):
            max_evidence_points = 8
        max_evidence_points = max(1, min(max_evidence_points, 20))

        if evidence_points is None:
            evidence_points = []
        if not isinstance(evidence_points, list):
            return {'status': 'validation_failed', 'reason': 'evidence_points_invalid'}, 'evidence_points_invalid'

        normalized_evidence: list[str] = []
        for item in evidence_points:
            normalized = str(item or '').strip()
            if not normalized:
                continue
            if cls._contains_unsafe_control_characters(normalized):
                return {'status': 'policy_blocked', 'reason': 'evidence_point_invalid'}, 'evidence_point_invalid'
            normalized_evidence.append(normalized)

        normalized_evidence = normalized_evidence[:max_evidence_points]
        if not normalized_evidence:
            return {'status': 'validation_failed', 'reason': 'evidence_points_missing'}, 'evidence_points_missing'

        prompt_text = cls._build_root_cause_prompt(symptom_summary, normalized_evidence)
        inference_result, error = cls.run_ollama_inference(prompt_text, runtime_config=runtime_config)
        if error:
            return inference_result, error

        inference = inference_result.get('inference') or {}
        response_text = str(inference.get('response_text') or '').strip()
        root_cause = cls._parse_root_cause_response(response_text)

        return {
            'status': 'success',
            'adapter': inference_result.get('adapter'),
            'model': inference_result.get('model'),
            'symptom_summary': symptom_summary,
            'evidence_count': len(normalized_evidence),
            'root_cause': root_cause,
            'inference': inference,
        }, None

    @classmethod
    def run_ollama_inference(
        cls,
        prompt_text: str,
        runtime_config: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], str | None]:
        """Run Ollama inference through a safe adapter boundary."""
        runtime_config = runtime_config or {}

        prompt_text = str(prompt_text or '').strip()
        if not prompt_text:
            return {'status': 'validation_failed', 'reason': 'prompt_missing'}, 'prompt_missing'

        prompt_max_chars = runtime_config.get('prompt_max_chars', 4000)
        try:
            prompt_max_chars = int(prompt_max_chars)
        except (TypeError, ValueError):
            prompt_max_chars = 4000
        prompt_max_chars = max(50, min(prompt_max_chars, 8000))

        if len(prompt_text) > prompt_max_chars:
            return {
                'status': 'policy_blocked',
                'reason': 'prompt_too_long',
                'max_prompt_chars': prompt_max_chars,
            }, 'prompt_too_long'

        if cls._contains_unsafe_control_characters(prompt_text):
            return {'status': 'policy_blocked', 'reason': 'prompt_invalid'}, 'prompt_invalid'

        adapter = str(runtime_config.get('adapter') or 'linux_test_double').strip()
        if adapter not in cls.ALLOWED_ADAPTERS:
            return {'status': 'policy_blocked', 'reason': 'adapter_not_allowed'}, 'adapter_not_allowed'

        model = str(runtime_config.get('model') or 'llama3.2').strip()
        if not cls.SAFE_MODEL_PATTERN.fullmatch(model):
            return {'status': 'policy_blocked', 'reason': 'model_invalid'}, 'model_invalid'

        allowed_models = runtime_config.get('allowed_models') or []
        if allowed_models:
            allowed_set = {str(value).strip() for value in allowed_models if str(value).strip()}
            if model not in allowed_set:
                return {
                    'status': 'policy_blocked',
                    'reason': 'model_not_allowlisted',
                    'model': model,
                }, 'model_not_allowlisted'

        response_max_chars = runtime_config.get('response_max_chars', 4000)
        try:
            response_max_chars = int(response_max_chars)
        except (TypeError, ValueError):
            response_max_chars = 4000
        response_max_chars = max(50, min(response_max_chars, 10000))

        timeout_seconds = runtime_config.get('timeout_seconds', 8)
        try:
            timeout_seconds = int(timeout_seconds)
        except (TypeError, ValueError):
            timeout_seconds = 8
        timeout_seconds = max(1, min(timeout_seconds, 30))

        if adapter == 'ollama_http':
            endpoint = str(runtime_config.get('endpoint') or 'http://localhost:11434/api/generate').strip()
            if not cls.SAFE_ENDPOINT_PATTERN.fullmatch(endpoint):
                return {'status': 'policy_blocked', 'reason': 'endpoint_invalid'}, 'endpoint_invalid'

            return cls._run_ollama_http_inference(
                prompt_text,
                model,
                endpoint,
                timeout_seconds,
                response_max_chars,
            )

        responses_map = runtime_config.get('linux_test_double_responses') or {}
        return cls._run_linux_test_double_inference(prompt_text, model, responses_map, response_max_chars)

    @staticmethod
    def _build_root_cause_prompt(symptom_summary: str, evidence_points: list[str]) -> str:
        """Build deterministic prompt for root cause analysis."""
        lines = [
            'You are a reliability root cause analyzer.',
            'Infer the most likely root cause from the provided symptoms and evidence.',
            'Return format:',
            'RootCause: <short probable cause>',
            'Confidence: <high|medium|low>',
            'Rationale: <one concise sentence>',
            '',
            f'Symptoms: {symptom_summary}',
            'Evidence:',
        ]
        for index, point in enumerate(evidence_points, start=1):
            lines.append(f'{index}. {point}')
        return '\n'.join(lines)

    @staticmethod
    def _parse_root_cause_response(response_text: str) -> dict[str, Any]:
        """Parse normalized root-cause response from Ollama output."""
        parsed_root_cause = ''
        parsed_confidence = 'low'
        parsed_rationale = ''

        for raw_line in str(response_text).splitlines():
            line = raw_line.strip()
            lower = line.lower()
            if lower.startswith('rootcause:') or lower.startswith('root_cause:'):
                parsed_root_cause = line.split(':', 1)[1].strip()
                continue
            if lower.startswith('confidence:'):
                parsed_confidence = line.split(':', 1)[1].strip().lower()
                continue
            if lower.startswith('rationale:'):
                parsed_rationale = line.split(':', 1)[1].strip()

        if parsed_confidence not in {'high', 'medium', 'low'}:
            parsed_confidence = 'low'

        if not parsed_root_cause:
            parsed_root_cause = str(response_text).strip().split('\n', 1)[0][:180] or 'unknown'

        if not parsed_rationale:
            parsed_rationale = str(response_text).strip()[:300]

        return {
            'probable_cause': parsed_root_cause,
            'confidence': parsed_confidence,
            'rationale': parsed_rationale,
            'analyzer_version': 'foundation-v1',
        }

    @staticmethod
    def _build_recommendation_prompt(
        symptom_summary: str,
        probable_cause: str,
        evidence_points: list[str],
        max_recommendations: int,
    ) -> str:
        """Build deterministic prompt for recommendation generation."""
        lines = [
            'You are an SRE recommendation engine.',
            'Given symptoms and probable cause, provide concise, prioritized remediation actions.',
            'Return format:',
            'Recommendation1: <action>',
            'Recommendation2: <action>',
            'Recommendation3: <action>',
            'Confidence: <high|medium|low>',
            '',
            f'Symptoms: {symptom_summary}',
            f'ProbableCause: {probable_cause}',
            f'MaxRecommendations: {max_recommendations}',
            'Evidence:',
        ]
        for index, point in enumerate(evidence_points, start=1):
            lines.append(f'{index}. {point}')
        return '\n'.join(lines)

    @staticmethod
    def _parse_recommendation_response(response_text: str, max_recommendations: int) -> dict[str, Any]:
        """Parse normalized recommendation response from Ollama output."""
        recommendations: list[str] = []
        confidence = 'low'

        for raw_line in str(response_text).splitlines():
            line = raw_line.strip()
            lower = line.lower()
            if lower.startswith('recommendation') and ':' in line:
                candidate = line.split(':', 1)[1].strip()
                if candidate:
                    recommendations.append(candidate)
                continue
            if lower.startswith('confidence:'):
                confidence = line.split(':', 1)[1].strip().lower()
                continue
            if line.startswith('- ') or line.startswith('* '):
                candidate = line[2:].strip()
                if candidate:
                    recommendations.append(candidate)

        if confidence not in {'high', 'medium', 'low'}:
            confidence = 'low'

        deduped: list[str] = []
        seen: set[str] = set()
        for item in recommendations:
            normalized = str(item).strip()
            if not normalized:
                continue
            key = normalized.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(normalized)

        if not deduped and str(response_text).strip():
            first_line = str(response_text).strip().split('\n', 1)[0]
            deduped = [first_line[:220]]

        deduped = deduped[:max_recommendations]
        return {
            'items': deduped,
            'count': len(deduped),
            'confidence': confidence,
            'engine_version': 'foundation-v1',
        }

    @staticmethod
    def _build_troubleshooting_prompt(question: str, context_items: list[str], max_steps: int) -> str:
        """Build deterministic prompt for troubleshooting assistant."""
        lines = [
            'You are a production troubleshooting assistant.',
            'Provide concise, operator-safe troubleshooting guidance.',
            'Return format:',
            'Step1: <first diagnostic step>',
            'Step2: <second diagnostic step>',
            'Step3: <third diagnostic step>',
            'EscalateIf: <when to escalate>',
            'Confidence: <high|medium|low>',
            '',
            f'Question: {question}',
            f'MaxSteps: {max_steps}',
            'Context:',
        ]
        for index, point in enumerate(context_items, start=1):
            lines.append(f'{index}. {point}')
        return '\n'.join(lines)

    @staticmethod
    def _parse_troubleshooting_response(response_text: str, max_steps: int) -> dict[str, Any]:
        """Parse normalized troubleshooting guidance output."""
        steps: list[str] = []
        escalate_if = ''
        confidence = 'low'

        for raw_line in str(response_text).splitlines():
            line = raw_line.strip()
            lower = line.lower()
            if lower.startswith('step') and ':' in line:
                candidate = line.split(':', 1)[1].strip()
                if candidate:
                    steps.append(candidate)
                continue
            if lower.startswith('escalateif:'):
                escalate_if = line.split(':', 1)[1].strip()
                continue
            if lower.startswith('confidence:'):
                confidence = line.split(':', 1)[1].strip().lower()

        deduped_steps: list[str] = []
        seen: set[str] = set()
        for item in steps:
            normalized = str(item).strip()
            if not normalized:
                continue
            key = normalized.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped_steps.append(normalized)

        if not deduped_steps and str(response_text).strip():
            first_line = str(response_text).strip().split('\n', 1)[0]
            deduped_steps = [first_line[:220]]

        if confidence not in {'high', 'medium', 'low'}:
            confidence = 'low'

        return {
            'steps': deduped_steps[:max_steps],
            'step_count': min(len(deduped_steps), max_steps),
            'escalate_if': escalate_if[:220],
            'confidence': confidence,
            'assistant_version': 'foundation-v1',
        }

    @staticmethod
    def _build_learning_prompt(
        issue_summary: str,
        resolution_summary: str,
        outcome: str,
        tags: list[str],
    ) -> str:
        """Build deterministic prompt for learning feedback extraction."""
        lines = [
            'You are a reliability learning-feedback handler.',
            'Extract reusable lessons from issue resolution feedback.',
            'Return format:',
            'Lesson: <key lesson learned>',
            'PreventiveAction: <future prevention action>',
            'PlaybookUpdate: <what to update in runbook>',
            'Confidence: <high|medium|low>',
            '',
            f'IssueSummary: {issue_summary}',
            f'ResolutionSummary: {resolution_summary}',
            f'Outcome: {outcome}',
            'Tags:',
        ]
        for index, tag in enumerate(tags, start=1):
            lines.append(f'{index}. {tag}')
        return '\n'.join(lines)

    @staticmethod
    def _parse_learning_response(response_text: str) -> dict[str, Any]:
        """Parse normalized learning feedback output."""
        lesson = ''
        preventive_action = ''
        playbook_update = ''
        confidence = 'low'

        for raw_line in str(response_text).splitlines():
            line = raw_line.strip()
            lower = line.lower()
            if lower.startswith('lesson:'):
                lesson = line.split(':', 1)[1].strip()
                continue
            if lower.startswith('preventiveaction:'):
                preventive_action = line.split(':', 1)[1].strip()
                continue
            if lower.startswith('playbookupdate:'):
                playbook_update = line.split(':', 1)[1].strip()
                continue
            if lower.startswith('confidence:'):
                confidence = line.split(':', 1)[1].strip().lower()

        if not lesson:
            lesson = str(response_text).strip().split('\n', 1)[0][:220] or 'No lesson extracted.'
        if not preventive_action:
            preventive_action = 'Review and refine operational safeguards.'
        if not playbook_update:
            playbook_update = 'Add validated resolution sequence to runbook.'
        if confidence not in {'high', 'medium', 'low'}:
            confidence = 'low'

        return {
            'lesson': lesson,
            'preventive_action': preventive_action,
            'playbook_update': playbook_update,
            'confidence': confidence,
            'handler_version': 'foundation-v1',
        }

    @classmethod
    def _run_ollama_http_inference(
        cls,
        prompt_text: str,
        model: str,
        endpoint: str,
        timeout_seconds: int,
        response_max_chars: int,
    ) -> tuple[dict[str, Any], str | None]:
        """Call Ollama HTTP endpoint with bounded and safe request semantics."""
        request_payload = {
            'model': model,
            'prompt': prompt_text,
            'stream': False,
        }

        try:
            response = cls._run_ollama_http_request(endpoint, request_payload, timeout_seconds)
        except requests.RequestException as exc:
            return {
                'status': 'command_failed',
                'adapter': 'ollama_http',
                'model': model,
                'reason': 'http_request_failed',
                'details': str(exc)[:500],
            }, 'command_failed'

        status_code = int(getattr(response, 'status_code', 0) or 0)
        if status_code < 200 or status_code >= 300:
            return {
                'status': 'command_failed',
                'adapter': 'ollama_http',
                'model': model,
                'http_status': status_code,
                'reason': 'http_status_not_success',
                'body_preview': str(getattr(response, 'text', '') or '')[:500],
            }, 'command_failed'

        try:
            payload = response.json()
        except ValueError:
            return {
                'status': 'command_failed',
                'adapter': 'ollama_http',
                'model': model,
                'reason': 'invalid_json',
                'body_preview': str(getattr(response, 'text', '') or '')[:500],
            }, 'command_failed'

        response_text = str((payload or {}).get('response') or '').strip()
        truncated = len(response_text) > response_max_chars
        if truncated:
            response_text = response_text[:response_max_chars]

        return {
            'status': 'success',
            'adapter': 'ollama_http',
            'model': model,
            'prompt_chars': len(prompt_text),
            'inference': {
                'response_text': response_text,
                'response_chars': len(response_text),
                'response_truncated': truncated,
                'engine': 'ollama',
                'inference_version': 'foundation-v1',
            },
        }, None

    @staticmethod
    def _run_ollama_http_request(endpoint: str, payload: dict[str, Any], timeout_seconds: int):
        """Execute Ollama HTTP request through a single patchable boundary."""
        return requests.post(endpoint, json=payload, timeout=timeout_seconds)

    @classmethod
    def _run_linux_test_double_inference(
        cls,
        prompt_text: str,
        model: str,
        responses_map: dict[str, str],
        response_max_chars: int,
    ) -> tuple[dict[str, Any], str | None]:
        """Resolve deterministic Ollama response for tests/dev on Linux."""
        by_model_key = f'{model}|{prompt_text}'
        response_text = str(
            responses_map.get(by_model_key)
            or responses_map.get(prompt_text)
            or f'[{model}] Deterministic response: {prompt_text[:120]}'
        ).strip()

        truncated = len(response_text) > response_max_chars
        if truncated:
            response_text = response_text[:response_max_chars]

        return {
            'status': 'success',
            'adapter': 'linux_test_double',
            'model': model,
            'prompt_chars': len(prompt_text),
            'inference': {
                'response_text': response_text,
                'response_chars': len(response_text),
                'response_truncated': truncated,
                'engine': 'ollama_test_double',
                'inference_version': 'foundation-v1',
            },
        }, None

    @staticmethod
    def _contains_unsafe_control_characters(value: str) -> bool:
        """Reject control characters except newline/tab/carriage-return."""
        for char in str(value):
            if char in ('\n', '\r', '\t'):
                continue
            if ord(char) < 32:
                return True
        return False