# AADITECH UFO — Production Deploy Guide

This document is the operator-facing runbook for taking the platform live. It
covers the server (Flask + React/Vite) and the Windows agent (PyInstaller +
NSIS).

---

## 1. Prerequisites

### Server host
- **OS**: Linux (Ubuntu 22.04+ recommended) or any container runtime.
- **Python**: 3.11 (matches CI).
- **Node**: 20.x for the frontend build.
- **Database**: PostgreSQL 14+ (set `DATABASE_URL`).
- **Cache / rate-limiter**: Redis 7+ (set `RATELIMIT_STORAGE_URL`,
  e.g. `redis://redis-host:6379/0`). The app **falls back to in-memory
  storage** automatically if Redis is unreachable — do **not** rely on this in
  production; it is for graceful degradation only.
- **Reverse proxy**: nginx / Caddy with TLS (Let's Encrypt or commercial cert).

### Agent host (Windows)
- Windows Server 2016+ or Windows 10+.
- Local admin rights (installer registers an uninstaller and writes to
  `C:\Program Files\AaditechUfo\Agent`).

---

## 2. Required environment variables

| Variable | Purpose | Example |
|---|---|---|
| `SECRET_KEY` | Flask session/JWT signing key. **Rotate per environment.** | `openssl rand -hex 32` |
| `DATABASE_URL` | SQLAlchemy URI for Postgres. | `postgresql+psycopg2://user:pw@host:5432/ufo` |
| `RATELIMIT_STORAGE_URL` | Redis URL for rate limits. | `redis://redis:6379/0` |
| `AGENT_API_KEY` | Shared key the agent uses for `/api/submit_data`. | `openssl rand -base64 48` |
| `DEFAULT_TENANT_SLUG` | Slug of the tenant that anonymous endpoints fall back to. | `default` |
| `JWT_SECRET_KEY` | (Optional) Separate JWT secret. Falls back to `SECRET_KEY`. | — |

Set these via the platform's secrets manager (Replit Secrets, AWS SSM, etc.).
Never commit them to git.

---

## 3. First-time deploy (server)

1. Install runtime deps:
   ```bash
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```
2. Run database migrations (Alembic):
   ```bash
   python -c "from server.app import create_app; from flask_migrate import upgrade; \
              app = create_app(); ctx = app.app_context(); ctx.push(); upgrade()"
   ```
3. Build the frontend:
   ```bash
   cd frontend && npm ci && npm run build
   ```
4. Start the server (production mode):
   ```bash
   gunicorn -k gthread -w 4 -b 0.0.0.0:5000 'server.app:create_app()'
   ```
5. Verify:
   ```bash
   curl -fsS https://your-domain.example.com/api/health
   # => {"status": "healthy", "database": "connected"}
   ```

---

## 4. Rolling out the agent

1. **Build the installer** (Windows runner — local or GitHub Actions
   `Test Suite > windows-installer` job):
   ```powershell
   pwsh ./scripts/build_agent_windows_installer.ps1 -Version 1.2.3
   ```
   Output: `agent/AaditechUfoAgentSetup-1.2.3.exe`
2. **Upload** the installer via the **Releases** page in the admin UI
   (or `POST /api/agent/releases/upload`).
3. **Distribute** the installer to fleet hosts. The installer:
   - Drops the binary into `C:\Program Files\AaditechUfo\Agent\`.
   - Writes `version.txt`.
   - Registers an Add/Remove Programs entry.
   - Adds a Start Menu shortcut.
4. **Configure the agent** by setting these env vars on the host (e.g. via
   Group Policy or a `.env` next to the binary):
   - `SERVER_BASE_URL=https://your-domain.example.com`
   - `AGENT_API_KEY=<value matching server>`
   - `TENANT_SLUG=<tenant slug for this host>`
5. The agent will:
   - Submit telemetry every `AGENT_REPORT_INTERVAL_SECONDS` (default 60s).
   - Buffer offline submissions in a local SQLite outbox and replay on
     reconnect (T2).
   - Poll `/api/agent/commands/pending` every
     `AGENT_COMMAND_POLL_INTERVAL_SECONDS` (default 30s) and execute
     whitelisted remote commands (T5).

---

## 5. TLS pinning + key rotation

### Pin the server certificate (T6)
Lock fleet agents to the production cert SHA-256 so a compromised intermediate
CA cannot serve a fake `your-domain.example.com`:

```bash
# Compute the SHA-256 of the deployed cert
SHA=$(openssl s_client -servername your-domain.example.com \
        -connect your-domain.example.com:443 </dev/null 2>/dev/null \
      | openssl x509 -outform DER \
      | openssl dgst -sha256 -hex | awk '{print $2}')

# Push it to the server
curl -X PUT https://your-domain.example.com/api/agent/cert/pin \
     -H "X-API-Key: $ADMIN_KEY" \
     -H "Content-Type: application/json" \
     -d "{\"cert_sha256\": \"$SHA\", \"label\": \"prod-2026-04\"}"
```

Agents fetch the active pin on startup and refuse to talk to any other cert.
Rotating the pin (PUT again with a new SHA) deactivates the previous one
automatically.

### Rotate the agent API key
```bash
curl -X POST https://your-domain.example.com/api/agent/key/rotate \
     -H "X-API-Key: $ADMIN_KEY" \
     -d '{"grace_seconds": 600}'
# Response includes new_api_key (shown ONCE) and a 10-minute grace window.
```
Distribute the new key to agents via your config-management tool. The old key
remains valid for `grace_seconds` so deploys are not racy.

---

## 6. Health & observability

- **Liveness probe**: `GET /api/health` (no auth, returns 200 + JSON).
- **Audit log**: every privileged action (command queue, pin set, key rotate)
  emits a structured row to the `audit_events` table.
- **Metrics**: agent posts CPU/RAM/network into `system_data` every interval.
- **Alerting**: configure rules under `/api/alerts/rules`.

---

## 7. CI / release pipeline

- `.github/workflows/test.yml` runs:
  1. `python-tests` — pytest suite (Redis fallback, transport, command client,
     command endpoints, cert pin, production smoke).
  2. `frontend-typecheck` — strict `tsc -b --force`.
  3. `windows-installer` — PyInstaller + NSIS, only on `main` push, uploads
     `aaditech-ufo-agent-installer` artifact.
- `.github/workflows/agent-release-publish.yml` (existing) publishes signed
  releases on git tags.

---

## 8. Production smoke checklist

After deploy, run:
```bash
pytest tests/test_production_smoke.py -v
```
All eight checks must pass before declaring the rollout green.

---

## 9. Rollback

If the new release misbehaves:
1. Keep the previous installer on the Releases page.
2. Set the **rollback target** under
   `/api/agent/releases/policy` (`rollback_version`).
3. Agents pick up the policy on the next update interval and downgrade
   themselves cleanly via the existing updater path.
