# Frontend Phase 5 Cutover Playbook

Updated: March 25, 2026

## 1. Goal

Cut browser operators over from legacy Jinja pages to the SPA under `/app` with a staged rollback-safe sequence.

This playbook assumes:
- backend API routes remain the system of record
- JWT-based SPA auth remains active
- legacy Jinja pages stay available until redirect validation is complete

## 1.1 Finalized Cutover Decisions

- Browser auth remains dual-mode for Phase 5 execution: SPA JWT auth is the primary path for `/app`, while legacy browser-session auth remains in place for compatibility pages that still serve HTML routes.
- `/admin` and `/features` remain compatibility pages for the current cutover window rather than redirect targets.
- `/login` and `/logout` remain available as session-auth endpoints until the legacy compatibility pages are formally retired.

## 2. Preconditions

The cutover should not begin until all of the following are true:

- frontend production build is green
- frontend test suite is green
- tenant-scoped auth and RBAC checks are verified against `/api/auth/*`
- route-level SPA parity is complete for dashboard, systems, history, backup, releases, and control-panel release build/download flows
- operator-facing regression check is completed for login, dashboard, systems, history, backup, releases, and admin-critical workflows

## 3. Route Decision Matrix

| Legacy Route | Current Owner | Phase 5 Action | Target | Notes |
| --- | --- | --- | --- | --- |
| `/login` | Jinja + web session | Keep as compatibility route | n/a | Dual-mode auth is the Phase 5 decision: SPA login for `/app`, session login for remaining compatibility pages. |
| `/logout` | Jinja + web session | Keep as compatibility route | n/a | Must remain while `/login`, `/admin`, and `/features` still use legacy session access. |
| `/` | Jinja dashboard | Redirect in wave 1 | `/app/dashboard` | Lowest-risk redirect once smoke checks pass. |
| `/user` | Jinja system detail | Redirect in wave 1 | `/app/systems` | Safe because SPA systems page auto-selects a system. |
| `/user/<serial_number>` | Jinja system detail | Redirect in wave 1 | `/app/systems?serial=<serial_number>` | SPA now supports serial-based deep-link selection. |
| `/history` | Jinja history | Redirect in wave 1 | `/app/history` | Parity complete. |
| `/backup` | Jinja backup | Redirect in wave 1 | `/app/backup` | Parity complete. |
| `/agent/releases` | Jinja release portal | Redirect in wave 2 | `/app/releases` | Keep one rollout wave later because release downloads and build operations are high-impact admin workflows. |
| `/admin` | Jinja admin panel | Keep as compatibility page | n/a | Current SPA coverage is distributed across several routes; retain as compatibility surface instead of forcing a fragmented redirect. |
| `/features` | Jinja feature hub | Keep as compatibility page | n/a | Retain as transitional discovery/fallback page for the same reason as `/admin`. |

## 4. Recommended Rollout Sequence

### Wave 0: Readiness

- confirm production asset deployment under `/app`
- confirm reverse proxy and Flask static handling serve SPA shell correctly on hard refreshes under `/app/*`
- confirm auth refresh and tenant header propagation in production-like environment
- confirm audit logging remains intact for login/logout/admin-sensitive operations

### Wave 1: Low-risk Redirects

Introduce redirects for:
- `/`
- `/user`
- `/user/<serial_number>`
- `/history`
- `/backup`

Validation window:
- monitor 24-48 hours
- confirm no increase in 4xx/5xx rates on redirected entry routes
- confirm operators can still complete dashboard, system detail, history, and backup workflows without falling back to legacy pages

### Wave 2: Release Workflow Redirect

Introduce redirect for:
- `/agent/releases`

Validation window:
- monitor build trigger success rate
- monitor binary download success rate
- verify policy update, guide lookup, and upload behavior across tenant roles

### Wave 3: Compatibility Page Review

Keep `/admin` and `/features` active as compatibility pages through the initial cutover and stabilization window.

Revisit replacement only after:
- tenant-management workflow sign-off is complete
- distributed admin workflow routing is documented for operators
- support volume shows the compatibility pages are no longer needed

## 5. Rollback Triggers

Rollback the most recent redirect wave if any of the following occur:

- critical auth regression on browser login, refresh, or logout
- tenant context mismatch on redirected SPA routes
- operator inability to access system detail deep links from legacy bookmarks
- release upload/build/download failures after `/agent/releases` redirect
- repeated 5xx responses or clear increase in support incidents tied to redirected routes

## 6. Rollback Procedure

1. Disable only the latest redirect wave.
2. Keep `/app` deployed and available for continued validation.
3. Re-verify legacy Jinja route behavior on affected endpoints.
4. Capture failing SPA route, tenant, permission set, and API response details.
5. Fix the specific parity or routing defect before reattempting the wave.

Target rollback time: 15 minutes or less for any single redirect wave.

## 7. Operational Checks During Cutover

- browser entry to redirected route lands on correct `/app/*` target
- hard refresh on redirected SPA route succeeds
- RBAC-restricted users see expected denied or hidden states without server-side authorization regressions
- legacy bookmarks to `/user/<serial_number>` resolve to the correct selected system in SPA
- release downloads still return the expected binary artifact
- audit events remain visible for security-sensitive actions

## 8. Follow-up Decisions

These items remain for later cleanup, not for initial cutover blocking:

- when to retire legacy session auth after compatibility pages are removed
- whether `/admin` and `/features` eventually become SPA informational landing pages instead of full HTML fallbacks
- how long compatibility routes remain available during post-cutover stabilization