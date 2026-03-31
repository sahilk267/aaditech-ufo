"""Joined operational-flow coverage for SPA-backed Phase 2 modules."""

from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
from unittest.mock import patch

from server.auth import get_api_key
from server.extensions import db
from server.models import Organization, SystemData


def _headers(tenant_slug: str = "default") -> dict[str, str]:
    return {
        "X-API-Key": get_api_key(),
        "X-Tenant-Slug": tenant_slug,
    }


def _ensure_tenant(app_fixture, slug: str = "default") -> Organization:
    with app_fixture.app_context():
        tenant = Organization.query.filter_by(slug=slug).first()
        if tenant is None:
            tenant = Organization(name="Default Organization", slug=slug, is_active=True)
            db.session.add(tenant)
            db.session.commit()
        return tenant


def _seed_alertable_system(app_fixture, tenant_slug: str = "default") -> None:
    with app_fixture.app_context():
        tenant = _ensure_tenant(app_fixture, slug=tenant_slug)
        db.session.add(
            SystemData(
                organization_id=tenant.id,
                serial_number="FLOW-SN-001",
                hostname="flow-host",
                cpu_usage=96.5,
                ram_usage=88.0,
                last_update=datetime.now(UTC).replace(tzinfo=None),
                status="active",
                deleted=False,
            )
        )
        db.session.commit()


def test_backup_releases_and_audit_operational_flow(client, app_fixture, tmp_path, monkeypatch):
    release_dir = tmp_path / "agent_releases"
    release_dir.mkdir(parents=True)
    app_fixture.config["AGENT_RELEASES_DIR"] = str(release_dir)

    monkeypatch.setattr(
        "server.blueprints.api.BackupService.list_backups",
        lambda: [{"filename": "backup_20260330_120000.db", "timestamp": "2026-03-30T12:00:00", "size": 12.5}],
    )
    monkeypatch.setattr(
        "server.blueprints.api.BackupService.create_backup",
        lambda db_path: {"success": True, "backup_filename": "backup_20260330_120000.db"},
    )
    monkeypatch.setattr(
        "server.blueprints.api.BackupService.restore_backup",
        lambda backup_path, db_path: {"success": True, "message": f"restored {backup_path}"},
    )

    upload = client.post(
        "/api/agent/releases/upload",
        headers=_headers(),
        data={
            "version": "4.0.0",
            "release_file": (BytesIO(b"flow-release-binary"), "agent.exe"),
        },
        content_type="multipart/form-data",
    )
    assert upload.status_code == 201
    assert upload.get_json()["release"]["filename"] == "aaditech-agent-4.0.0.exe"

    listing = client.get("/api/agent/releases", headers=_headers())
    assert listing.status_code == 200
    listing_payload = listing.get_json()
    assert listing_payload["count"] == 1
    assert listing_payload["releases"][0]["version"] == "4.0.0"

    guide = client.get(
        "/api/agent/releases/guide",
        headers=_headers(),
        query_string={"current_version": "3.5.0"},
    )
    assert guide.status_code == 200
    assert guide.get_json()["guide"]["recommended_version"] == "4.0.0"

    download = client.get(
        "/api/agent/releases/download/aaditech-agent-4.0.0.exe",
        headers={"X-API-Key": get_api_key()},
    )
    assert download.status_code == 200
    assert download.data == b"flow-release-binary"

    backups_list = client.get("/api/backups", headers=_headers())
    assert backups_list.status_code == 200
    assert backups_list.get_json()["backups"][0]["filename"] == "backup_20260330_120000.db"

    backup_create = client.post("/api/backups", headers=_headers())
    assert backup_create.status_code == 201
    assert backup_create.get_json()["backup"]["backup_filename"] == "backup_20260330_120000.db"

    backup_restore = client.post("/api/backups/backup_20260330_120000.db/restore", headers=_headers())
    assert backup_restore.status_code == 200
    assert "backup_20260330_120000.db" in backup_restore.get_json()["restore"]["message"]

    audit = client.get("/api/audit-events", headers=_headers(), query_string={"per_page": 100})
    assert audit.status_code == 200
    actions = {event["action"] for event in audit.get_json()["events"]}
    assert "agent.release.upload.api" in actions
    assert "backup.create.api" in actions
    assert "backup.restore.api" in actions


