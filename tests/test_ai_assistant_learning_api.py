"""Tests for Phase 2 Week 16 troubleshooting assistant and learning feedback foundations."""

from unittest.mock import patch

from server.auth import get_api_key
from server.services.ai_service import AIService


def _headers(tenant_slug=None):
    headers = {'X-API-Key': get_api_key()}
    if tenant_slug:
        headers['X-Tenant-Slug'] = tenant_slug
    return headers


def test_troubleshooting_assistant_uses_linux_test_double_path(client, app_fixture):
    question = 'How do I triage repeated service restarts on host-a?'
    context_items = [
        'System event log has Event ID 7031 entries.',
        'Restart count exceeded threshold in last 10 minutes.',
    ]
    prompt_text = AIService._build_troubleshooting_prompt(question, context_items, 4)

    app_fixture.config['OLLAMA_ADAPTER'] = 'linux_test_double'
    app_fixture.config['OLLAMA_ALLOWED_MODELS'] = 'llama3.2,phi3'
    app_fixture.config['OLLAMA_DEFAULT_MODEL'] = 'llama3.2'
    app_fixture.config['AI_TROUBLESHOOT_MAX_STEPS'] = 4
    app_fixture.config['AI_TROUBLESHOOT_MAX_CONTEXT_ITEMS'] = 6
    app_fixture.config['OLLAMA_LINUX_TEST_DOUBLE_RESPONSES'] = (
        f'{prompt_text}=Step1: Check service logs for fatal errors.\n'
        'Step2: Validate dependency health and startup order.\n'
        'Step3: Inspect recent configuration changes.\n'
        'EscalateIf: Service still crashes after rollback.\n'
        'Confidence: high'
    )

    response = client.post(
        '/api/ai/troubleshooting/assist',
        headers=_headers(),
        json={
            'question': question,
            'context_items': context_items,
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['status'] == 'success'
    assert payload['assistant']['adapter'] == 'linux_test_double'
    assert payload['assistant']['guidance']['step_count'] == 3
    assert payload['assistant']['guidance']['confidence'] == 'high'


def test_troubleshooting_assistant_requires_question(client):
    response = client.post(
        '/api/ai/troubleshooting/assist',
        headers=_headers(),
        json={'context_items': ['some context']},
    )

    assert response.status_code == 400
    payload = response.get_json()
    assert payload['error'] == 'Validation failed'


def test_troubleshooting_assistant_maps_non_2xx_http_response_to_503(client, app_fixture):
    app_fixture.config['OLLAMA_ADAPTER'] = 'ollama_http'
    app_fixture.config['OLLAMA_ENDPOINT'] = 'http://ollama:11434/api/generate'
    app_fixture.config['OLLAMA_ALLOWED_MODELS'] = 'llama3.2'
    app_fixture.config['OLLAMA_DEFAULT_MODEL'] = 'llama3.2'

    class _OllamaHttpErrorResponseDouble:
        status_code = 502
        text = 'bad gateway'

        @staticmethod
        def json():
            return {'error': 'bad gateway'}

    with patch(
        'server.services.ai_service.AIService._run_ollama_http_request',
        return_value=_OllamaHttpErrorResponseDouble(),
    ) as runner_double:
        response = client.post(
            '/api/ai/troubleshooting/assist',
            headers=_headers(),
            json={
                'question': 'Why is disk latency high?',
                'context_items': ['Disk queue depth above baseline.'],
            },
        )

    assert runner_double.call_count == 1
    assert response.status_code == 503
    payload = response.get_json()
    assert payload['error'] == 'Troubleshooting assistant request failed'


def test_learning_feedback_handler_uses_linux_test_double_path(client, app_fixture):
    issue_summary = 'Database primary failed over during maintenance window.'
    resolution_summary = 'Adjusted failover timeout and validated replication health checks.'
    tags = ['database', 'failover', 'maintenance']
    prompt_text = AIService._build_learning_prompt(
        issue_summary,
        resolution_summary,
        'resolved',
        tags,
    )

    app_fixture.config['OLLAMA_ADAPTER'] = 'linux_test_double'
    app_fixture.config['OLLAMA_ALLOWED_MODELS'] = 'llama3.2,phi3'
    app_fixture.config['OLLAMA_DEFAULT_MODEL'] = 'llama3.2'
    app_fixture.config['AI_LEARNING_MAX_TAGS'] = 8
    app_fixture.config['OLLAMA_LINUX_TEST_DOUBLE_RESPONSES'] = (
        f'{prompt_text}=Lesson: Validate replication lag before controlled failover.\n'
        'PreventiveAction: Add pre-check gate in maintenance runbook.\n'
        'PlaybookUpdate: Include timeout tuning checklist and validation SQL.\n'
        'Confidence: high'
    )

    response = client.post(
        '/api/ai/learning/feedback',
        headers=_headers(),
        json={
            'issue_summary': issue_summary,
            'resolution_summary': resolution_summary,
            'outcome': 'resolved',
            'tags': tags,
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['status'] == 'success'
    assert payload['learning_feedback']['adapter'] == 'linux_test_double'
    assert payload['learning_feedback']['learning']['confidence'] == 'high'
    assert payload['learning_feedback']['learning']['lesson'].startswith('Validate replication lag')


def test_learning_feedback_handler_requires_resolution_summary(client):
    response = client.post(
        '/api/ai/learning/feedback',
        headers=_headers(),
        json={
            'issue_summary': 'Intermittent 5xx spikes.',
            'outcome': 'resolved',
            'tags': ['api'],
        },
    )

    assert response.status_code == 400
    payload = response.get_json()
    assert payload['error'] == 'Validation failed'


def test_learning_feedback_handler_maps_non_2xx_http_response_to_503(client, app_fixture):
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
            '/api/ai/learning/feedback',
            headers=_headers(),
            json={
                'issue_summary': 'Queue backlog growth under load.',
                'resolution_summary': 'Increased worker pool and tuned prefetch settings.',
                'outcome': 'mitigated',
                'tags': ['queue'],
            },
        )

    assert runner_double.call_count == 1
    assert response.status_code == 503
    payload = response.get_json()
    assert payload['error'] == 'Learning feedback request failed'
