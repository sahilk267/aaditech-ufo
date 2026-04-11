from __future__ import annotations

from datetime import UTC, datetime, timedelta

from server.auth import get_api_key
from server.extensions import db
from server.models import AuditEvent, Organization


def _headers(tenant_slug: str = "default") -> dict[str, str]:
    return {
        "X-API-Key": get_api_key(),
        "X-Tenant-Slug": tenant_slug,
    }


def _ensure_tenant(app_fixture, slug: str = "default") -> int:
    with app_fixture.app_context():
        tenant = Organization.query.filter_by(slug=slug).first()
        if tenant is None:
            tenant = Organization(name="Default Organization", slug=slug, is_active=True)
            db.session.add(tenant)
            db.session.commit()
        return tenant.id


def test_ai_operations_report_aggregates_runtime_visibility(client, app_fixture):
    with app_fixture.app_context():
        tenant_id = _ensure_tenant(app_fixture)
        now = datetime.now(UTC).replace(tzinfo=None)
        db.session.add_all([
            AuditEvent(
                tenant_id=tenant_id,
                action="ai.ollama.inference",
                outcome="success",
                created_at=now,
                event_metadata={
                    "adapter": "ollama_http",
                    "model": "llama3.2",
                    "duration_ms": "123",
                    "fallback_used": "false",
                },
            ),
            AuditEvent(
                tenant_id=tenant_id,
                action="ai.root_cause.analyze",
                outcome="failure",
                created_at=now - timedelta(minutes=1),
                event_metadata={
                    "requested_adapter": "ollama_http",
                    "duration_ms": "245",
                    "fallback_used": "true",
                    "primary_error_reason": "http_status_not_success",
                    "reason": "command_failed",
                },
            ),
            AuditEvent(
                tenant_id=tenant_id,
                action="ai.recommendations.generate",
                outcome="success",
                created_at=now - timedelta(minutes=2),
                event_metadata={
                    "adapter": "linux_test_double",
                    "duration_ms": "80",
                    "fallback_used": "true",
                },
            ),
        ])
        db.session.commit()

    response = client.get("/api/ai/operations/report", headers=_headers(), query_string={"limit": 5})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "success"

    report = payload["report"]
    assert report["summary"]["total_events"] == 3
    assert report["summary"]["success_count"] == 2
    assert report["summary"]["failure_count"] == 1
    assert report["summary"]["fallback_count"] == 2
    assert report["summary"]["avg_duration_ms"] == 149

    assert report["counts"]["by_action"]["ai.ollama.inference"] == 1
    assert report["counts"]["by_adapter"]["ollama_http"] == 2
    assert report["counts"]["by_adapter"]["linux_test_double"] == 1
    assert report["counts"]["by_primary_error_reason"]["http_status_not_success"] == 1

    assert len(report["recent_operations"]) == 3
    assert report["recent_operations"][0]["action"] == "ai.ollama.inference"
    assert len(report["recent_failures"]) == 1
    assert report["recent_failures"][0]["primary_error_reason"] == "http_status_not_success"


def test_ai_operations_report_is_tenant_scoped(client, app_fixture):
    with app_fixture.app_context():
        default_tenant_id = _ensure_tenant(app_fixture, slug="default")
        other_tenant_id = _ensure_tenant(app_fixture, slug="other")
        now = datetime.now(UTC).replace(tzinfo=None)
        db.session.add_all([
            AuditEvent(
                tenant_id=default_tenant_id,
                action="ai.ollama.inference",
                outcome="success",
                created_at=now,
                event_metadata={"adapter": "linux_test_double", "duration_ms": "55"},
            ),
            AuditEvent(
                tenant_id=other_tenant_id,
                action="ai.ollama.inference",
                outcome="failure",
                created_at=now,
                event_metadata={"adapter": "ollama_http", "reason": "blocked"},
            ),
        ])
        db.session.commit()

    response = client.get("/api/ai/operations/report", headers=_headers("default"))

    assert response.status_code == 200
    report = response.get_json()["report"]
    assert report["summary"]["total_events"] == 1
    assert report["summary"]["failure_count"] == 0
    assert report["counts"]["by_adapter"]["linux_test_double"] == 1
    assert "ollama_http" not in report["counts"]["by_adapter"]
