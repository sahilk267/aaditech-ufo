# Staging Verification Checklist

Updated: March 31, 2026

## Purpose

Use this checklist before the first real staging deployment and before promoting a staging build toward production.

This file assumes the current deployment baseline already verified in the repo:

- compose config renders cleanly with `.env.prod`
- gateway config passes `nginx -t`
- SPA shell and asset cache behavior are regression-tested
- agent release upload/list/guide/download flow is regression-tested

---

## 1. Pre-Deploy Inputs

- [ ] Confirm the exact git commit or release tag to deploy.
- [ ] Confirm `.env.prod` exists outside the repo and is the file used with `--env-file`.
- [ ] Confirm real values are present for `DB_PASSWORD`, `REDIS_PASSWORD`, `SECRET_KEY`, and `JWT_SECRET_KEY`.
- [ ] Confirm staging URLs and DNS targets are known for app, gateway, and any external frontend-facing hostname if one exists.
- [ ] Confirm the target database is a staging database, not production.
- [ ] Confirm release artifacts needed for update-flow validation are available.

---

## 2. Config Render Checks

Run:

```bash
docker compose --env-file .env.prod -f docker-compose.yml -f docker-compose.prod.yml config
docker compose --env-file .env.prod --profile full -f docker-compose.yml -f docker-compose.prod.yml config
```

Verify:

- [ ] `DATABASE_URL` resolves to the intended staging database.
- [ ] `REDIS_URL` resolves to the intended staging Redis instance.
- [ ] gateway and app services render in the full profile, and any optional staging-only sidecars are expected.
- [ ] health checks, startup ordering, and mounted volumes render as expected.

---

## 3. Deploy And Bootstrap

Run the staging stack using the same compose inputs validated above.

Verify:

- [ ] app container starts without import-time bootstrap errors.
- [ ] migrations apply successfully during startup.
- [ ] gateway starts cleanly.
- [ ] frontend static files are available through the app/gateway-served `/app` path you expect.
- [ ] no service is crash-looping after initial startup.

---

## 4. Health And Routing Checks

Verify:

- [ ] `GET /gateway/health` returns `200`.
- [ ] `GET /health` returns `200` and includes `X-API-Gateway-Ready`.
- [ ] `GET /api/health` returns `200` through the deployed route.
- [ ] `GET /app` returns the SPA shell.
- [ ] hard refresh on a nested SPA route such as `/app/dashboard` or `/app/systems` returns the SPA shell instead of a 404.
- [ ] request IDs survive the gateway path if `X-Request-ID` is supplied.

---

## 5. Auth And Tenant Checks

Verify:

- [ ] browser login works for a staging tenant.
- [ ] JWT/API-key protected endpoints still work with `X-Tenant-Slug`.
- [ ] tenant-scoped pages and APIs return data for the authenticated tenant.
- [ ] logout and token/session expiry behavior look normal.

---

## 6. SPA Asset And Cache Checks

Verify:

- [ ] `index.html` responses under `/app` send `Cache-Control` with `no-cache` and `no-store`.
- [ ] hashed JS/CSS assets under `/app/assets/...` send long-lived public cache headers.
- [ ] missing asset paths return `404`.
- [ ] missing SPA-dist behavior is not occurring in staging.

---

## 7. Agent Release Flow Checks

Verify:

- [ ] upload a test agent release through `/api/agent/releases/upload` or the release UI.
- [ ] `GET /api/agent/releases` lists the uploaded version.
- [ ] `GET /api/agent/releases/guide?current_version=x.y.z` returns the expected recommendation.
- [ ] the generated download URL downloads the expected file with attachment headers.
- [ ] release files are written to the expected release storage directory.

---

## 8. Smoke Checks For Core Flows

Verify:

- [ ] one authenticated dashboard/API request succeeds.
- [ ] one alerting-related API call succeeds.
- [ ] one queue-backed or maintenance workflow path succeeds in the deployed environment.
- [ ] one audit-producing action appears in the audit trail or logs.

---

## 9. Logs And Evidence

- [ ] Save the exact compose command used for deployment.
- [ ] Save container logs from app, gateway, and frontend for the deploy window.
- [ ] Save screenshots or curl output for `/gateway/health`, `/health`, `/api/health`, and `/app`.
- [ ] Save the uploaded release version used for staging validation.
- [ ] Record any warnings that are acceptable versus blockers.

---

## 10. Exit Decision

Staging can be considered ready only when:

- [ ] all checks above pass without unexplained warnings
- [ ] no service is restart-looping
- [ ] migrations completed cleanly
- [ ] gateway and SPA routing are healthy
- [ ] release lifecycle validation succeeded
- [ ] rollback owner and rollback commands are known before promotion

If any item fails, stop promotion and document:

- failed step
- exact command or URL used
- observed output
- likely owner
- rollback or containment action taken
