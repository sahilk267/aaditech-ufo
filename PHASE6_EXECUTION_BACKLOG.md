# Phase 6 Execution Backlog

Updated: April 2, 2026

## Purpose

Turn the post-rebaseline state into a practical next-cycle execution backlog.

This backlog is derived from:

- `FULL_REPO_REBASELINE_REPORT_2026_04_01.md`
- `REALTIME_TRANSPORT_DECISION.md`
- `ENTERPRISE_AUTH_ROADMAP_DECISION.md`
- `COMMERCIAL_PLATFORM_ROADMAP_DECISION.md`

---

## Backlog Rules

- `P0` means highest leverage and best fit for the current repo state.
- `P1` means important product-depth work after `P0` starts landing.
- `P2` means strategically important but can wait until earlier slices stabilize.
- Every execution slice should include code, tests, and doc updates together.

---

## Recommended Execution Order

1. P0-A: Entitlements and feature flags foundation
2. P0-B: Realtime SSE v1 for alerts/logs/timeline
3. P0-C: Enterprise auth v1 local hardening
4. P1-A: Logs investigation productization
5. P1-B: Reliability operator history/productization
6. P1-C: Updates productization

---

## P0

### P0-A: Tenant Entitlements And Feature Flags Foundation

Goal:

Create the minimum commercial/platform control layer before quotas or billing.

Deliverables:

- `TenantPlan` / `TenantEntitlement` / `TenantFeatureFlag` durable models
- tenant-scoped read/update APIs for entitlements and feature flags
- backend guard helpers for entitlement/flag checks
- one or two frontend operator surfaces for viewing effective tenant controls
- audit events for entitlement or flag changes

Primary files:

- `server/models.py`
- `server/blueprints/api.py`
- `server/auth.py`
- `frontend/src/lib/api.ts`
- `frontend/src/pages/tenants/`
- `migrations/versions/`

Validation target:

- dedicated entitlement API tests
- one frontend contract/build validation pass
- fresh migration upgrade validation

Why first:

- commercial roadmap says feature boundaries should exist before quotas/billing
- this also creates a safe mechanism for rollout gating across future features

---

### P0-B: Realtime SSE V1

Goal:

Add selective live-feed support without moving to full WebSocket complexity.

Deliverables:

- SSE endpoint for alerts feed
- SSE endpoint for operations timeline feed
- optional SSE endpoint for logs feed
- frontend consumers for at least alerts + timeline
- reconnect/fallback behavior to existing polling
- auth and tenant-scope rules for SSE endpoints

Primary files:

- `server/blueprints/api.py`
- `frontend/src/lib/api.ts`
- `frontend/src/pages/alerts/AlertsPage.tsx`
- `frontend/src/pages/audit/AuditPage.tsx`
- `REALTIME_TRANSPORT_DECISION.md`

Validation target:

- API tests for event-stream response shape and tenant isolation
- frontend build validation
- deployment-note update if proxy config needs SSE headers/buffering rules

Why now:

- Phase 5 already chose polling + selective SSE
- alerts/logs/timeline are the clearest high-value live surfaces

Status:

- Completed on April 2, 2026
- `GET /api/alerts/stream` and `GET /api/operations/timeline/stream` landed
- Alerts and Audit SPA pages now consume same-origin SSE with fallback to existing polling/query cache
- Gateway config now disables proxy buffering for the SSE routes
- Validation passed through targeted pytest, frontend build, fresh migration upgrade, and `nginx -t`

---

### P0-C: Enterprise Auth V1 Local Hardening

Goal:

Implement the first stage of the auth roadmap before external IdP work.

Deliverables:

- stronger session policy fields in tenant settings
- optional TOTP MFA model + API flow
- password/lockout policy baseline
- session invalidation/admin revoke flow
- auth docs updated with current stage and guardrails

Primary files:

- `server/models.py`
- `server/blueprints/api.py`
- `server/auth.py`
- `server/tenant_context.py`
- `frontend/src/pages/tenants/`
- `ENTERPRISE_AUTH_ROADMAP_DECISION.md`

Validation target:

- auth regression tests
- tenant-settings contract tests
- fresh migration upgrade validation

Why now:

