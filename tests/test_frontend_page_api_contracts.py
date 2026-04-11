"""Regression coverage for SPA pages against live Flask endpoint contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
import uuid

from server.auth import get_api_key, hash_password
from server.extensions import db
from server.models import AuditEvent, Organization, Permission, Role, SystemData, User


def _headers(tenant_slug: str = "default", extra: dict[str, str] | None = None) -> dict[str, str]:
    headers = {
        "X-API-Key": get_api_key(),
        "X-Tenant-Slug": tenant_slug,
    }
    if extra:
        headers.update(extra)
    return headers


def _ensure_tenant(app_fixture, slug: str = "default", name: str = "Default Organization") -> int:
    with app_fixture.app_context():
        tenant = Organization.query.filter_by(slug=slug).first()
        if tenant is None:
            tenant = Organization(name=name, slug=slug, is_active=True)
            db.session.add(tenant)
            db.session.commit()
        return tenant.id


def _seed_system(app_fixture, tenant_slug: str = "default", hostname: str = "spa-host") -> int:
    with app_fixture.app_context():
        tenant_id = _ensure_tenant(app_fixture, slug=tenant_slug)
        row = SystemData(
            organization_id=tenant_id,
            serial_number=f"SER-{uuid.uuid4().hex[:8]}",
            hostname=hostname,
            cpu_usage=33.3,
            ram_usage=44.4,
            last_update=datetime.now(UTC),
            status="active",
        )
        db.session.add(row)
        db.session.commit()
        return row.id


def _create_user_with_permissions(client, app_fixture, permission_codes: list[str], email: str | None = None) -> str:
    if email is None:
        email = f"spa-contract-{uuid.uuid4().hex[:8]}@tenant.local"

    with app_fixture.app_context():
        tenant_id = _ensure_tenant(app_fixture)

        role = Role(
            organization_id=tenant_id,
            name=f"role-{uuid.uuid4().hex[:8]}",
            description="SPA contract test role",
            is_system=False,
        )
        db.session.add(role)
        db.session.flush()

        for code in permission_codes:
            permission = Permission.query.filter_by(code=code).first()
            if permission is None:
                permission = Permission(code=code, description=f"Permission {code}")
                db.session.add(permission)
                db.session.flush()
            role.permissions.append(permission)

        user = User(
            organization_id=tenant_id,
            email=email,
            full_name="SPA Contract User",
            password_hash=hash_password("StrongPass123"),
            is_active=True,
        )
        user.roles.append(role)
        db.session.add(user)
        db.session.commit()

    login = client.post("/api/auth/login", json={"email": email, "password": "StrongPass123"})
    assert login.status_code == 200
    return login.get_json()["tokens"]["access_token"]


def test_dashboard_inventory_users_and_tenants_page_contracts(client, app_fixture, monkeypatch):
    system_id = _seed_system(app_fixture, hostname="dashboard-contract-host")

    monkeypatch.setattr(
        "server.blueprints.api.DashboardService.get_aggregate_dashboard_status",
        lambda host_name, runtime_config=None: (
            {
                "aggregate_health": {"overall_status": "healthy"},
                "host_name": host_name,
            },
            None,
        ),
    )
    monkeypatch.setattr(
        "server.blueprints.api.PerformanceService.get_or_compute",
        lambda cache_key, loader, ttl_seconds=None: (loader(), False),
    )

    dashboard_token = _create_user_with_permissions(client, app_fixture, ["dashboard.view"])

    status_response = client.get("/api/status", headers={"Authorization": f"Bearer {dashboard_token}"})
    assert status_response.status_code == 200
    status_payload = status_response.get_json()
    assert status_payload["status"] == "operational"
    assert "version" in status_payload

    systems_response = client.get("/api/systems", headers={"Authorization": f"Bearer {dashboard_token}"})
    assert systems_response.status_code == 200
    systems_payload = systems_response.get_json()
    assert systems_payload["count"] >= 1
    assert {"id", "hostname", "status", "last_update", "serial_number"} <= set(systems_payload["systems"][0].keys())

    detail_response = client.get(f"/api/system/{system_id}", headers={"Authorization": f"Bearer {dashboard_token}"})
    assert detail_response.status_code == 200
    detail_payload = detail_response.get_json()
    assert detail_payload["system"]["id"] == system_id
    assert detail_payload["system"]["hostname"] == "dashboard-contract-host"

    dashboard_status = client.get(
        "/api/dashboard/status",
        headers={"Authorization": f"Bearer {dashboard_token}"},
        query_string={"host_name": "dashboard-contract-host"},
    )
    assert dashboard_status.status_code == 200
    dashboard_payload = dashboard_status.get_json()
    assert dashboard_payload["status"] == "success"
    assert dashboard_payload["dashboard"]["aggregate_health"]["overall_status"] == "healthy"
    assert dashboard_payload["cache_hit"] is False

    tenant_admin_token = _create_user_with_permissions(client, app_fixture, ["tenant.manage", "dashboard.view"])
    me_response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tenant_admin_token}"})
    assert me_response.status_code == 200
    me_payload = me_response.get_json()
    assert isinstance(me_payload["user"]["permissions"], list)
    assert "tenant.manage" in me_payload["user"]["permissions"]

    create_user_response = client.post(
        "/api/users",
        headers={"Authorization": f"Bearer {tenant_admin_token}"},
        json={
            "email": f"new-user-{uuid.uuid4().hex[:8]}@tenant.local",
            "full_name": "New SPA User",
            "password": "StrongPass123",
        },
    )
    assert create_user_response.status_code == 201
    created_user = create_user_response.get_json()["user"]
    assert created_user["email"].startswith("new-user-")
    assert created_user["full_name"] == "New SPA User"

    tenants_response = client.get("/api/tenants", headers={"Authorization": f"Bearer {tenant_admin_token}"})
    assert tenants_response.status_code == 200
    tenants_payload = tenants_response.get_json()
    assert tenants_payload["count"] >= 1
    assert {"id", "name", "slug", "is_active"} <= set(tenants_payload["tenants"][0].keys())

    quotas_response = client.get("/api/tenant-quotas", headers={"Authorization": f"Bearer {tenant_admin_token}"})
    assert quotas_response.status_code == 200
    usage_report_response = client.get(
        "/api/tenant-usage/report",
        headers={"Authorization": f"Bearer {tenant_admin_token}"},
    )
    assert usage_report_response.status_code == 200
    usage_report_payload = usage_report_response.get_json()["tenant_usage_report"]
    assert "summary" in usage_report_payload
    assert "quotas" in usage_report_payload

    create_tenant_response = client.post(
        "/api/tenants",
        headers={"Authorization": f"Bearer {tenant_admin_token}"},
        json={"name": "SPA Contract Tenant", "slug": f"spa-{uuid.uuid4().hex[:8]}"},
    )
    assert create_tenant_response.status_code == 201
    assert create_tenant_response.get_json()["tenant"]["name"] == "SPA Contract Tenant"


def test_releases_backup_platform_and_audit_page_contracts(client, app_fixture, tmp_path, monkeypatch):
    release_dir = tmp_path / "agent_releases"
    release_dir.mkdir(parents=True)
    (release_dir / "aaditech-agent-2.5.0.exe").write_bytes(b"release-binary")
    app_fixture.config["AGENT_RELEASES_DIR"] = str(release_dir)

    with app_fixture.app_context():
        tenant_id = _ensure_tenant(app_fixture)
        db.session.add(
            AuditEvent(
                action="frontend.contract.check",
                outcome="success",
                tenant_id=tenant_id,
                event_metadata={"page": "audit"},
            )
        )
        db.session.commit()

    releases_response = client.get("/api/agent/releases", headers=_headers())
    assert releases_response.status_code == 200
    releases_payload = releases_response.get_json()
    assert releases_payload["count"] == 1
    assert releases_payload["releases"][0]["version"] == "2.5.0"
    assert releases_payload["releases"][0]["download_url"].endswith("/api/agent/releases/download/aaditech-agent-2.5.0.exe")

    policy_response = client.get("/api/agent/releases/policy", headers=_headers())
    assert policy_response.status_code == 200
    assert "policy" in policy_response.get_json()

    guide_response = client.get(
        "/api/agent/releases/guide",
        headers=_headers(),
        query_string={"current_version": "1.0.0"},
    )
    assert guide_response.status_code == 200
    guide_payload = guide_response.get_json()["guide"]
    assert guide_payload["recommended_version"] == "2.5.0"
    assert guide_payload["recommended_download_url"].endswith("/api/agent/releases/download/aaditech-agent-2.5.0.exe")

    upload_response = client.post(
        "/api/agent/releases/upload",
        headers=_headers(),
        data={
            "version": "3.0.0",
            "release_file": (BytesIO(b"new-release"), "agent.exe"),
        },
        content_type="multipart/form-data",
    )
    assert upload_response.status_code == 201
    assert upload_response.get_json()["release"]["filename"] == "aaditech-agent-3.0.0.exe"

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
    monkeypatch.setattr(
        "server.blueprints.api.PerformanceService.optimize_database",
        lambda database_uri: {"status": "success", "backend": "sqlite", "actions": ["analyze"]},
    )

    backups_list = client.get("/api/backups", headers=_headers())
    assert backups_list.status_code == 200
    assert backups_list.get_json()["backups"][0]["filename"] == "backup_20260330_120000.db"

    backup_create = client.post("/api/backups", headers=_headers())
    assert backup_create.status_code == 201
    assert backup_create.get_json()["backup"]["backup_filename"] == "backup_20260330_120000.db"

    backup_restore = client.post("/api/backups/backup_20260330_120000.db/restore", headers=_headers())
    assert backup_restore.status_code == 200
    assert "backup_20260330_120000.db" in backup_restore.get_json()["restore"]["message"]

    audit_response = client.get("/api/audit-events", headers=_headers())
    assert audit_response.status_code == 200
    audit_payload = audit_response.get_json()
    assert audit_payload["total"] >= 1
    assert audit_payload["events"][0]["action"]

    cache_response = client.get("/api/performance/cache/status", headers=_headers())
    assert cache_response.status_code == 200
    assert "cache" in cache_response.get_json()

    optimize_response = client.post("/api/database/optimize", headers=_headers(), json={"dry_run": True})
    assert optimize_response.status_code == 200
    assert optimize_response.get_json()["optimization"]["backend"] == "sqlite"

    maintenance_response = client.post(
        "/api/jobs/maintenance",
        headers=_headers(),
        json={"job": "cleanup_revoked_tokens"},
    )
    assert maintenance_response.status_code == 202
    assert maintenance_response.get_json()["status"] == "accepted"


def test_alerts_automation_and_logs_page_contracts(client, app_fixture, monkeypatch):
    _ensure_tenant(app_fixture)

    create_rule = client.post(
        "/api/alerts/rules",
        headers=_headers(),
        json={
            "name": "CPU Critical",
            "metric": "cpu_usage",
            "operator": ">",
            "threshold": 90,
            "severity": "critical",
        },
    )
    assert create_rule.status_code == 201

    rules_response = client.get("/api/alerts/rules", headers=_headers())
    assert rules_response.status_code == 200
    assert isinstance(rules_response.get_json()["rules"], list)

    silences_response = client.get("/api/alerts/silences", headers=_headers())
    assert silences_response.status_code == 200
    assert isinstance(silences_response.get_json()["silences"], list)

    evaluate_response = client.post("/api/alerts/evaluate", headers=_headers(), json={"apply_silences": False})
    assert evaluate_response.status_code == 200
    assert "alerts" in evaluate_response.get_json()

    prioritize_response = client.post(
        "/api/alerts/prioritize",
        headers=_headers(),
        json={"alerts": [{"severity": "critical", "metric": "cpu_usage", "actual_value": 98}], "top_n": 10},
    )
    assert prioritize_response.status_code == 200
    assert "prioritized_alerts" in prioritize_response.get_json()

    dispatch_response = client.post(
        "/api/alerts/dispatch",
        headers=_headers(),
        json={"alerts": [], "channels": ["email"], "deduplicate": True},
    )
    assert dispatch_response.status_code in {200, 202}
    assert dispatch_response.get_json()["status"] == "accepted"

    workflow_response = client.post(
        "/api/automation/workflows",
        headers=_headers(),
        json={
            "name": "Restart Service",
            "trigger_type": "manual",
            "trigger_conditions": {},
            "action_type": "service_restart",
            "action_config": {"service_name": "spooler"},
            "is_active": True,
        },
    )
    assert workflow_response.status_code == 201
    workflow_id = workflow_response.get_json()["workflow"]["id"]

    workflows_list = client.get("/api/automation/workflows", headers=_headers())
    assert workflows_list.status_code == 200
    assert isinstance(workflows_list.get_json()["workflows"], list)

    jobs_list = client.get("/api/automation/scheduled-jobs", headers=_headers())
    assert jobs_list.status_code == 200
    assert "scheduled_jobs" in jobs_list.get_json()

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

    execute_response = client.post(
        f"/api/automation/workflows/{workflow_id}/execute",
        headers=_headers(),
        json={"dry_run": True, "payload": {}},
    )
    assert execute_response.status_code == 202
    assert execute_response.get_json()["job"]["accepted"] is True

    self_heal = client.post("/api/automation/self-heal", headers=_headers(), json={"alerts": [], "dry_run": True})
    assert self_heal.status_code == 200
    assert self_heal.get_json()["status"] == "success"

    monkeypatch.setattr(
        "server.blueprints.api.LogService.ingest_logs",
        lambda source_name, runtime_config=None: ({"adapter": "test", "entry_count": 1}, None),
    )
    monkeypatch.setattr(
        "server.blueprints.api.LogService.query_event_entries",
        lambda source_name, runtime_config=None: (
            {"adapter": "test", "entry_count": 1, "entries": [{"source": source_name, "message": "error"}]},
            None,
        ),
    )
    monkeypatch.setattr(
        "server.blueprints.api.LogService.parse_log_entries",
        lambda entries, runtime_config=None: (
            {"entry_count": len(entries), "structured_count": len(entries), "entries": entries},
            None,
        ),
    )
    monkeypatch.setattr(
        "server.blueprints.api.LogService.filter_and_correlate_events",
        lambda events, runtime_config=None: ({"filtered_count": len(events), "group_count": 1, "groups": [{"size": len(events)}]}, None),
    )
    monkeypatch.setattr(
        "server.blueprints.api.LogService.stream_events",
        lambda source_name, runtime_config=None: ({"adapter": "test", "event_count": 1, "entries": [{"source": source_name}]}, None),
    )
    monkeypatch.setattr(
        "server.blueprints.api.LogService.search_and_index_logs",
        lambda source_name, query_text, runtime_config=None: (
            {"adapter": "test", "result_count": 1, "results": [{"source": source_name, "query": query_text}]},
            None,
        ),
    )
    monkeypatch.setattr(
        "server.blueprints.api.LogService.monitor_drivers",
        lambda host_name, runtime_config=None: ({"adapter": "test", "driver_count": 1, "drivers": [{"host": host_name}]}, None),
    )
    monkeypatch.setattr(
        "server.blueprints.api.LogService.detect_driver_errors",
        lambda host_name, runtime_config=None: ({"adapter": "test", "error_count": 1, "errors": [{"host": host_name}]}, None),
    )

    assert client.post("/api/logs/ingest", headers=_headers(), json={"source_name": "system"}).get_json()["status"] == "success"
    assert "events" in client.post("/api/logs/events/query", headers=_headers(), json={"source_name": "system"}).get_json()
    assert "parsed" in client.post("/api/logs/parse", headers=_headers(), json={"entries": [{"message": "error"}]}).get_json()
    assert "correlation" in client.post("/api/logs/events/correlate", headers=_headers(), json={"events": [{"severity": "error"}]}).get_json()
    assert "stream" in client.post("/api/logs/events/stream", headers=_headers(), json={"source_name": "system"}).get_json()
    assert "search" in client.post("/api/logs/search", headers=_headers(), json={"source_name": "system", "query_text": "error"}).get_json()
    assert "drivers" in client.post("/api/logs/drivers/monitor", headers=_headers(), json={"host_name": "localhost"}).get_json()
    assert "driver_errors" in client.post("/api/logs/drivers/errors", headers=_headers(), json={"host_name": "localhost"}).get_json()


def test_history_reliability_ai_updates_remote_and_platform_adjacent_page_contracts(client, app_fixture, monkeypatch):
    _ensure_tenant(app_fixture)

    monkeypatch.setattr(
        "server.blueprints.api.ReliabilityService.collect_reliability_history",
        lambda host_name, runtime_config=None: (
            {
                "adapter": "test",
                "record_count": 1,
                "records": [{"timestamp": "2026-03-30T12:00:00", "source": "system", "message": "Recovered"}],
            },
            None,
        ),
    )
    monkeypatch.setattr(
        "server.blueprints.api.ReliabilityService.score_reliability",
        lambda host_name, runtime_config=None: (
            {"adapter": "test", "reliability_score": {"current_score": 0.91, "health_band": "healthy"}},
            None,
        ),
    )
    monkeypatch.setattr(
        "server.blueprints.api.ReliabilityService.analyze_reliability_trend",
        lambda host_name, runtime_config=None: (
            {"adapter": "test", "trend": {"direction": "improving", "point_count": 1}, "series": []},
            None,
        ),
    )
    monkeypatch.setattr(
        "server.blueprints.api.ReliabilityService.predict_reliability",
        lambda host_name, runtime_config=None: (
            {"adapter": "test", "prediction": {"summary": "stable"}, "forecast": []},
            None,
        ),
    )
    monkeypatch.setattr(
        "server.blueprints.api.AIService.run_ollama_inference",
        lambda prompt_text, runtime_config=None: ({"adapter": "test", "model": "llama", "inference": {"response_text": "ok"}}, None),
    )
    monkeypatch.setattr(
        "server.blueprints.api.AIService.analyze_root_cause",
        lambda symptom_summary, evidence_points=None, runtime_config=None: (
            {"adapter": "test", "model": "llama", "root_cause": {"summary": "task loop", "confidence": 0.8}},
            None,
        ),
    )
    monkeypatch.setattr(
        "server.blueprints.api.AIService.generate_recommendations",
        lambda symptom_summary, probable_cause, evidence_points=None, runtime_config=None: (
            {"adapter": "test", "model": "llama", "recommendations": {"count": 1, "items": ["restart service"]}},
            None,
        ),
    )
    monkeypatch.setattr(
        "server.blueprints.api.UpdateService.monitor_windows_updates",
        lambda host_name, runtime_config=None: (
            {"adapter": "test", "update_count": 1, "updates": [{"kb": "KB123"}]},
            None,
        ),
    )
    monkeypatch.setattr(
        "server.blueprints.api.ConfidenceService.score_update_reliability_impact",
        lambda host_name, updates_list=None, reliability_score=None, ollama_model=None, runtime_config=None: (
            {"adapter": "test", "confidence_score": 0.77, "risk_factors": ["driver"]},
            None,
        ),
    )
    monkeypatch.setattr(
        "server.blueprints.api.RemoteExecutorService.execute_remote_command",
        lambda host, command, runtime_config=None: (
            {"adapter": "test", "host": host, "command": command, "stdout": "ok", "returncode": 0},
            None,
        ),
    )

    history = client.post("/api/reliability/history", headers=_headers(), json={"host_name": "localhost"})
    assert history.status_code == 200
    assert history.get_json()["history"]["records"][0]["source"] == "system"

    score = client.post("/api/reliability/score", headers=_headers(), json={"host_name": "localhost"})
    assert score.status_code == 200
    assert score.get_json()["reliability"]["reliability_score"]["current_score"] == 0.91

    trend = client.post("/api/reliability/trends/analyze", headers=_headers(), json={"host_name": "localhost"})
    assert trend.status_code == 200
    assert trend.get_json()["trend"]["trend"]["direction"] == "improving"

    prediction = client.post("/api/reliability/predictions/analyze", headers=_headers(), json={"host_name": "localhost"})
    assert prediction.status_code == 200
    assert prediction.get_json()["prediction"]["prediction"]["summary"] == "stable"

    inference = client.post("/api/ai/ollama/infer", headers=_headers(), json={"prompt": "explain CPU"})
    assert inference.status_code == 200
    assert inference.get_json()["ollama"]["inference"]["response_text"] == "ok"

    root_cause = client.post(
        "/api/ai/root-cause/analyze",
        headers=_headers(),
        json={"symptom_summary": "CPU spikes", "evidence_points": ["scheduler loop"]},
    )
    assert root_cause.status_code == 200
    assert root_cause.get_json()["analysis"]["root_cause"]["summary"] == "task loop"

    recommendations = client.post(
        "/api/ai/recommendations/generate",
        headers=_headers(),
        json={
            "symptom_summary": "CPU spikes",
            "probable_cause": "scheduler loop",
            "evidence_points": ["scheduler loop"],
        },
    )
    assert recommendations.status_code == 200
    assert recommendations.get_json()["recommendations"]["recommendations"]["count"] == 1

    ai_report = client.get("/api/ai/operations/report", headers=_headers(), query_string={"limit": 5})
    assert ai_report.status_code == 200
    ai_report_payload = ai_report.get_json()
    assert ai_report_payload["status"] == "success"
    assert "summary" in ai_report_payload["report"]
    assert "recent_operations" in ai_report_payload["report"]

    updates = client.post("/api/updates/monitor", headers=_headers(), json={"host_name": "localhost"})
    assert updates.status_code == 200
    assert updates.get_json()["updates"]["update_count"] == 1

    confidence = client.post(
        "/api/ai/confidence/score",
        headers=_headers(),
        json={"host_name": "localhost", "updates": [{"kb": "KB123"}], "reliability_score": 0.8},
    )
    assert confidence.status_code == 200
    assert confidence.get_json()["confidence"]["confidence_score"] == 0.77

    remote = client.post(
        "/api/remote/exec",
        headers=_headers(),
        json={"host": "127.0.0.1", "command": "hostname"},
    )
    assert remote.status_code == 200
    assert remote.get_json()["execution"]["returncode"] == 0
