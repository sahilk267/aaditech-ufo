# Production Deployment Plan

## Goal
Prepare AADITECH UFO for production deployment using a real IP/DNS name and port `9773`, with secure environment variables and agent configuration.

This plan is intentionally a documentation-only change. No application code or configuration files are modified until the plan is finalized and approved.

---

## 1. Deployment target

Use a public/private hostname and port instead of localhost:
- Example DNS: `UFOMUM-MAS.ufomoviez.com`
- Example IP: `10.73.77.58` (replace with the actual production IP)
- Use port: `9773`

The agent EXE should not point to `localhost:5000`; it should point to the deployed gateway host and port.

> Implementation note: `.env.prod` has been updated to use `NGINX_PORT=9773`, `SERVER_BASE_URL=http://UFOMUM-MAS.ufomoviez.com:9773`, and a new production `AGENT_API_KEY`.

---

## 2. Required environment variables for production

Update `.env.prod` or the production environment store with the following values:

### Core service settings
- `FLASK_ENV=production`
- `FLASK_DEBUG=False`
- `NGINX_PORT=9773`
- `VITE_API_BASE_URL=/api`

### Backend and agent security
- `SECRET_KEY=<secure-random-value>`
- `JWT_SECRET_KEY=<secure-random-value>`
- `AGENT_API_KEY=<secure-random-value>`
- `DB_PASSWORD=<secure-random-value>`
- `REDIS_PASSWORD=<secure-random-value>`
- `TENANT_HEADER=X-Tenant-Slug`
- `DEFAULT_TENANT_SLUG=default`

### Agent runtime configuration
If the agent EXE is packaged for production, configure these environment values for the agent runtime or deployment manifest:
- `SERVER_BASE_URL=http://UFOMUM-MAS.ufomoviez.com:9773`
- `AGENT_SUBMIT_PATH=/api/submit_data`
- `AGENT_API_KEY=<same-secure-api-key-as-backend>`
- `TENANT_HEADER=X-Tenant-Slug`
- `TENANT_SLUG=default` (or actual tenant slug)
- `AGENT_REPORT_INTERVAL_SECONDS=60`
- `AGENT_REQUEST_TIMEOUT_SECONDS=10`

> Note: If HTTPS will be used, change `SERVER_BASE_URL` to `https://UFOMUM-MAS.ufomoviez.com:9773` and configure TLS on the gateway.

---

## 3. Gateway and service port mapping

The deployed `gateway` service should expose port `9773` externally and forward internal requests to the backend and frontend services.

### Required production compose changes (planned)
- In `docker-compose.prod.yml` or the production runtime configuration:
  - Set `NGINX_PORT=9773`
  - Confirm `gateway` service publishes external port `9773`
  - Confirm backend app remains accessible on internal port `5000`
  - Confirm frontend static server remains accessible on internal port `3000`

### Expected external access
- `http://UFOMUM-MAS.ufomoviez.com:9773/app` for the SPA
- `http://UFOMUM-MAS.ufomoviez.com:9773/api/...` for API calls
- Agent POST endpoint: `http://UFOMUM-MAS.ufomoviez.com:9773/api/submit_data`

---

## 4. API key generation

Generate secure API keys and secrets using a trusted random generator.

Example command:
```bash
python - <<'PY'
import secrets
for name in ['SECRET_KEY', 'JWT_SECRET_KEY', 'AGENT_API_KEY', 'DB_PASSWORD', 'REDIS_PASSWORD']:
    print(f'{name}={secrets.token_urlsafe(32)}')
PY
```

Use the generated values in the production environment only.

---

## 5. Agent data submission behavior

The EXE built from `agent/agent.py` sends data to:
- `SERVER_BASE_URL` + `AGENT_SUBMIT_PATH`
- default values in code: `http://localhost:5000` + `/api/submit_data`

For production, set:
- `SERVER_BASE_URL=http://UFOMUM-MAS.ufomoviez.com:9773`
- `AGENT_SUBMIT_PATH=/api/submit_data`

The payload includes:
- `serial_number`
- `hostname`
- `model_number`
- `local_ip`
- `public_ip`
- `cpu_info`
- `cpu_cores`
- `cpu_threads`
- `ram_info`
- `current_user`
- `cpu_usage`
- `cpu_per_core`
- `cpu_frequency`
- `ram_usage`
- `storage_usage`
- `disk_info`
- `software_benchmark`
- `hardware_benchmark`
- `overall_benchmark`
- `last_update`
- `status`

Also, request headers include:
- `X-API-Key: <AGENT_API_KEY>`
- `X-Tenant-Slug: <TENANT_SLUG>` (if configured)

---

## 6. Validation steps before deployment

1. Confirm `.env.prod` contains the real DNS/IP and `NGINX_PORT=9773`.
2. Confirm `AGENT_API_KEY` is generated and matches backend config.
3. Confirm `SERVER_BASE_URL` for the agent is pointed at `http://UFOMUM-MAS.ufomoviez.com:9773`.
4. Rebuild production images and restart services:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml pull
   docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
   ```
5. Check service health:
   - `docker compose -f docker-compose.yml -f docker-compose.prod.yml ps`
   - `docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail 50 gateway`
6. Validate with direct requests:
   - `curl -I http://UFOMUM-MAS.ufomoviez.com:9773/app`
   - `curl -H "X-API-Key: <key>" http://UFOMUM-MAS.ufomoviez.com:9773/api/agent/releases`
   - `curl -H "X-API-Key: <key>" http://UFOMUM-MAS.ufomoviez.com:9773/api/agent/releases/download/<filename>`

---

## 7. Rollout considerations

- Use DNS and port `9773` consistently across frontend, backend, gateway, and agent config.
- Keep internal service ports unchanged for container networking (`5000` backend, `3000` frontend) and use gateway mapping for external traffic.
- Store secrets out of source control and deploy them via environment or secret manager.
- Do not hardcode `localhost` in a production agent package.
- If using HTTPS, update TLS certs and `SERVER_BASE_URL` accordingly.

---

## 8. Next action (after approval)

Once the plan is approved, the implementation tasks are:
1. update `.env.prod` with production DNS/IP and `NGINX_PORT=9773`
2. ensure `AGENT_API_KEY` and other secrets are generated
3. update `DOCKER_DEPLOYMENT_GUIDE.md` or documentation to reflect the new production hostname and port
4. rebuild and deploy services
5. test frontend, API, and agent download/upload flows
