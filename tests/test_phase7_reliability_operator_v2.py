"""Phase 7 P1-A reliability operator v2 coverage."""

from pathlib import Path
from tempfile import TemporaryDirectory

from server.auth import get_api_key
from server.extensions import db
from server.models import Organization, ReliabilityRun, SystemData


def _headers(tenant_slug: str = "default") -> dict[str, str]:
    return {
        "X-API-Key": get_api_key(),
        "X-Tenant-Slug": tenant_slug,
    }


def _ensure_tenant(app_fixture, slug: str, name: str) -> int:
    with app_fixture.app_context():
        tenant = Organization.query.filter_by(slug=slug).first()
        if tenant is None:
            tenant = Organization(name=name, slug=slug, is_active=True)
            db.session.add(tenant)
            db.session.commit()
        return int(tenant.id)


def _seed_rows(app_fixture, tenant_slug: str, host_name: str) -> None:
    with app_fixture.app_context():
        tenant_id = _ensure_tenant(app_fixture, tenant_slug, f"{tenant_slug.title()} Org")
        db.session.add_all([
            SystemData(
                organization_id=tenant_id,
                serial_number=f"{tenant_slug}-relv2-1",
                hostname=host_name,
                cpu_usage=88.0,
                ram_usage=81.0,
                storage_usage=79.0,
                status="active",
            ),
            SystemData(
                organization_id=tenant_id,
                serial_number=f"{tenant_slug}-relv2-2",
                hostname=host_name,
                cpu_usage=41.0,
                ram_usage=40.0,
                storage_usage=51.0,
                status="active",
            ),
        ])
        db.session.commit()


def test_reliability_report_and_latest_per_type_filters(client, app_fixture):
    _seed_rows(app_fixture, "default", "host-local")

    app_fixture.config["RELIABILITY_HISTORY_ADAPTER"] = "local_database"
    app_fixture.config["RELIABILITY_SCORER_ADAPTER"] = "local_database"
    app_fixture.config["RELIABILITY_TREND_ADAPTER"] = "local_database"
    app_fixture.config["RELIABILITY_PREDICTION_ADAPTER"] = "local_database"
    app_fixture.config["RELIABILITY_PATTERN_ADAPTER"] = "local_database"
    app_fixture.config["RELIABILITY_ALLOWED_HOSTS"] = "host-local"

    assert client.post("/api/reliability/score", headers=_headers(), json={"host_name": "host-local"}).status_code == 200
    assert client.post("/api/reliability/score", headers=_headers(), json={"host_name": "host-local"}).status_code == 200
    assert client.post("/api/reliability/trends/analyze", headers=_headers(), json={"host_name": "host-local"}).status_code == 200
    assert client.post("/api/reliability/predictions/analyze", headers=_headers(), json={"host_name": "host-local"}).status_code == 200

    report_response = client.get("/api/reliability/report?host_name=host-local", headers=_headers())
    assert report_response.status_code == 200
    report = report_response.get_json()["report"]
    assert report["status_counts"]["success"] == 4
    assert report["diagnostic_counts"]["score"] == 2
    assert "current_score" in report["latest_score"]
    assert "direction" in report["latest_trend"]
    assert "predicted_score" in report["latest_prediction"]

    latest_only_response = client.get("/api/reliability/runs?host_name=host-local&latest_per_type=true", headers=_headers())
    assert latest_only_response.status_code == 200
    latest_payload = latest_only_response.get_json()
    assert latest_payload["total"] == 3
    assert {item["diagnostic_type"] for item in latest_payload["reliability_runs"]} == {"score", "trend", "prediction"}


def test_reliability_run_detail_includes_related_crash_runs_and_error_filter(client, app_fixture):
    _ensure_tenant(app_fixture, "default", "Default Org")

    with TemporaryDirectory() as temp_dir:
        dump_dir = Path(temp_dir)
        dump_path = dump_dir / "kernel-crash.dmp"
        dump_path.write_bytes(b"crash-dump-content")

        app_fixture.config["RELIABILITY_CRASH_DUMP_ADAPTER"] = "local_filesystem"
        app_fixture.config["RELIABILITY_EXCEPTION_IDENTIFIER_ADAPTER"] = "local_filesystem"
        app_fixture.config["RELIABILITY_STACK_TRACE_ADAPTER"] = "local_filesystem"
        app_fixture.config["RELIABILITY_ALLOWED_HOSTS"] = "host-a"
        app_fixture.config["RELIABILITY_ALLOWED_DUMP_ROOTS"] = str(dump_dir)
        app_fixture.config["RELIABILITY_CRASH_DUMP_ROOT"] = str(dump_dir)

        parse_response = client.post(
            "/api/reliability/crash-dumps/parse",
            headers=_headers(),
            json={"host_name": "host-a", "dump_name": dump_path.name},
        )
        assert parse_response.status_code == 200
        assert client.post(
            "/api/reliability/exceptions/identify",
            headers=_headers(),
            json={"host_name": "host-a", "dump_name": dump_path.name},
        ).status_code == 200
        assert client.post(
            "/api/reliability/stack-traces/analyze",
            headers=_headers(),
            json={"host_name": "host-a", "dump_name": dump_path.name},
        ).status_code == 200

        with app_fixture.app_context():
            tenant_id = _ensure_tenant(app_fixture, "default", "Default Org")
            db.session.add(
                ReliabilityRun(
                    organization_id=tenant_id,
                    diagnostic_type="score",
                    host_name="host-a",
                    status="failure",
                    error_reason="command_failed",
                    request_payload={"host_name": "host-a"},
                    result_payload={"error": "failed"},
                    summary={"note": "failed"},
                )
            )
            db.session.commit()

        failure_list = client.get("/api/reliability/runs?host_name=host-a&error_reason=command_failed", headers=_headers())
        assert failure_list.status_code == 200
        failure_payload = failure_list.get_json()
        assert failure_payload["total"] == 1
        assert failure_payload["reliability_runs"][0]["error_reason"] == "command_failed"

        runs_response = client.get("/api/reliability/runs?host_name=host-a&dump_name=kernel-crash.dmp", headers=_headers())
        assert runs_response.status_code == 200
        runs_payload = runs_response.get_json()
        parse_run = next(item for item in runs_payload["reliability_runs"] if item["diagnostic_type"] == "crash_dump_parse")

        detail_response = client.get(f"/api/reliability/runs/{parse_run['id']}", headers=_headers())
        assert detail_response.status_code == 200
        detail = detail_response.get_json()["reliability_run"]
        related_types = {item["diagnostic_type"] for item in detail["related_runs"]}
        assert {"exception_identify", "stack_trace_analyze"}.issubset(related_types)

        report_response = client.get("/api/reliability/report?host_name=host-a", headers=_headers())
        report = report_response.get_json()["report"]
        assert report["failure_reasons"]["command_failed"] == 1
        assert len(report["crash_related_runs"]) >= 3
