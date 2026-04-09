"""Phase 6 P1-B reliability operator productization coverage."""

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
                serial_number=f"{tenant_slug}-rel-1",
                hostname=host_name,
                cpu_usage=85.0,
                ram_usage=80.0,
                storage_usage=78.0,
                status="active",
            ),
            SystemData(
                organization_id=tenant_id,
                serial_number=f"{tenant_slug}-rel-2",
                hostname=host_name,
                cpu_usage=45.0,
                ram_usage=44.0,
                storage_usage=52.0,
                status="active",
            ),
        ])
        db.session.commit()


def test_reliability_runs_list_and_detail_are_persisted(client, app_fixture):
    _seed_rows(app_fixture, "default", "host-local")
    _seed_rows(app_fixture, "beta", "host-beta")

    app_fixture.config["RELIABILITY_HISTORY_ADAPTER"] = "local_database"
    app_fixture.config["RELIABILITY_SCORER_ADAPTER"] = "local_database"
    app_fixture.config["RELIABILITY_TREND_ADAPTER"] = "local_database"
    app_fixture.config["RELIABILITY_PREDICTION_ADAPTER"] = "local_database"
    app_fixture.config["RELIABILITY_PATTERN_ADAPTER"] = "local_database"
    app_fixture.config["RELIABILITY_ALLOWED_HOSTS"] = "host-local,host-beta"

    assert client.post("/api/reliability/history", headers=_headers(), json={"host_name": "host-local"}).status_code == 200
    assert client.post("/api/reliability/score", headers=_headers(), json={"host_name": "host-local"}).status_code == 200
    assert client.post("/api/reliability/trends/analyze", headers=_headers(), json={"host_name": "host-local"}).status_code == 200

    beta_score = client.post("/api/reliability/score", headers=_headers("beta"), json={"host_name": "host-beta"})
    assert beta_score.status_code == 200

    list_response = client.get("/api/reliability/runs?host_name=host-local", headers=_headers())
    assert list_response.status_code == 200
    payload = list_response.get_json()
    assert payload["total"] == 3
    assert all(item["host_name"] == "host-local" for item in payload["reliability_runs"])
    assert {item["diagnostic_type"] for item in payload["reliability_runs"]} == {"history", "score", "trend"}

    score_run = next(item for item in payload["reliability_runs"] if item["diagnostic_type"] == "score")
    assert score_run["summary"]["current_score"] is not None

    detail_response = client.get(f"/api/reliability/runs/{score_run['id']}", headers=_headers())
    assert detail_response.status_code == 200
    detail_payload = detail_response.get_json()["reliability_run"]
    assert detail_payload["result_payload"]["reliability_score"]["current_score"] == score_run["summary"]["current_score"]

    forbidden_response = client.get(f"/api/reliability/runs/{score_run['id']}", headers=_headers("beta"))
    assert forbidden_response.status_code == 404

    with app_fixture.app_context():
        all_runs = ReliabilityRun.query.all()
        assert len(all_runs) == 4


def test_crash_workflows_persist_reliability_runs(client, app_fixture):
    _ensure_tenant(app_fixture, "default", "Default Org")

    with TemporaryDirectory() as temp_dir:
        dump_dir = Path(temp_dir)
        dump_path = dump_dir / "access-violation-app.dmp"
        dump_path.write_bytes(b"crash-dump-content")

        app_fixture.config["RELIABILITY_CRASH_DUMP_ADAPTER"] = "local_filesystem"
        app_fixture.config["RELIABILITY_EXCEPTION_IDENTIFIER_ADAPTER"] = "local_filesystem"
        app_fixture.config["RELIABILITY_STACK_TRACE_ADAPTER"] = "local_filesystem"
        app_fixture.config["RELIABILITY_ALLOWED_HOSTS"] = "host-a"
        app_fixture.config["RELIABILITY_ALLOWED_DUMP_ROOTS"] = str(dump_dir)
        app_fixture.config["RELIABILITY_CRASH_DUMP_ROOT"] = str(dump_dir)

        assert client.post(
            "/api/reliability/crash-dumps/parse",
            headers=_headers(),
            json={"host_name": "host-a", "dump_name": dump_path.name},
        ).status_code == 200
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

        runs_response = client.get("/api/reliability/runs?host_name=host-a", headers=_headers())
        assert runs_response.status_code == 200
        runs_payload = runs_response.get_json()
        assert runs_payload["total"] == 3
        diagnostic_types = {item["diagnostic_type"] for item in runs_payload["reliability_runs"]}
        assert diagnostic_types == {"crash_dump_parse", "exception_identify", "stack_trace_analyze"}
        assert all(item["dump_name"] == dump_path.name for item in runs_payload["reliability_runs"])
