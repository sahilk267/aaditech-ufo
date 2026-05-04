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

- **Server** — `cd frontend && npm install --silent && npx vite build 2>&1 | tail -3 && cd .. && python -m scripts.seed_default_admin 2>&1 | tail -4 && python -m server.app`
  - Flask binds `0.0.0.0:5000` and applies Alembic migrations on startup.
  - Serves API, Jinja templates, and the built SPA from `frontend/dist`.

### Database

PostgreSQL is provisioned via Replit's built-in database. The `DATABASE_URL` environment variable is automatically populated.

### Frontend Build

The React SPA is pre-built into `frontend/dist/` so Flask can serve it. To rebuild after frontend changes:

```bash
cd frontend && npx vite build
```

### Deployment

Configured for **autoscale** deployment:

- **Build:** `pip install -r requirements.txt && cd frontend && npm install && npx vite build`
- **Run:** Apply migrations, then `gunicorn --bind=0.0.0.0:5000 --workers=2 --timeout=60 server.app:app`

## Local Fixes Applied During Import

1. **`migrations/env.py`** — Added explicit `connection.commit()` calls so Alembic migrations actually persist under SQLAlchemy 2.0.
2. **`frontend/src/pages/logs/LogsPage.tsx`** — Rebuilt as full feature page (was placeholder).

## Default Admin Seed

Run `python -m scripts.seed_default_admin` to (re)create a default admin in the `default` tenant.

Default credentials (override with CLI flags or `SEED_ADMIN_*` env vars):

- Tenant Slug: `default`
- Email: `admin@example.com`
- Password: `ChangeMe123!`

The script is idempotent: it will reuse the existing tenant/role and reset the user's password if the user already exists. The user is granted the built-in `admin` role with `tenant.manage`, `dashboard.view`, `system.submit`, `backup.manage`, and `automation.manage` permissions.

## Added in this session

- **Remote Commands SPA page** (`/app/agent-commands`, requires `automation.manage`) — queue whitelisted commands, filter by status / type / target serial, auto-refresh every 5s. Backed by new admin endpoint `GET /api/agent/commands` (read-only list, no side-effects).
- **Self-service Change Password** — modal accessible from the topbar in every authenticated SPA page. Backed by new endpoint `POST /api/auth/change-password` which requires `current_password`, validates the new password against the tenant's auth policy, bumps `auth_token_version` (revoking other sessions), and returns a fresh token pair.

## Agent Engine (Modular AI Automation System)

A production-grade, multi-component AI orchestration system mounted at `/api/agent_engine` (backend) and `/app/agent-engine` (frontend SPA page).

### Architecture

```
Orchestrator  ←→  Planner  ←→  Executor  ←→  Tool Layer
     ↓                               ↓
ShortTermMemory                 AgentSession (DB)
```

- **`server/agent_engine/orchestrator.py`** — Top-level lifecycle: create DB session, invoke planner, dispatch executor, persist result, compute duration.
- **`server/agent_engine/planner.py`** — Two-stage planner: AI JSON plan via `AIService` first; rule-based keyword fallback if AI fails. Produces `Step` dataclass list.
- **`server/agent_engine/executor.py`** — Topological sort (`depends_on`), retry with exponential back-off (0.3s / 0.6s / 1.2s), never raises — errors are captured in step outputs.
- **`server/agent_engine/memory.py`** — `ShortTermMemory` dict shared across all steps in a run; allows downstream steps to read upstream results.
- **`server/agent_engine/tools/`** — Six registered tools: `system_query`, `automation_trigger`, `ai_analysis`, `alert_check`, `log_search`, `remote_exec`.
- **`server/agent_engine/blueprint.py`** — Flask blueprint (`/api/agent_engine`): `POST /run`, `GET /sessions`, `GET /sessions/<id>`, `GET /tools`.
- **`server/orchestrator_factory.py`** — `build_runtime_config()` helper that merges `app.config` with per-call overrides.
- **`server/models.py` → `AgentSession`** — Persists every run: `session_id`, `status`, `plan_steps`, `step_outputs`, `final_result`, `duration_ms`.
- **Migration** — `migrations/versions/027_agent_sessions.py`.

### ai_analysis Tool — Supported Modes

The `ai_analysis` tool (`server/agent_engine/tools/ai_analysis.py`) supports five modes:

| Mode | Method called | Memory key set |
|---|---|---|
| `root_cause` | `AIService.analyze_root_cause` | `ai_root_cause` |
| `recommendations` | `AIService.generate_recommendations` | `ai_recommendations` |
| `troubleshoot` | `AIService.assist_troubleshooting` | `ai_guidance` |
| `anomaly` | `AIService.analyze_anomalies` | `ai_anomaly_analysis` |
| `incident` | `AIService.explain_incident` | `ai_incident_explanation` |

`anomaly` mode builds an anomaly list from upstream evidence when none is supplied. `incident` mode accepts `incident_title`, `affected_systems`, and `metrics_snapshot` params.

### Frontend

- **`frontend/src/pages/agent-engine/AgentEnginePage.tsx`** — Full SPA page: run panel with dry-run toggle, plan viewer, step results table with JSON drill-down, session history, tool registry. `statusBadge` correctly maps `failed` → `"error"` (valid `StatCard` status).
- Route: `/app/agent-engine` (requires `automation.manage` permission).
- Navigation entry: "Agent Engine" in the "Automation & AI" section.

### Config knobs (env vars)