- enterprise auth roadmap explicitly starts with local hardening
- this improves security without needing full OIDC/SAML yet

Status:

- `P0-C1` started and completed on April 2, 2026
- tenant auth-policy defaults and bounded validation now exist on `tenant-settings`
- password policy enforcement now applies during registration
- tenant-scoped login lockout baseline now applies to API and browser login
- admin session invalidation now exists through user session revocation
- JWT and browser sessions now respect auth token version revocation
- `P0-C2` also completed on April 2, 2026 with optional TOTP MFA enrollment/activation/disable APIs, MFA login challenge verification, and a tenant/admin visibility surface in the SPA
- Revalidated on April 7, 2026 with targeted MFA/auth regression tests and a fresh frontend production build

---

## P1

### P1-A: Logs Investigation Productization

Goal:

Move logs from durable storage to stronger operator workflows.

Deliverables:

- source configuration metadata improvements
- richer log search/filter/detail APIs
- saved query or investigation context if useful
- frontend logs page improvements for stored history and drill-down

Primary files:

- `server/services/log_service.py`
- `server/blueprints/api.py`
- `frontend/src/pages/logs/LogsPage.tsx`
- `FEATURE_ACCEPTANCE_CRITERIA.md`

Status:

- Completed on April 7, 2026
- Added log-source investigation metadata (`description`, `host_name`, `is_active`, `source_metadata`) with migration `018_logs_investigation_productization`
- Added `GET /api/logs/sources`, `GET/PATCH /api/logs/sources/<id>`, `GET /api/logs/entries`, and `GET /api/logs/entries/<id>` for stored-history investigation workflows
- Upgraded the SPA Logs page from a single latest-response panel to persisted source selection, metadata editing, stored-entry filtering, and drill-down detail views
- Validation passed through dedicated logs-investigation pytest coverage, existing logs operational-flow coverage, frontend build, and fresh migration upgrade

---

### P1-B: Reliability Operator Productization

Goal:

Give reliability a clearer operator-facing lifecycle and history surface.

Deliverables:

- durable reliability run/history storage where needed
- clearer reliability detail/read APIs
- frontend reliability page improvements beyond raw action responses

Primary files:

- `server/services/reliability_service.py`
- `server/models.py`
- `server/blueprints/api.py`
- `frontend/src/pages/reliability/ReliabilityPage.tsx`

Status:

- Completed on April 8, 2026
- Added durable `ReliabilityRun` history with migration `019_reliability_runs`
- Added `GET /api/reliability/runs` and `GET /api/reliability/runs/<id>` for operator history/detail workflows
- Persisted reliability history, score, trend, prediction, pattern, crash-dump parse, exception, and stack-trace executions into tenant-scoped run history
- Upgraded the SPA Reliability page from a latest-response panel into an operator workflow with run stats, persisted history filters, crash-dump actions, and selected-run drill-down
- Validation passed through dedicated reliability-operator pytest coverage, existing reliability API coverage, frontend build, and fresh migration upgrade

---

### P1-C: Updates Productization

Goal:

Move updates from foundation-level monitoring to a stronger operational product slice.

Deliverables:

- update history persistence if needed
- richer update read APIs
- frontend update state/history surface
- acceptance-criteria refresh

Primary files:

- `server/services/update_service.py`
- `server/models.py`
- `server/blueprints/api.py`
- `frontend/src/pages/updates/UpdatesPage.tsx`

Status:

- Completed on April 8, 2026
- Added durable `UpdateRun` history with migration `020_update_runs`
- Added `GET /api/updates/runs` and `GET /api/updates/runs/<id>` for operator history/detail workflows
- Update monitoring now persists tenant-scoped update snapshots, and confidence scoring can attach analysis to a selected update run
- Upgraded the SPA Updates page from a single latest-response panel into a monitor-plus-history workflow with persisted run selection and confidence drill-down
- Validation passed through dedicated updates-productization pytest coverage, existing update/confidence API coverage, frontend build, and fresh migration upgrade

---

## P2

### P2-A: OIDC Foundation

Goal:

Start Stage 2 of the enterprise auth roadmap after local hardening stabilizes.

Deliverables:

- OIDC provider config model
- tenant-scoped OIDC settings
- login/callback flow
- claim mapping into RBAC

Status:

