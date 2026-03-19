"""Tests for Phase 2 Week 16 item 1 Ollama wrapper foundation."""

from unittest.mock import patch

from server.auth import get_api_key
from server.services.ai_service import AIService


def _headers(tenant_slug=None):
    headers = {'X-API-Key': get_api_key()}
    if tenant_slug:
        headers['X-Tenant-Slug'] = tenant_slug
    return headers


def test_ollama_inference_uses_linux_test_double_path(client, app_fixture):
    app_fixture.config['OLLAMA_ADAPTER'] = 'linux_test_double'
    app_fixture.config['OLLAMA_ALLOWED_MODELS'] = 'llama3.2,phi3'
    app_fixture.config['OLLAMA_DEFAULT_MODEL'] = 'llama3.2'
    app_fixture.config['OLLAMA_LINUX_TEST_DOUBLE_RESPONSES'] = (
        'llama3.2|Summarize boot failures.=Boot failures correlate with recent driver updates.'
    )

    response = client.post(
        '/api/ai/ollama/infer',
        headers=_headers(),
        json={'prompt': 'Summarize boot failures.'},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['status'] == 'success'
    assert payload['ollama']['adapter'] == 'linux_test_double'
    assert payload['ollama']['model'] == 'llama3.2'
    assert payload['ollama']['inference']['response_text'] == (
        'Boot failures correlate with recent driver updates.'
    )


def test_ollama_inference_uses_http_boundary(client, app_fixture):
    app_fixture.config['OLLAMA_ADAPTER'] = 'ollama_http'
    app_fixture.config['OLLAMA_ENDPOINT'] = 'http://ollama:11434/api/generate'
    app_fixture.config['OLLAMA_ALLOWED_MODELS'] = 'llama3.2'
    app_fixture.config['OLLAMA_DEFAULT_MODEL'] = 'llama3.2'
    app_fixture.config['OLLAMA_TIMEOUT_SECONDS'] = 9

    class _OllamaHttpResponseDouble:
        status_code = 200
        text = '{"response":"Likely root cause is a failing dependency."}'

        @staticmethod
        def json():
            return {'response': 'Likely root cause is a failing dependency.'}

    with patch(
        'server.services.ai_service.AIService._run_ollama_http_request',
        return_value=_OllamaHttpResponseDouble(),
    ) as runner_double:
        response = client.post(
            '/api/ai/ollama/infer',
            headers=_headers(),
            json={'prompt': 'Find the likely root cause.'},
        )

    assert runner_double.call_count == 1
    call_args, call_kwargs = runner_double.call_args
    assert call_args[0] == 'http://ollama:11434/api/generate'
    assert call_args[1]['model'] == 'llama3.2'
    assert call_args[1]['prompt'] == 'Find the likely root cause.'
    assert call_args[1]['stream'] is False
    assert call_args[2] == 9
    assert call_kwargs == {}

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['status'] == 'success'
    assert payload['ollama']['adapter'] == 'ollama_http'
    assert payload['ollama']['inference']['response_text'] == 'Likely root cause is a failing dependency.'


def test_ollama_inference_blocks_model_outside_allowlist(client, app_fixture):
    app_fixture.config['OLLAMA_ADAPTER'] = 'linux_test_double'
    app_fixture.config['OLLAMA_ALLOWED_MODELS'] = 'llama3.2'

    response = client.post(
        '/api/ai/ollama/infer',
        headers=_headers(),
        json={'prompt': 'Check recurring failures.', 'model': 'mistral'},
    )

    assert response.status_code == 400
    payload = response.get_json()
    assert payload['error'] == 'Validation failed'
    assert payload['details']['reason'] == 'model_not_allowlisted'


def test_ollama_inference_maps_non_2xx_http_response_to_503(client, app_fixture):
    app_fixture.config['OLLAMA_ADAPTER'] = 'ollama_http'
    app_fixture.config['OLLAMA_ENDPOINT'] = 'http://ollama:11434/api/generate'
    app_fixture.config['OLLAMA_ALLOWED_MODELS'] = 'llama3.2'
    app_fixture.config['OLLAMA_DEFAULT_MODEL'] = 'llama3.2'

    class _OllamaHttpErrorResponseDouble:
        status_code = 502
        text = 'upstream unavailable'

        @staticmethod
        def json():
            return {'error': 'upstream unavailable'}

    with patch(
        'server.services.ai_service.AIService._run_ollama_http_request',
        return_value=_OllamaHttpErrorResponseDouble(),
    ) as runner_double:
        response = client.post(
            '/api/ai/ollama/infer',
            headers=_headers(),
            json={'prompt': 'Analyze service outage symptoms.'},
        )

    assert runner_double.call_count == 1
    assert response.status_code == 503

    payload = response.get_json()
    assert payload['error'] == 'Ollama inference request failed'
    assert payload['details']['status'] == 'command_failed'
    assert payload['details']['reason'] == 'http_status_not_success'
    assert payload['details']['http_status'] == 502


def test_root_cause_analyzer_uses_linux_test_double_path(client, app_fixture):
    symptom_summary = 'Host reboots unexpectedly after recent patching.'
    evidence_points = [
        'Kernel-Power Event ID 41 logged three times in one hour.',
        'Graphics driver was updated one day before the first reboot.',
    ]
    prompt_text = AIService._build_root_cause_prompt(symptom_summary, evidence_points)

    app_fixture.config['OLLAMA_ADAPTER'] = 'linux_test_double'
    app_fixture.config['OLLAMA_ALLOWED_MODELS'] = 'llama3.2,phi3'
    app_fixture.config['OLLAMA_DEFAULT_MODEL'] = 'llama3.2'
    app_fixture.config['OLLAMA_LINUX_TEST_DOUBLE_RESPONSES'] = (
        f'{prompt_text}=RootCause: Faulty graphics driver update\n'
        'Confidence: high\n'
        'Rationale: Reboots started immediately after the driver change and match kernel-power failures.'
    )

    response = client.post(
        '/api/ai/root-cause/analyze',
        headers=_headers(),
        json={
            'symptom_summary': symptom_summary,
            'evidence_points': evidence_points,
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['status'] == 'success'
    assert payload['analysis']['adapter'] == 'linux_test_double'
    assert payload['analysis']['root_cause']['probable_cause'] == 'Faulty graphics driver update'
    assert payload['analysis']['root_cause']['confidence'] == 'high'


def test_root_cause_analyzer_uses_http_boundary(client, app_fixture):
    app_fixture.config['OLLAMA_ADAPTER'] = 'ollama_http'
    app_fixture.config['OLLAMA_ENDPOINT'] = 'http://ollama:11434/api/generate'
    app_fixture.config['OLLAMA_ALLOWED_MODELS'] = 'llama3.2'
    app_fixture.config['OLLAMA_DEFAULT_MODEL'] = 'llama3.2'
    app_fixture.config['OLLAMA_TIMEOUT_SECONDS'] = 9

    class _OllamaHttpResponseDouble:
        status_code = 200
        text = '{"response":"RootCause: Memory leak in telemetry agent\\nConfidence: medium\\nRationale: RSS growth and OOM events match leak behavior."}'

        @staticmethod
        def json():
            return {
                'response': (
                    'RootCause: Memory leak in telemetry agent\n'
                    'Confidence: medium\n'
                    'Rationale: RSS growth and OOM events match leak behavior.'
                )
            }

    with patch(
        'server.services.ai_service.AIService._run_ollama_http_request',
        return_value=_OllamaHttpResponseDouble(),
    ) as runner_double:
        response = client.post(
            '/api/ai/root-cause/analyze',
            headers=_headers(),
            json={
                'symptom_summary': 'Service exits with OOM kill alerts.',
                'evidence_points': [
                    'Container memory usage climbs steadily for two hours.',
                    'OOMKill reason reported by orchestrator.',
                ],
            },
        )

    assert runner_double.call_count == 1
    call_args, call_kwargs = runner_double.call_args
    assert call_args[0] == 'http://ollama:11434/api/generate'
    assert call_args[1]['model'] == 'llama3.2'
    assert 'Service exits with OOM kill alerts.' in call_args[1]['prompt']
    assert call_args[1]['stream'] is False
    assert call_args[2] == 9
    assert call_kwargs == {}

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['status'] == 'success'
    assert payload['analysis']['adapter'] == 'ollama_http'
    assert payload['analysis']['root_cause']['probable_cause'] == 'Memory leak in telemetry agent'
    assert payload['analysis']['root_cause']['confidence'] == 'medium'


def test_root_cause_analyzer_maps_non_2xx_http_response_to_503(client, app_fixture):
    app_fixture.config['OLLAMA_ADAPTER'] = 'ollama_http'
    app_fixture.config['OLLAMA_ENDPOINT'] = 'http://ollama:11434/api/generate'
    app_fixture.config['OLLAMA_ALLOWED_MODELS'] = 'llama3.2'
    app_fixture.config['OLLAMA_DEFAULT_MODEL'] = 'llama3.2'

    class _OllamaHttpErrorResponseDouble:
        status_code = 504
        text = 'gateway timeout'

        @staticmethod
        def json():
            return {'error': 'gateway timeout'}

    with patch(
        'server.services.ai_service.AIService._run_ollama_http_request',
        return_value=_OllamaHttpErrorResponseDouble(),
    ) as runner_double:
        response = client.post(
            '/api/ai/root-cause/analyze',
            headers=_headers(),
            json={
                'symptom_summary': 'Periodic downtime during traffic spikes.',
                'evidence_points': ['API gateway reports repeated upstream timeouts.'],
            },
        )

    assert runner_double.call_count == 1
    assert response.status_code == 503

    payload = response.get_json()
    assert payload['error'] == 'Root cause analysis request failed'
    assert payload['details']['status'] == 'command_failed'
    assert payload['details']['reason'] == 'http_status_not_success'
    assert payload['details']['http_status'] == 504


def test_recommendation_engine_uses_linux_test_double_path(client, app_fixture):
    symptom_summary = 'Database response times spike every hour.'
    probable_cause = 'Connection pool exhaustion during scheduled batch jobs.'
    evidence_points = [
        'Pool utilization reaches 100% near :00 each hour.',
        'Batch import cron starts at the same time.',
    ]
    prompt_text = AIService._build_recommendation_prompt(
        symptom_summary,
        probable_cause,
        evidence_points,
        3,
    )

    app_fixture.config['OLLAMA_ADAPTER'] = 'linux_test_double'
    app_fixture.config['OLLAMA_ALLOWED_MODELS'] = 'llama3.2,phi3'
    app_fixture.config['OLLAMA_DEFAULT_MODEL'] = 'llama3.2'
    app_fixture.config['AI_RECOMMENDATION_MAX_ITEMS'] = 3
    app_fixture.config['OLLAMA_LINUX_TEST_DOUBLE_RESPONSES'] = (
        f'{prompt_text}=Recommendation1: Increase pool size by 25%.\n'
        'Recommendation2: Stagger batch start time by 10 minutes.\n'
        'Recommendation3: Add queue backpressure at import ingress.\n'
        'Confidence: high'
    )

    response = client.post(
        '/api/ai/recommendations/generate',
        headers=_headers(),
        json={
            'symptom_summary': symptom_summary,
            'probable_cause': probable_cause,
            'evidence_points': evidence_points,
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['status'] == 'success'
    assert payload['recommendations']['adapter'] == 'linux_test_double'
    assert payload['recommendations']['recommendations']['count'] == 3
    assert payload['recommendations']['recommendations']['confidence'] == 'high'


def test_recommendation_engine_uses_http_boundary(client, app_fixture):
    app_fixture.config['OLLAMA_ADAPTER'] = 'ollama_http'
    app_fixture.config['OLLAMA_ENDPOINT'] = 'http://ollama:11434/api/generate'
    app_fixture.config['OLLAMA_ALLOWED_MODELS'] = 'llama3.2'
    app_fixture.config['OLLAMA_DEFAULT_MODEL'] = 'llama3.2'
    app_fixture.config['OLLAMA_TIMEOUT_SECONDS'] = 9
    app_fixture.config['AI_RECOMMENDATION_MAX_ITEMS'] = 2

    class _OllamaHttpResponseDouble:
        status_code = 200
        text = '{"response":"Recommendation1: Restart the service during low traffic.\\nRecommendation2: Enable adaptive autoscaling.\\nConfidence: medium"}'

        @staticmethod
        def json():
            return {
                'response': (
                    'Recommendation1: Restart the service during low traffic.\n'
                    'Recommendation2: Enable adaptive autoscaling.\n'
                    'Confidence: medium'
                )
            }

    with patch(
        'server.services.ai_service.AIService._run_ollama_http_request',
        return_value=_OllamaHttpResponseDouble(),
    ) as runner_double:
        response = client.post(
            '/api/ai/recommendations/generate',
            headers=_headers(),
            json={
                'symptom_summary': 'Web nodes show sustained CPU pressure.',
                'probable_cause': 'Traffic surge exceeds current scale settings.',
                'evidence_points': ['CPU remains above 90% for 15 minutes.'],
            },
        )

    assert runner_double.call_count == 1
    call_args, call_kwargs = runner_double.call_args
    assert call_args[0] == 'http://ollama:11434/api/generate'
    assert call_args[1]['model'] == 'llama3.2'
    assert 'Web nodes show sustained CPU pressure.' in call_args[1]['prompt']
    assert call_args[1]['stream'] is False
    assert call_args[2] == 9
    assert call_kwargs == {}

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['status'] == 'success'
    assert payload['recommendations']['adapter'] == 'ollama_http'
    assert payload['recommendations']['recommendations']['count'] == 2
    assert payload['recommendations']['recommendations']['confidence'] == 'medium'


def test_recommendation_engine_maps_non_2xx_http_response_to_503(client, app_fixture):
    app_fixture.config['OLLAMA_ADAPTER'] = 'ollama_http'
    app_fixture.config['OLLAMA_ENDPOINT'] = 'http://ollama:11434/api/generate'
    app_fixture.config['OLLAMA_ALLOWED_MODELS'] = 'llama3.2'
    app_fixture.config['OLLAMA_DEFAULT_MODEL'] = 'llama3.2'

    class _OllamaHttpErrorResponseDouble:
        status_code = 503
        text = 'service unavailable'

        @staticmethod
        def json():
            return {'error': 'service unavailable'}

    with patch(
        'server.services.ai_service.AIService._run_ollama_http_request',
        return_value=_OllamaHttpErrorResponseDouble(),
    ) as runner_double:
        response = client.post(
            '/api/ai/recommendations/generate',
            headers=_headers(),
            json={
                'symptom_summary': 'Fleet-wide latency alerts are firing.',
                'probable_cause': 'Upstream dependency instability.',
                'evidence_points': ['Multiple gateway 5xx events in 3 minutes.'],
            },
        )

    assert runner_double.call_count == 1
    assert response.status_code == 503

    payload = response.get_json()
    assert payload['error'] == 'Recommendation engine request failed'
    assert payload['details']['status'] == 'command_failed'
    assert payload['details']['reason'] == 'http_status_not_success'
    assert payload['details']['http_status'] == 503