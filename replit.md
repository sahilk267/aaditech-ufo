# Aaditech UFO - Universal Observability, Monitoring & Automation Platform

## Overview

This project is an enterprise-grade **Infrastructure Observability, Monitoring, Automation, and AI Analytics Platform**. It is a multi-tenant Flask backend that serves both server-rendered Jinja2 pages and a React (Vite) Single Page Application mounted at `/app`.

## Tech Stack

- **Backend:** Python 3.12, Flask 3, Flask-SQLAlchemy, Flask-Migrate (Alembic), Flask-Limiter, Celery (Redis-backed, optional)
- **Database:** PostgreSQL (Replit-managed)
- **Frontend:** React 19 + Vite + TypeScript (under `frontend/`), built into `frontend/dist/` and served by Flask at `/app`
- **Server entry:** `server/app.py` (`app = create_app()`)
- **Migrations:** `migrations/versions/` (Alembic via Flask-Migrate)

## Replit Setup

### Workflow

- **Server** — `python -m server.app` on port `5000` (webview)
  - Flask binds `0.0.0.0:5000` and applies Alembic migrations on startup.
  - Serves API, Jinja templates, and the built SPA from `frontend/dist`.

### Database

PostgreSQL is provisioned via Replit's built-in database. The `DATABASE_URL` environment variable is automatically populated.

### Frontend Build

The React SPA is pre-built into `frontend/dist/` so Flask can serve it. To rebuild after frontend changes:

```bash
cd frontend && npx vite build
```

The strict TypeScript check (`npx tsc -b --force` in `frontend/`) now passes cleanly after fixes to `src/lib/axios.ts` (AxiosHeaders.from + .set/.delete) and `tsconfig.test.json` (empty `exclude` array).

### Deployment

Configured for **autoscale** deployment:

- **Build:** `pip install -r requirements.txt && cd frontend && npm install && npx vite build`
- **Run:** Apply migrations, then `gunicorn --bind=0.0.0.0:5000 --workers=2 --timeout=60 server.app:app`

## Local Fixes Applied During Import

1. **`migrations/env.py`** — Added explicit `connection.commit()` calls so Alembic migrations actually persist under SQLAlchemy 2.0 (the previous transactional-DDL block was being rolled back, leaving the schema empty).
2. **`frontend/src/pages/logs/LogsPage.tsx`** — Added a placeholder module page; the file was referenced by the SPA router but missing from the import, breaking the Vite build.

## Default Admin Seed

Run `python -m scripts.seed_default_admin` to (re)create a default admin in the `default` tenant.

Default credentials (override with CLI flags or `SEED_ADMIN_*` env vars):

- Tenant Slug: `default`
- Email: `admin@example.com`
- Password: `ChangeMe123!`

The script is idempotent: it will reuse the existing tenant/role and reset the user's password if the user already exists. The user is granted the built-in `admin` role with `tenant.manage`, `dashboard.view`, `system.submit`, `backup.manage`, and `automation.manage` permissions.

## Notes

- Redis is **not** provisioned by default. Celery and rate-limiting fall back to in-memory storage; the `/health` endpoint reports Redis as `disconnected`, which is expected in this environment.
- The SPA is served at `/app` and `/app/*`; the legacy server-rendered UI (login, dashboard, admin) is at `/`.
- The default tenant slug is `default`; tenants are auto-created on first request.

## Agent Release / .exe Build Pipeline

PyInstaller cannot cross-compile a Windows `.exe` from the Linux server, so a dedicated pipeline is in place. Full operator documentation lives at `docs/AGENT_RELEASE_BUILD.md`.

