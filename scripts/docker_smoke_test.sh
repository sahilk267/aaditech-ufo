#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://localhost:8080}"

echo "[smoke] Checking gateway health: ${BASE_URL}/gateway/health"
curl -fsS "${BASE_URL}/gateway/health" >/dev/null

echo "[smoke] Checking app health via gateway: ${BASE_URL}/health"
curl -fsS "${BASE_URL}/health" >/dev/null

echo "[smoke] Checking API status endpoint reachability: ${BASE_URL}/api/status"
if [[ -n "${AGENT_API_KEY:-}" ]]; then
	http_code="$(curl -sS -o /tmp/aaditech-api-status.out -w "%{http_code}" -H "X-API-Key: ${AGENT_API_KEY}" "${BASE_URL}/api/status")"
	if [[ "${http_code}" != "200" ]]; then
		echo "[smoke] FAIL: expected 200 from /api/status with API key, got ${http_code}"
		cat /tmp/aaditech-api-status.out || true
		exit 1
	fi
else
	http_code="$(curl -sS -o /tmp/aaditech-api-status.out -w "%{http_code}" "${BASE_URL}/api/status")"
	if [[ "${http_code}" != "200" && "${http_code}" != "401" ]]; then
		echo "[smoke] FAIL: expected 200 or 401 from /api/status reachability check, got ${http_code}"
		cat /tmp/aaditech-api-status.out || true
		exit 1
	fi
fi

echo "[smoke] PASS: gateway/app/API health checks succeeded"
