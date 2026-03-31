# Aaditech UFO Frontend

This frontend is the React + TypeScript + Vite single-page application served under `/app/`.

It is the active replacement path for the legacy Flask-rendered operational pages and currently covers:

- authentication and session bootstrap
- dashboard and systems inventory
- tenants and users
- alerts and automation
- logs, reliability, AI, updates, and remote execution
- platform maintenance
- backup and agent releases
- audit activity review

## Local Development

Requirements:

- Node.js 20.20.1 or newer
- npm

Install dependencies:

```powershell
npm install
```

Start the Vite dev server:

```powershell
npm run dev
```

Build for production:

```powershell
npm run build
```

Run the frontend test suite:

```powershell
npx.cmd vitest run --pool threads --maxWorkers 1
```

## Runtime Notes

- The production build is emitted to `frontend/dist`.
- Vite is configured with `base: "/app/"`, so deployed assets and router paths assume the SPA is mounted under `/app`.
- In local development, Vite proxies `/api`, `/health`, `/manual_submit`, `/agent`, and `/features` to the Flask backend.
- In deployment mode, Flask/Nginx serve the built SPA and preserve hard-refresh behavior for `/app/*`.

## Auth, Tenant, and Permissions

- The SPA uses the backend auth APIs at `/api/auth/login`, `/api/auth/me`, `/api/auth/logout`, and `/api/auth/refresh`.
- Tenant context is propagated through the same backend auth/session model used by the Flask app.
- Route guards and navigation permissions share one source of truth in `src/config/routePermissions.ts`.
- Current route permission alignment is validated in `src/config/__tests__/routePermissions.test.ts`.

## Important Files

- `src/app/router.tsx`: route definitions and guarded module loading
- `src/config/navigation.ts`: navigation model
- `src/config/routePermissions.ts`: route-to-permission mapping
- `src/lib/api.ts`: SPA-to-backend API calls
- `src/lib/schemas.ts`: form validation schemas
- `src/pages/`: operational modules

## Current Validation Baseline

As of March 31, 2026:

- Vitest: `5 files, 85 tests passed`
- Production build: passing
- Live backend contract sweep: passing via `tests/test_frontend_page_api_contracts.py`
- Joined operational-flow validation: passing via `tests/test_frontend_operational_flows.py`

## Deployment Context

- The SPA rollout is controlled with the backend deployment flow documented in `BACKEND_STARTUP_RUNBOOK.md`.
- First real deployment checks live in `STAGING_VERIFICATION_CHECKLIST.md`.
- Redirect rollback steps for wave activation live in `SPA_WAVE_ROLLBACK_CHECKLIST.md`.

## Related Docs

- `../FRONTEND_PHASE_1_TO_5_TRACKING.md`
- `../FRONTEND_VITE_SPA_IMPLEMENTATION_PLAN.md`
- `../CURRENT_PHASE_WISE_PROGRESS_PLAN.md`
- `../PROGRESS_TRACKER.md`