- **Server endpoint** `POST /api/agent/build` returns `windows_compatible` (bool) + `guidance` (string) so the SPA can warn operators when a non-Windows build runs. Status is `success` on Windows runtimes and `success_non_windows` elsewhere.
- **SPA Releases page** (`frontend/src/pages/releases/ReleasesPage.tsx`) now shows a "How to obtain a Windows .exe" panel, inline version-regex/file-extension/size validation on the upload form, and a yellow runtime-mismatch banner above the server-build button.
- **GitHub Actions workflow** `.github/workflows/agent-release-publish.yml` runs on `windows-latest`, builds via `scripts/build_agent_windows.ps1`, attaches the `.exe` to a GitHub Release, and (when secrets `AGENT_RELEASE_UPLOAD_URL` + `AGENT_RELEASE_API_KEY` are set, plus optional `AGENT_RELEASE_TENANT_SLUG`) auto-uploads it to the running server. A job-summary step records what was published.
- **Agent self-update** — `agent/updater.py` polls `/api/agent/releases/guide` every `AGENT_UPDATE_CHECK_INTERVAL_SECONDS` (default 1h), verifies the recommended `.exe` against the SHA-256 returned by the server (now exposed by `AgentReleaseService.list_releases`), atomically swaps the running binary, and re-execs. Guards: only runs when `sys.frozen` is true (i.e. a real PyInstaller build) and the API key is not the placeholder default. The PowerShell build script and CI workflow stamp `agent/version.py` with the requested version so the running .exe truthfully reports `agent_version` in metric submissions.
- **Agent log forwarding** — `agent/log_forwarder.py` (opt-in via `AGENT_LOG_FORWARD_ENABLED=1`) tails any number of file paths and (on Windows) `wevtutil` event-log channels, formats each entry as `<ts>|<sev>|<event_id>|<source>|<message>`, batches up to 200 entries, and POSTs to `/api/logs/parse` which persists them as `LogEntry` rows. State (per-file byte offsets and per-channel `EventRecordID`) is saved to a JSON file so restarts never re-send historical lines; rotation/truncation is detected via inode + size shrink. End-to-end smoke-tested against the running server.

## Production Hardening (2026-04-29)

The following operability + security features completed this session — all backed by tests in `tests/`:

1. **Redis fallback (T1)** — `server/extensions._resolve_limiter_storage` pings the configured Redis URL and falls back to `memory://` automatically. Resolved storage is exposed as `app.config['_LIMITER_STORAGE_RESOLVED']`. Tests: `tests/test_redis_fallback.py` (6).
2. **Agent retry + offline outbox (T2)** — `agent/transport.py` wraps every outbound POST with bounded retries and a SQLite-backed outbox (WAL mode, capped queue). Wired into `agent/agent.send_data`. Tests: `tests/test_agent_transport.py` (10).
3. **Strict TypeScript (T3)** — `npx tsc -b --force` exits 0 after fixes to `frontend/src/lib/axios.ts` (AxiosHeaders) and `frontend/tsconfig.test.json` (empty exclude).
4. **Remote command queue (T5)** — Models `AgentCommand` + endpoints `POST /api/agent/commands`, `GET /api/agent/commands/pending`, `POST /api/agent/commands/<id>/result`. Whitelisted command types only. Agent-side executor (`agent/commands.py`) is wired into the main loop with allow-listed PowerShell prefixes and shell-metachar guards. Migration `026_agent_commands_and_pins`. Tests: `tests/test_agent_command_endpoints.py` (11) + `tests/test_agent_commands_client.py` (12).
5. **TLS pinning + key rotation (T6)** — Model `AgentServerPin` + endpoints `GET/PUT /api/agent/cert/pin` and `POST /api/agent/key/rotate`. Pin rotation deactivates the previous pin transactionally; key rotation returns the new key once with a configurable grace window. Tests: `tests/test_cert_pin_and_key_rotate.py` (10).
6. **NSIS Windows installer (T7)** — `agent/installer.nsi` + helper `scripts/build_agent_windows_installer.ps1`. CI workflow `.github/workflows/test.yml` builds the installer on Windows runners on `main` push and uploads the artifact.
7. **Production deploy guide + smoke tests (T8)** — `docs/PRODUCTION_DEPLOY.md` is the operator runbook (env vars, deploy steps, pin/key rotation, rollback). `tests/test_production_smoke.py` (9) asserts health probe, auth gating, migration presence, model importability, and Redis fallback wiring.

Total new tests: **58 passing in ~80 seconds**.
