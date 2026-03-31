"""Deployment-facing regression tests for gateway, SPA, and API routing."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
NGINX_CONFIG_PATH = REPO_ROOT / "gateway" / "nginx.conf"


class TestGatewayProxyContract:
    """Verify the gateway contract used in deployment-like setups."""

    def test_nginx_gateway_config_routes_all_traffic_to_app(self):
        config = NGINX_CONFIG_PATH.read_text(encoding="utf-8")

        assert "location = /gateway/health" in config
        assert "return 200 '{\"status\":\"healthy\",\"component\":\"nginx-gateway\"}';" in config
        assert "upstream aaditech_app" in config
        assert "server app:5000;" in config
        assert "location / {" in config
        assert "proxy_pass http://aaditech_app;" in config
        assert "proxy_set_header X-Forwarded-Proto $scheme;" in config
        assert "proxy_set_header X-Forwarded-Host $host;" in config
        assert "proxy_set_header X-Forwarded-Port $server_port;" in config
        assert "proxy_set_header X-Request-ID $request_id_upstream;" in config

    def test_api_health_is_gateway_ready_and_preserves_request_id(self, client):
        response = client.get(
            "/api/health",
            headers={
                "X-Forwarded-Proto": "https",
                "X-Forwarded-Host": "demo.example.com",
                "X-Forwarded-Port": "443",
                "X-Request-ID": "gateway-api-health",
            },
        )

        assert response.status_code == 200
        assert response.headers["X-API-Gateway-Ready"] == "true"
        assert response.headers["X-Request-ID"] == "gateway-api-health"

        payload = response.get_json()
        assert payload["status"] == "healthy"

    def test_spa_shell_is_gateway_ready_and_preserves_request_id(self, client):
        response = client.get(
            "/app/dashboard",
            headers={
                "X-Forwarded-Proto": "https",
                "X-Forwarded-Host": "demo.example.com",
                "X-Forwarded-Port": "443",
                "X-Request-ID": "gateway-spa-shell",
            },
        )

        assert response.status_code == 200
        assert response.content_type.startswith("text/html")
        assert response.headers["X-API-Gateway-Ready"] == "true"
        assert response.headers["X-Request-ID"] == "gateway-spa-shell"
        assert b"<!DOCTYPE" in response.data or b"<html" in response.data
