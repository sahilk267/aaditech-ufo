# Backend Startup Runbook

Updated: March 27, 2026

## Purpose

This is the short source of truth for backend startup in local, dev, and test workflows.

Use this file when you need to:

- boot the Flask backend locally
- run migrations safely
- understand test-mode queue behavior
- validate the backend after startup changes

---

## Local Python Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Minimum variables to review in `.env`:

- `SECRET_KEY`
- `AGENT_API_KEY`
- `JWT_SECRET_KEY`
- `DATABASE_URL`
- `REDIS_URL`

If you want non-dry-run automation actions:

- `AUTOMATION_ALLOWED_SERVICES` for `service_restart`
- `AUTOMATION_ALLOWED_SCRIPT_ROOTS` and optional `AUTOMATION_SCRIPT_EXECUTOR_ADAPTER` for `script_execute`
- `AUTOMATION_ALLOWED_WEBHOOK_HOSTS` and optional `AUTOMATION_WEBHOOK_ADAPTER` for `webhook_call`

If you want live Ollama-backed AI behavior instead of the deterministic test double:

- `OLLAMA_ADAPTER=ollama_http`
- `OLLAMA_ENDPOINT`
- `OLLAMA_ALLOWED_HOSTS` to restrict which Ollama hosts are allowed
- optional `OLLAMA_HTTP_FALLBACK_TO_TEST_DOUBLE=true` only if you explicitly want safe degraded fallback on upstream HTTP failure

---

## Local Backend Start

Preferred local backend flow:

```bash
flask --app server.app db upgrade
flask --app server.app run --host 0.0.0.0 --port 5000
```

Notes:

- `server.app` now uses `create_app()`.
- Schema creation should happen through Alembic migrations, not `db.create_all()`.
- Running `python server/app.py` also applies migrations before starting, but the `flask --app server.app ...` flow is the clearest day-to-day path.

Quick verification:

```bash
curl http://127.0.0.1:5000/health
```

Expected result:

- HTTP `200`
- JSON includes `status=healthy`
- response headers include `X-API-Gateway-Ready`

---

## Docker Dev Start

Validate compose first:

```bash
docker compose -f docker-compose.yml config
docker compose --profile full -f docker-compose.yml -f docker-compose.dev.yml config
```

Start the dev stack:

```bash
docker compose --profile full -f docker-compose.yml -f docker-compose.dev.yml up --build
```

Container startup notes:

- `entrypoint.sh` runs `flask --app server.app db upgrade` before app startup.
- Production-like compose flows still require real secret values.

---

## Production Compose Verification

Use `.env.prod` for compose-file interpolation and supply non-placeholder secrets at runtime.

Validation commands:

```bash
docker compose --env-file .env.prod -f docker-compose.yml -f docker-compose.prod.yml config
docker compose --env-file .env.prod --profile full -f docker-compose.yml -f docker-compose.prod.yml config
```

Required secret values to supply outside the repo:

- `DB_PASSWORD`
- `REDIS_PASSWORD`
- `SECRET_KEY`
- `JWT_SECRET_KEY`

What this verification confirms:

- production database and Redis credentials resolve into container config
- app `DATABASE_URL` and `REDIS_URL` resolve correctly
- Redis health checks authenticate with the same passworded URL the app uses
- health checks, startup order, volumes, and gateway/app service wiring render cleanly
- the deployed SPA is expected to be served by the app/gateway path, not a separate production frontend container

For the first real deployment pass, use `STAGING_VERIFICATION_CHECKLIST.md` after compose validation succeeds.

Important note:

- `env_file:` inside the compose service does not replace `--env-file` for compose interpolation
- if you skip `--env-file .env.prod`, `DB_USER` and `DB_NAME` can silently fall back to defaults

---

## Test Startup Behavior

Pytest uses `create_app(TestConfig)` from `tests/conftest.py`.

Important test-mode behavior:

- each test gets its own temporary SQLite database
- tables are created inside the test fixture
- queue jobs run inline in testing mode
- limiter is explicitly disabled for tests

This means tests do not require a running Redis or Celery worker.

Run core backend regression slices:

```bash
python -m pytest tests/test_app_bootstrap.py -q
python -m pytest tests/test_api_endpoints.py tests/test_alerting_api.py tests/test_async_maintenance_jobs.py -q
python -m pytest tests/test_alert_notifications.py -q
python -m pytest tests/test_tenant_admin_api.py tests/test_tenant_context.py tests/test_web_session_auth.py -q
```

Run broader backend coverage used during stabilization:

```bash
python -m pytest tests/test_alert_suppression_pattern_ai_anomaly.py tests/test_phase2_remaining_features.py -q
```

---

## Migration Workflow

When models change:

```bash
flask --app server.app db migrate -m "describe change"
flask --app server.app db upgrade
```

Rules:

- every schema change must have a migration
- do not rely on runtime table creation for new models
- validate migrations against a fresh database when startup behavior changes

---

## Troubleshooting

If startup fails:

1. Check `.env` values, especially `DATABASE_URL`, `SECRET_KEY`, and `JWT_SECRET_KEY`.
2. Run `flask --app server.app db upgrade` manually and inspect the traceback.
3. Verify compose config with `docker compose ... config` before blaming runtime.
4. Run `python -m pytest tests/test_app_bootstrap.py -q` to confirm factory/bootstrap wiring.

If tests fail with DB-session errors:

1. Confirm the failing path rolled back the SQLAlchemy session.
2. Re-run the focused suite before running a broader slice.
3. Check whether a new model change is missing a migration.