- Completed on April 9, 2026
- Existing `TenantOidcProvider` model/migration is now wired into working tenant-admin APIs: `GET /api/auth/oidc/providers`, `POST /api/auth/oidc/providers`, and `PATCH /api/auth/oidc/providers/<id>`
- Tenant auth policy now supports bounded `oidc_enabled` and `local_admin_fallback_enabled` settings on `tenant-settings`
- OIDC foundation login now exists through `POST /api/auth/oidc/login` plus `GET /api/auth/oidc/callback`
- Test-mode providers support deterministic callback completion without external network dependencies, which lets the repo validate the full flow end-to-end
- Claim mappings now map OIDC claims into tenant user creation/update and RBAC role assignment, with default-admin fallback when no explicit role map matches
- Tenant secrets are now used for OIDC client secret storage instead of exposing raw client secrets
- The SPA Tenants page now exposes basic OIDC admin visibility and test-provider creation/toggle controls
- Validation passed through dedicated OIDC pytest coverage, existing auth/MFA regression suites, frontend build, and a fresh migration upgrade

---

### P2-B: Quotas And Usage Metrics

Goal:

Add measurable tenant usage and enforceable quota boundaries.

Deliverables:

- usage metric model(s)
- quota policy model(s)
- enforcement hooks for key resource domains
- operator/admin visibility

Status:

- Completed on April 9, 2026
- Added durable `TenantQuotaPolicy` and `TenantUsageMetric` models with migration `022_tenant_quotas_and_usage_metrics`
- Added `GET /api/tenant-quotas`, `PATCH /api/tenant-quotas`, and `GET /api/tenant-usage` for tenant-admin quota and usage visibility
- Added current usage snapshot syncing for `monitored_systems`, `automation_workflows`, `tenant_secrets`, and `enrolled_agents`
- Added real quota enforcement for new monitored-system submissions, tenant secret creation, and automation workflow creation
- Extended the SPA Tenants page with quota usage visibility and basic enforce/clear admin controls
- Validation passed through dedicated quota/usage pytest coverage, existing tenant-controls and affected API suites, frontend build, and a fresh migration upgrade

---

### P2-C: Billing / Licensing Preparation

Goal:

Prepare the repo for later commercial integration without overcommitting early.

Deliverables:

- billing/license domain draft models
- contract boundaries for entitlement versus billing
- docs and acceptance criteria updates

Status:

- Completed on April 9, 2026
- Added durable draft commercial models: `TenantPlan`, `TenantBillingProfile`, and `TenantLicense` with migration `023_tenant_commercial_models`
- Added `GET /api/tenant-commercial` and `PATCH /api/tenant-commercial` for tenant-admin plan, billing-profile, and license draft visibility
- Added explicit contract-boundary serialization so entitlements, quotas, billing profile, and license state are exposed as separate sources of truth
- Extended the SPA Tenants page with a commercial draft admin section for plan, provider, billing email, and license draft metadata
- Validation passed through dedicated commercial-preparation pytest coverage, related quota/control regressions, frontend build, and a fresh migration upgrade

---

## Suggested First Working Slice

Start with:

### `P0-A1: Tenant Feature Flags And Entitlements V1`

Definition:

- add minimal `TenantFeatureFlag` and `TenantEntitlement`
- expose tenant-scoped read/update API
- use one real flag in frontend/backend flow
- add audit coverage and migration validation

Why this slice:

- smallest high-leverage entry into the commercial/platform roadmap
- helps future SSE/auth/features roll out safely
- low coordination risk compared with starting OIDC or SSE first

Status:

- Completed on April 2, 2026
- Durable `TenantEntitlement` and `TenantFeatureFlag` models landed
- `GET/PATCH /api/tenant-controls` landed
- Real backend/frontend gating now exists for `incident_case_management_v1`
- Validation passed through targeted pytest, frontend build, and fresh migration upgrade

Next recommended slice:

- Full repo rebaseline / next-cycle backlog refresh

---

## Exit Criteria For Phase 6 Start

Phase 6 should be considered underway once:

- one `P0` slice is implemented and validated
- tracker and plan move from "Phase 5 complete" to "Phase 6 active"
- the chosen slice has a dedicated acceptance target and regression coverage
