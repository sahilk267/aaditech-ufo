"""Phase 6 P1-A logs investigation productization coverage."""

from server.auth import get_api_key
from server.extensions import db
from server.models import LogEntry, LogSource, Organization


def _headers(tenant_slug: str = "default") -> dict[str, str]:
    return {
        "X-API-Key": get_api_key(),
        "X-Tenant-Slug": tenant_slug,
    }


def _ensure_tenant(app_fixture, slug: str = "default", name: str = "Default Organization") -> Organization:
    with app_fixture.app_context():
        tenant = Organization.query.filter_by(slug=slug).first()
        if tenant is None:
            tenant = Organization(name=name, slug=slug, is_active=True)
            db.session.add(tenant)
            db.session.commit()
        return tenant


def test_log_sources_detail_and_metadata_update(client, app_fixture):
    _ensure_tenant(app_fixture)
    app_fixture.config["LOG_PERSISTENT_STORE_ENABLED"] = True
    app_fixture.config["LOG_INGESTION_ADAPTER"] = "linux_test_double"
    app_fixture.config["LOG_EVENT_QUERY_ADAPTER"] = "linux_test_double"
    app_fixture.config["LOG_INGESTION_ALLOWED_SOURCES"] = "system,application"
    app_fixture.config["LOG_LINUX_INGESTION_TEST_DOUBLE"] = "system=kernel panic|retry started"
    app_fixture.config["LOG_LINUX_EVENT_QUERY_TEST_DOUBLE"] = (
        "system=2026-04-07T12:00:00Z|Error|1001|system|Disk failure"
        "||2026-04-07T12:01:00Z|Warning|1002|system|Retry started"
    )

    ingest_response = client.post("/api/logs/ingest", headers=_headers(), json={"source_name": "system"})
    assert ingest_response.status_code == 200

    query_response = client.post("/api/logs/events/query", headers=_headers(), json={"source_name": "system"})
    assert query_response.status_code == 200

    parse_response = client.post(
        "/api/logs/parse",
        headers=_headers(),
        json={"entries": [{"source": "application", "severity": "error", "message": "Worker crashed"}]},
    )
    assert parse_response.status_code == 200

    list_response = client.get("/api/logs/sources", headers=_headers())
    assert list_response.status_code == 200
    payload = list_response.get_json()
    assert payload["count"] == 2

    system_source = next(source for source in payload["sources"] if source["name"] == "system")
    assert system_source["entry_count"] == 4
    assert system_source["severity_breakdown"]["error"] == 1
    assert system_source["capture_kinds"]["ingest"] == 2
    assert system_source["capture_kinds"]["event_query"] == 2

    detail_response = client.get(f"/api/logs/sources/{system_source['id']}?recent_limit=2", headers=_headers())
    assert detail_response.status_code == 200
    detail_payload = detail_response.get_json()
    assert detail_payload["log_source"]["id"] == system_source["id"]
    assert len(detail_payload["recent_entries"]) == 2

    update_response = client.patch(
        f"/api/logs/sources/{system_source['id']}",
        headers=_headers(),
        json={
            "description": "Primary operating-system stream",
            "host_name": "prod-host-01",
            "is_active": False,
            "source_metadata": {"environment": "prod", "team": "ops"},
        },
    )
    assert update_response.status_code == 200
    updated = update_response.get_json()["log_source"]
    assert updated["description"] == "Primary operating-system stream"
    assert updated["host_name"] == "prod-host-01"
    assert updated["is_active"] is False
    assert updated["source_metadata"]["environment"] == "prod"

    with app_fixture.app_context():
        stored = db.session.get(LogSource, system_source["id"])
        assert stored is not None
        assert stored.host_name == "prod-host-01"
        assert stored.is_active is False


def test_log_entries_filters_detail_and_tenant_isolation(client, app_fixture):
    _ensure_tenant(app_fixture, slug="default", name="Default Organization")
    _ensure_tenant(app_fixture, slug="beta", name="Beta Organization")
    app_fixture.config["LOG_PERSISTENT_STORE_ENABLED"] = True
    app_fixture.config["LOG_EVENT_QUERY_ADAPTER"] = "linux_test_double"
    app_fixture.config["LOG_INGESTION_ALLOWED_SOURCES"] = "system"
    app_fixture.config["LOG_LINUX_EVENT_QUERY_TEST_DOUBLE"] = (
        "system=2026-04-07T12:00:00Z|Error|1001|system|Disk failure"
        "||2026-04-07T12:01:00Z|Warning|1002|system|Retry started"
    )

    default_query = client.post("/api/logs/events/query", headers=_headers("default"), json={"source_name": "system"})
    beta_query = client.post("/api/logs/events/query", headers=_headers("beta"), json={"source_name": "system"})
    assert default_query.status_code == 200
    assert beta_query.status_code == 200

    entries_response = client.get(
        "/api/logs/entries?source_name=system&severity=error&capture_kind=event_query&query_text=Disk",
        headers=_headers("default"),
    )
    assert entries_response.status_code == 200
    entries_payload = entries_response.get_json()
    assert entries_payload["total"] == 1
    entry = entries_payload["entries"][0]
    assert entry["message"] == "Disk failure"
    assert entry["severity"] == "error"

    detail_response = client.get(f"/api/logs/entries/{entry['id']}", headers=_headers("default"))
    assert detail_response.status_code == 200
    assert detail_response.get_json()["entry"]["event_id"] == "1001"

    forbidden_response = client.get(f"/api/logs/entries/{entry['id']}", headers=_headers("beta"))
    assert forbidden_response.status_code == 404

    with app_fixture.app_context():
        all_entries = LogEntry.query.filter_by(source_name="system").all()
        assert len(all_entries) == 4
