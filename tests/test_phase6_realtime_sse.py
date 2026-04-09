"""Tests for Phase 6 realtime SSE feeds."""

from __future__ import annotations

import json

from server.auth import get_api_key
from server.extensions import db
from server.models import AuditEvent, IncidentRecord, NotificationDelivery, Organization
from server.tenant_context import get_or_create_default_tenant


def _headers(tenant_slug: str = "default") -> dict[str, str]:
    return {"X-API-Key": get_api_key(), "X-Tenant-Slug": tenant_slug}


def _default_tenant() -> Organization:
    return Organization.query.filter_by(slug="default").first() or get_or_create_default_tenant()


def _consume_stream_text(response) -> str:
    return b"".join(response.response).decode("utf-8")


def test_alerts_stream_returns_sse_snapshot_for_current_tenant(client, db_session, app_fixture):
    with app_fixture.app_context():
        tenant = _default_tenant()
        other = Organization.query.filter_by(slug="beta-tenant").first()
        if other is None:
            other = Organization(name="Beta Tenant", slug="beta-tenant", is_active=True)
            db.session.add(other)
            db.session.flush()

        db_session.add(
            NotificationDelivery(
                organization_id=tenant.id,
                status="success",
                channels_requested=["email"],
                delivered_channels=["email"],
                alerts_count=1,
                raw_alerts_count=1,
            )
        )
        db_session.add(
            IncidentRecord(
                organization_id=tenant.id,
                fingerprint="default-stream-incident",
                title="Default stream incident",
                severity="critical",
                status="open",
            )
        )
        db_session.add(
            NotificationDelivery(
                organization_id=other.id,
                status="failed",
                channels_requested=["webhook"],
                delivered_channels=[],
                alerts_count=1,
                raw_alerts_count=1,
            )
        )
        db_session.commit()

    response = client.get("/api/alerts/stream?limit=10", headers=_headers(), buffered=False)
    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("text/event-stream")
    assert response.headers["X-Accel-Buffering"] == "no"

    text = _consume_stream_text(response)
    assert "event: alerts.snapshot" in text
    assert "retry: 10000" in text

    data_line = next(line for line in text.splitlines() if line.startswith("data: "))
    payload = json.loads(data_line.removeprefix("data: "))
    assert payload["counts"]["deliveries"] == 1
    assert payload["counts"]["incidents_total"] == 1
    assert payload["deliveries"][0]["organization_id"] == payload["incidents"][0]["organization_id"]
    assert payload["incidents"][0]["title"] == "Default stream incident"
    assert all(item["status"] != "failed" for item in payload["deliveries"])


def test_operations_timeline_stream_returns_sse_snapshot(client, db_session, app_fixture):
    with app_fixture.app_context():
        tenant = _default_tenant()
        db_session.add(
            AuditEvent(
                action="operations.timeline.test",
                outcome="success",
                tenant_id=tenant.id,
                event_metadata={"source": "sse-test"},
            )
        )
        db_session.add(
            IncidentRecord(
                organization_id=tenant.id,
                fingerprint="timeline-stream-incident",
                title="Timeline stream incident",
                severity="warning",
                status="open",
            )
        )
        db_session.commit()

    response = client.get("/api/operations/timeline/stream?limit=10", headers=_headers(), buffered=False)
    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("text/event-stream")

    text = _consume_stream_text(response)
    assert "event: operations.timeline.snapshot" in text

    data_line = next(line for line in text.splitlines() if line.startswith("data: "))
    payload = json.loads(data_line.removeprefix("data: "))
    assert payload["count"] >= 1
    kinds = {item["kind"] for item in payload["timeline"]}
    assert "audit_event" in kinds or "incident" in kinds