def test_alerts_automation_logs_and_audit_operational_flow(client, app_fixture, monkeypatch):
    _ensure_tenant(app_fixture)
    _seed_alertable_system(app_fixture)

    app_fixture.config["ALERT_WEBHOOK_ENABLED"] = True
    app_fixture.config["ALERT_WEBHOOK_URL"] = "http://example.local/hook"

    app_fixture.config["LOG_INGESTION_ADAPTER"] = "linux_test_double"
    app_fixture.config["LOG_INGESTION_ALLOWED_SOURCES"] = "system"
    app_fixture.config["LOG_LINUX_INGESTION_TEST_DOUBLE"] = "system=event_a|event_b"
    app_fixture.config["LOG_EVENT_QUERY_ADAPTER"] = "linux_test_double"
    app_fixture.config["LOG_LINUX_EVENT_QUERY_TEST_DOUBLE"] = (
        "system=2026-03-30T10:00:00Z|error|1001|system|CPU overload"
        "||2026-03-30T10:01:00Z|critical|1001|system|CPU overload repeated"
    )
    app_fixture.config["LOG_EVENT_STREAM_ADAPTER"] = "linux_test_double"
    app_fixture.config["LOG_LINUX_EVENT_STREAM_TEST_DOUBLE"] = "system=1|evtA||2|evtB"
    app_fixture.config["LOG_EVENT_STREAM_BATCH_SIZE"] = 2
    app_fixture.config["LOG_SEARCH_ADAPTER"] = "linux_test_double"
    app_fixture.config["LOG_LINUX_SEARCH_TEST_DOUBLE"] = (
        "system=2026-03-30T10:00:00Z|error|1001|system|CPU overload detected"
        "||2026-03-30T10:01:00Z|warning|1002|system|CPU recovered"
    )
    app_fixture.config["LOG_SEARCH_MAX_RESULTS"] = 10
    app_fixture.config["LOG_DRIVER_MONITOR_ADAPTER"] = "linux_test_double"
    app_fixture.config["LOG_DRIVER_ALLOWED_HOSTS"] = "localhost"
    app_fixture.config["LOG_LINUX_DRIVER_MONITOR_TEST_DOUBLE"] = "localhost=Audio Driver|1.0|VendorA|true"
    app_fixture.config["LOG_DRIVER_ERROR_ADAPTER"] = "linux_test_double"
    app_fixture.config["LOG_LINUX_DRIVER_ERROR_TEST_DOUBLE"] = "localhost=Display Driver|2.1|VendorB|false|unsigned"

    rule_create = client.post(
        "/api/alerts/rules",
        headers=_headers(),
        json={
            "name": "Flow CPU Critical",
            "metric": "cpu_usage",
            "operator": ">",
            "threshold": 90,
            "severity": "critical",
        },
    )
    assert rule_create.status_code == 201

    rules_list = client.get("/api/alerts/rules", headers=_headers())
    assert rules_list.status_code == 200
    assert any(rule["name"] == "Flow CPU Critical" for rule in rules_list.get_json()["rules"])

    evaluate = client.post("/api/alerts/evaluate", headers=_headers(), json={"apply_silences": False})
    assert evaluate.status_code == 200
    evaluated_alerts = evaluate.get_json()["alerts"]
    assert len(evaluated_alerts) >= 1

    prioritize = client.post(
        "/api/alerts/prioritize",
        headers=_headers(),
        json={"alerts": evaluated_alerts, "top_n": 5},
    )
    assert prioritize.status_code == 200
    assert prioritize.get_json()["prioritized_alerts"][0]["severity"] == "critical"

    with patch("server.services.notification_service.NotificationService.send_webhook_notification") as webhook_mock:
        webhook_mock.return_value = None

        dispatch = client.post(
            "/api/alerts/dispatch",
            headers=_headers(),
            json={"alerts": evaluated_alerts, "channels": ["webhook"], "deduplicate": True},
        )

    assert dispatch.status_code == 202
    dispatch_result = dispatch.get_json()["job"]["result"]
    assert dispatch_result["failure_count"] == 0
    assert "webhook" in dispatch_result["delivered_channels"]

    workflow_create = client.post(
        "/api/automation/workflows",
        headers=_headers(),
        json={
            "name": "Restart Spooler Flow",
            "description": "SPA-compatible workflow payload",
            "trigger_type": "alert",
            "trigger_conditions": {"metric": "cpu_usage"},
            "action_type": "service_restart",
            "action_config": {"service_name": "spooler"},
            "is_active": True,
        },
    )
    assert workflow_create.status_code == 201
    workflow_id = workflow_create.get_json()["workflow"]["id"]

    workflows_list = client.get("/api/automation/workflows", headers=_headers())
    assert workflows_list.status_code == 200
    assert any(workflow["id"] == workflow_id for workflow in workflows_list.get_json()["workflows"])

    monkeypatch.setattr(
        "server.blueprints.api.AutomationService.get_service_status",
        lambda service_name, runtime_config=None: ({"service_name": service_name, "status": "running"}, None),
    )

    service_status = client.post(
        "/api/automation/services/status",
        headers=_headers(),
        json={"service_name": "spooler"},
    )
    assert service_status.status_code == 200
    assert service_status.get_json()["service"]["status"] == "running"

    execute = client.post(
        f"/api/automation/workflows/{workflow_id}/execute",
        headers=_headers(),
        json={"dry_run": True, "payload": {"reason": "flow-check"}},
    )
    assert execute.status_code == 202
    assert execute.get_json()["job"]["accepted"] is True

    self_heal = client.post(
        "/api/automation/self-heal",
        headers=_headers(),
        json={"alerts": evaluated_alerts, "dry_run": True},
    )
    assert self_heal.status_code == 200
    assert self_heal.get_json()["self_healing"]["alert_count"] >= 1

    ingest = client.post("/api/logs/ingest", headers=_headers(), json={"source_name": "system"})
    assert ingest.status_code == 200
    assert ingest.get_json()["logs"]["entry_count"] == 2

    query = client.post("/api/logs/events/query", headers=_headers(), json={"source_name": "system"})
    assert query.status_code == 200
    events = query.get_json()["events"]["entries"]
    assert len(events) == 2

    parse = client.post("/api/logs/parse", headers=_headers(), json={"entries": events})
    assert parse.status_code == 200
    parsed_events = parse.get_json()["parsed"]["events"]
    assert len(parsed_events) == 2

    correlate = client.post(
        "/api/logs/events/correlate",
        headers=_headers(),
        json={"events": parsed_events, "allowed_severities": ["error", "critical"], "min_group_size": 2},
    )
    assert correlate.status_code == 200
    assert correlate.get_json()["correlation"]["group_count"] >= 1

    stream = client.post("/api/logs/events/stream", headers=_headers(), json={"source_name": "system"})
    assert stream.status_code == 200
    assert stream.get_json()["stream"]["event_count"] == 2

    search = client.post(
        "/api/logs/search",
        headers=_headers(),
        json={"source_name": "system", "query_text": "CPU"},
    )
    assert search.status_code == 200
    assert search.get_json()["search"]["result_count"] >= 1

    drivers = client.post("/api/logs/drivers/monitor", headers=_headers(), json={"host_name": "localhost"})
    assert drivers.status_code == 200
    assert drivers.get_json()["drivers"]["driver_count"] == 1

    driver_errors = client.post("/api/logs/drivers/errors", headers=_headers(), json={"host_name": "localhost"})
    assert driver_errors.status_code == 200
    assert driver_errors.get_json()["driver_errors"]["error_count"] == 1

    audit = client.get("/api/audit-events", headers=_headers(), query_string={"per_page": 100})
    assert audit.status_code == 200
    actions = {event["action"] for event in audit.get_json()["events"]}
    assert "alerts.rule.create" in actions
    assert "alerts.dispatch.enqueue" in actions
    assert "automation.workflow.create" in actions
    assert "automation.execute.enqueue" in actions
    assert "logs.ingest" in actions
    assert "logs.search" in actions
