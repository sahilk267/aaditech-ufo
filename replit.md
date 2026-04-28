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

The strict TypeScript check (`tsc -b`) currently fails due to legacy type drift in `src/lib/axios.ts` and `tsconfig.test.json`; using `npx vite build` bypasses the typecheck while still producing a working bundle.

### Deployment

Configured for **autoscale** deployment:

- **Build:** `pip install -r requirements.txt && cd frontend && npm install && npx vite build`
- **Run:** Apply migrations, then `gunicorn --bind=0.0.0.0:5000 --workers=2 --timeout=60 server.app:app`

## Local Fixes Applied During Import

1. **`migrations/env.py`** — Added explicit `connection.commit()` calls so Alembic migrations actually persist under SQLAlchemy 2.0 (the previous transactional-DDL block was being rolled back, leaving the schema empty).
2. **`frontend/src/pages/logs/LogsPage.tsx`** — Added a placeholder module page; the file was referenced by the SPA router but missing from the import, breaking the Vite build.

## Notes

- Redis is **not** provisioned by default. Celery and rate-limiting fall back to in-memory storage; the `/health` endpoint reports Redis as `disconnected`, which is expected in this environment.
- The SPA is served at `/app` and `/app/*`; the legacy server-rendered UI (login, dashboard, admin) is at `/`.
- The default tenant slug is `default`; tenants are auto-created on first request.
