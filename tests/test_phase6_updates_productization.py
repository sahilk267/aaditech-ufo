"""Phase 6 P1-C updates productization coverage."""

from server.auth import get_api_key
from server.extensions import db
from server.models import Organization, UpdateRun


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


def test_update_runs_history_detail_and_confidence_attachment(client, app_fixture):
    _ensure_tenant(app_fixture, "default", "Default Org")
    _ensure_tenant(app_fixture, "beta", "Beta Org")

    app_fixture.config["UPDATE_MONITOR_ADAPTER"] = "linux_test_double"
    app_fixture.config["UPDATE_ALLOWED_HOSTS"] = "host-a,host-b"
    app_fixture.config["UPDATE_MONITOR_MAX_ENTRIES"] = 3
    app_fixture.config["UPDATE_LINUX_MONITOR_TEST_DOUBLE"] = (
        "host-a=KB5030211|Security Update|2026-03-17||KB5031455|Cumulative Update|2026-03-12;"
        "host-b=KB6000001|Security Update|2026-04-01"
    )
    app_fixture.config["CONFIDENCE_ADAPTER"] = "linux_test_double"
    app_fixture.config["CONFIDENCE_ALLOWED_HOSTS"] = "host-a,host-b"
    app_fixture.config["CONFIDENCE_LINUX_TEST_DOUBLE_SCORES"] = "host-a=0.82|driver_age|reboot_pending|Moderate update risk"

    monitor_response = client.post("/api/updates/monitor", headers=_headers(), json={"host_name": "host-a"})
    assert monitor_response.status_code == 200
    monitor_payload = monitor_response.get_json()["updates"]
    run_id = monitor_payload["update_run_id"]
    assert monitor_payload["update_count"] == 2

    confidence_response = client.post(
        "/api/ai/confidence/score",
        headers=_headers(),
        json={
            "host_name": "host-a",
            "updates": monitor_payload["updates"],
            "reliability_score": 0.7,
            "update_run_id": run_id,
        },
    )
    assert confidence_response.status_code == 200
    confidence_payload = confidence_response.get_json()
    assert confidence_payload["update_run_id"] == run_id
    assert confidence_payload["confidence"]["confidence_score"] == 0.82

    beta_monitor = client.post("/api/updates/monitor", headers=_headers("beta"), json={"host_name": "host-b"})
    assert beta_monitor.status_code == 200

    list_response = client.get("/api/updates/runs?host_name=host-a", headers=_headers())
    assert list_response.status_code == 200
    payload = list_response.get_json()
    assert payload["total"] == 1
    listed_run = payload["update_runs"][0]
    assert listed_run["id"] == run_id
    assert listed_run["confidence_score"] == 0.82
    assert listed_run["summary"]["update_count"] == 2

    detail_response = client.get(f"/api/updates/runs/{run_id}", headers=_headers())
    assert detail_response.status_code == 200
    detail_payload = detail_response.get_json()["update_run"]
    assert detail_payload["updates_payload"]["latest_installed_on"] == "2026-03-17"
    assert detail_payload["confidence_payload"]["confidence_score"] == 0.82

    forbidden_response = client.get(f"/api/updates/runs/{run_id}", headers=_headers("beta"))
    assert forbidden_response.status_code == 404

    with app_fixture.app_context():
        runs = UpdateRun.query.all()
        assert len(runs) == 2