| Variable | Default | Purpose |
|---|---|---|
| `AGENT_ENGINE_ENABLED` | `True` | Master feature flag |
| `AGENT_ENGINE_MAX_STEPS` | `10` | Cap on planner output steps |
| `AGENT_ENGINE_MAX_RETRIES` | `2` | Per-step retry limit |
| `AGENT_ENGINE_STEP_TIMEOUT_SECONDS` | `30` | Per-step wall-clock timeout |

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

## Full Diagnostic Refactor (2026-05-04)

All items from the "COMPLETE DIAGNOSTIC REPORT" have been implemented end-to-end:

### Backend

- **`server/agent_engine/tools/ai_analysis.py`** — Added `anomaly` and `incident` modes to `_VALID_MODES`. Implemented `_anomaly()` (calls `AIService.analyze_anomalies`, builds anomaly list from upstream evidence if none supplied, sets `ai_anomaly_analysis` in memory) and `_incident()` (calls `AIService.explain_incident` with `incident_title`, `affected_systems`, `metrics_snapshot`, sets `ai_incident_explanation` in memory).

### Frontend — Component Fixes

- **`StatCard`** — Added `trend` (`"up" | "down" | "flat"`) and `trendLabel` props; renders a color-coded arrow glyph next to the value. Status type now explicitly typed as `"ok" | "warn" | "error" | "neutral"` (removed invalid `"critical"` usage).
- **`ErrorBoundary`** — New class component (`frontend/src/components/common/ErrorBoundary.tsx`). Shows the error message, component stack, "Try again" and "Reload page" buttons. Wraps the entire `<App>` in `App.tsx`.
- **`AgentEnginePage`** — Fixed `statusBadge()` to return `"error"` instead of invalid `"critical"` for failed sessions.

### Frontend — Navigation

- **`frontend/src/config/navigation.ts`** — Refactored from flat `NAV_ITEMS` array into `NAV_SECTIONS` (5 labelled groups: Monitoring, Automation & AI, Logs & Reliability, Operations, Admin). `NAV_ITEMS` remains exported as `NAV_SECTIONS.flatMap(s => s.items)` for backward compatibility.
- **`frontend/src/components/layout/AppShell.tsx`** — Updated to render section headers (`.nav-section-label`) between nav groups. Sections with zero visible items are hidden.
- **`frontend/src/index.css`** — Added `.nav-section` and `.nav-section-label` styles.

### Frontend — Dashboard

- **`DashboardPage`** — Chart data now built dynamically from `systemsQuery.data.systems`. Each system becomes a data point with `time = hostname`, `health = 100 - cpu_usage × 0.6` (capped 0–100, drops to 40 for inactive systems), `load = cpu_usage`. Falls back to `[{ time: "No data", health: 0, load: 0 }]` when no systems are enrolled.

### Frontend — Login

- **`LoginPage`** — Removed hardcoded dev credentials (`default` / `admin@example.com` / `ChangeMe123!`) from initial state. All fields now start empty.

### Frontend — Logs Page

- **`LogsPage`** — Fully rebuilt from placeholder. Features: log source table (click to filter entries, "Use in search" button), log search panel (source name + query, keyboard-submit, Ingest button), log entries table (severity badge, event ID, message truncation), log investigations panel (create with Enter key, investigation table). Uses `getLogSources`, `getLogEntries`, `getLogInvestigations`, `createLogInvestigation`, `searchLogs`, `ingestLogs` from `api.ts`.

### Frontend — Automation Page

- **`AutomationPage`** — Added **Dependencies** and **Failures** action buttons alongside "Check Status". Backed by new mutations `serviceDependenciesMutation` → `getAutomationServiceDependencies` and `serviceFailuresMutation` → `getAutomationServiceFailures`. Results shown in the existing `latestResult` JSON viewer.

### Frontend — Backup Page

- **`BackupPage`** — Added **Verify** button per backup row. Calls `verifyBackup(filename)` → `POST /api/backups/<filename>/verify`. Result shown in the `latestResult` panel. Also added a **Select** button to each row (replaces the dropdown-only UX).

### Frontend — Users Page

- **`UsersPage`** — Added **Revoke sessions** button per user row. Calls `revokeUserSessions(userId)` → `POST /api/users/<id>/revoke-sessions`. Styled in amber to signal a destructive-ish action.

### Frontend — API Layer

- **`frontend/src/lib/api.ts`** — Complete rewrite to deduplicate imports and add all missing wrappers:
  - `revokeUserSessions(userId)` → `POST /api/users/<id>/revoke-sessions`
  - `getRoles()` → `GET /api/roles`
  - `getPermissions()` → `GET /api/permissions`
  - `getAutomationServiceDependencies(serviceName, runtimeConfig?)` → `POST /api/automation/services/dependencies`
  - `getAutomationServiceFailures(serviceName, runtimeConfig?)` → `POST /api/automation/services/failures`
  - `executeServiceCommand(serviceName, commandText, runtimeConfig?)` → `POST /api/automation/services/execute`
  - `verifyBackup(filename)` → `POST /api/backups/<filename>/verify`
  - `updateAlertRule(ruleId, payload)` → `PATCH /api/alerts/rules/<id>`
  - `deleteAlertSilence(silenceId)` → `DELETE /api/alerts/silences/<id>`
  - `getSupportabilityPolicy()` → `GET /api/supportability/policy`
  - `getSupportabilityMetrics()` → `GET /api/supportability/metrics`
  - `updateLogSource(sourceId, payload)` → `PATCH /api/logs/sources/<id>`
  - `getLogEntries` updated to accept both `sourceId` and `source_id` param aliases
