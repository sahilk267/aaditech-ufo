# AADITECH UFO - CURRENT PHASE-WISE PROGRESS PLAN

Updated: March 26, 2026

## Purpose

This file is the current execution checklist for the project based on the actual repository state.

Use this file to decide:

- what to do first
- what is blocked
- what is incomplete
- what must be verified before moving ahead

This plan is intentionally practical. It prioritizes stabilization before expansion.

---

## How To Use This File

Daily workflow:

1. Start from the current active phase.
2. Pick unchecked items from the current phase only.
3. Complete code + test + doc update together.
4. Check the item only after validation is done.
5. Move to the next phase only when exit criteria are met.

Rules:

- Do not start new major features while Phase 0 is open.
- Do not mark a feature complete if it is only a stub, adapter, or test-double path.
- Update this file, `PROGRESS_TRACKER.md`, and any feature-specific tracking file after each milestone.

---

## Shared Status Vocabulary

Use these labels consistently across planning and tracking files:

- `IMPLEMENTED`: End-to-end behavior exists in the repo and is validated enough to use for its intended flow.
- `FOUNDATION IMPLEMENTED`: Boundary, adapter, schema, or API scaffolding exists, but the feature is not yet product-complete.
- `PARTIAL`: Some real user-facing behavior exists, but important capability, polish, or validation is still missing.
- `PLANNED`: Intended work is known, but the feature is not yet implemented in a meaningful way.
- `NOT IMPLEMENTED`: No meaningful implementation exists yet.

Rule of thumb:

- Do not label adapter-only, test-double-only, or placeholder behavior as `IMPLEMENTED`.
- Prefer `FOUNDATION IMPLEMENTED` when the repo has safe boundaries and tests, but not full product behavior.

---

## Executive Status

Current reality from repo audit:

- Backend has substantial implementation, but startup/test architecture needs stabilization.
- Frontend SPA is mostly present, but route/module completeness and deploy validation still need work.
- Documentation is rich but not fully aligned with actual code status.
- Several features are foundation-level, not end-to-end production-complete.

Recommended active phase:

- Phase 0: Stabilization and truth-alignment

---

## Phase 0 - Stabilization And Truth Alignment

Goal:
Make the repo safe to build, test, and reason about before adding more features.

### Checklist

- [x] Replace import-time app bootstrap with a proper app factory pattern.
- [x] Remove automatic `db.create_all()` side effects from import/startup path.
- [x] Make test database lifecycle deterministic and isolated.
- [x] Re-run backend targeted failing suites and capture exact remaining failures.
- [x] Reconcile API request/response contracts with current tests.
- [x] Fix schema/test drift for system submission payloads, especially `status`.
- [x] Confirm frontend route map matches actual page files.
- [x] Fix missing SPA modules and broken lazy imports.
- [x] Verify Docker compose files for dev/prod/gateway all parse successfully.
- [x] Remove or clearly label stale status claims in docs.
- [x] Create one source of truth for "implemented", "foundation", and "planned".

### Exit Criteria

- Backend tests can run repeatedly without DB bootstrap/setup collisions.
- Frontend route tree has no missing page modules.
- Core docs no longer contradict current repo state.

### Primary Files

- `server/app.py`
- `tests/conftest.py`
- `server/schemas.py`
- `tests/test_api_endpoints.py`
- `frontend/src/app/router.tsx`
- `frontend/src/app/routePrefetch.ts`
- `PROGRESS_TRACKER.md`
- `FEATURE_COVERAGE_MAP.md`

---

## Phase 1 - Backend Architecture Hardening

Goal:
Convert the backend from "works in many places" to "predictable, maintainable, production-safe".

### Checklist

- [x] Introduce `create_app()` and environment-specific app creation.
- [x] Separate app initialization, extension setup, blueprint registration, and DB setup cleanly.
- [x] Ensure migrations are the DB source of truth instead of runtime table creation.
- [x] Review all auth, tenant, audit, and limiter initialization order.
- [x] Revalidate queue initialization and maintenance job behavior.
- [x] Fix alert dispatch failing tests and queue-backed notification behavior.
- [x] Fix async maintenance job failures and retention/cleanup behavior.
- [x] Review service layer boundaries for exceptions, rollback safety, and audit logging.
- [x] Add regression coverage for startup/bootstrap behavior.
- [x] Add a short backend runbook for local/dev/test startup.

### Exit Criteria

- Backend app startup is factory-based.
- Migrations and tests work without hidden import side effects.
- Core backend failing suites are green.

### Primary Files

- `server/app.py`
- `server/extensions.py`
- `server/queue.py`
- `server/auth.py`
- `server/audit.py`
- `tests/conftest.py`
- `tests/test_alert_notifications.py`
- `tests/test_async_maintenance_jobs.py`

---

## Phase 2 - Frontend Completion And Validation

Goal:
Finish SPA parity and make the frontend deployable with confidence.

### Checklist

- [x] Restore or implement missing `LogsPage`.
- [x] Verify every route in router/navigation/prefetch has a corresponding page module.
- [x] Recheck route guards against actual permission model.
- [x] Validate all major pages against live backend endpoints.
- [x] Review loading, empty, and failure states on operational pages.
- [x] Confirm backup, releases, alerts, automation, logs, and audit flows end-to-end.
- [x] Replace placeholder/template frontend docs with project-specific docs.
- [x] Run TypeScript build validation.
- [x] Run frontend tests and capture current pass/fail status.
- [x] Validate Vite build in a clean environment outside shell-policy blockers.
- [x] Validate `/app` serving, hard refresh, and redirect behavior in deployment.

### Exit Criteria

- No missing page modules.
- Frontend build and tests are verifiably green.
- SPA critical flows are confirmed against real backend behavior.

### Primary Files

- `frontend/src/app/router.tsx`
- `frontend/src/app/routePrefetch.ts`
- `frontend/src/config/navigation.ts`
- `frontend/src/pages/`
- `frontend/README.md`
- `FRONTEND_PHASE_1_TO_5_TRACKING.md`

---

## Phase 3 - Feature Completion From Foundations

Goal:
Turn "foundation implemented" areas into true product features.

### Checklist

- [x] Define which features are adapter-only versus product-complete.
- [x] Complete log ingestion as a persistent product capability, not only adapter/test-double logic.
- [x] Add durable models/storage for logs, incidents, workflow runs, and delivery history where needed.
- [x] Complete automation action backends still marked pending.
- [x] Review reliability features for real host/runtime execution beyond test doubles.
- [x] Review AI/Ollama features for production guardrails, fallback behavior, and observability.
- [x] Add feature-level acceptance criteria for alerts, automation, logs, reliability, AI, updates, and releases.
- [x] Update coverage map to distinguish:
- [x] implemented
- [x] foundation only
- [x] partial
- [x] planned
- [x] Validate each feature area with targeted tests.

### Exit Criteria

- Priority feature areas are measurable end-to-end capabilities.
- Docs no longer treat foundations as complete product delivery.

### Primary Files

- `server/services/automation_service.py`
- `server/services/log_service.py`
- `server/services/reliability_service.py`
- `server/services/ai_service.py`
- `server/services/update_service.py`
- `server/models.py`
- `FEATURE_COVERAGE_MAP.md`

---

## Phase 4 - Deployment, DevOps, And Operational Readiness

Goal:
Make local, staging, and production deployment paths repeatable and verifiable.

### Checklist

- [x] Fix `docker-compose.dev.yml` service definition gaps.
- [x] Validate `docker-compose.yml`, `docker-compose.dev.yml`, `docker-compose.prod.yml`, and `docker-compose.gateway.yml`.
- [x] Confirm required environment variables for prod startup are documented.
- [x] Verify gateway/proxy behavior with SPA and API together.
- [x] Confirm health checks, startup order, volumes, and secrets handling.
- [x] Validate frontend asset serving and cache headers in deployed mode.
- [x] Validate release upload/download flow in a deployment-like environment.
- [x] Add a staging verification checklist for first real deployment.
- [x] Add rollback checklist for SPA wave activation and routing changes.

### Exit Criteria

- All compose variants validate.
- One staging-like deployment path is documented and tested.
- Operational rollback steps are explicit.

### Primary Files

- `docker-compose.yml`
- `docker-compose.dev.yml`
- `docker-compose.prod.yml`
- `docker-compose.gateway.yml`
- `gateway/nginx.conf`
- `DOCKER_DEPLOYMENT_GUIDE.md`
- `FRONTEND_PHASE_5_CUTOVER_PLAYBOOK.md`

---

## Phase 5 - Product Gaps And Overlooked Features

Goal:
Capture the important features that are likely needed but not yet fully planned.

### Checklist

- [x] Decide agent enrollment and provisioning lifecycle.
- [x] Decide API key rotation and tenant secret management model.
- [x] Decide whether tenant settings should be a first-class model/API.
- [x] Plan workflow execution history and audit timeline UX.
- [x] Plan notification delivery history and retry visibility.
- [x] Plan incident/case management layer if operators need investigation workflows.
- [x] Decide whether real-time streaming should use polling, SSE, or WebSocket.
- [x] Decide enterprise auth roadmap: MFA, SSO, OIDC, SAML, session policy.
- [x] Decide commercial/platform roadmap: quotas, billing, licensing, feature flags.
- [x] Define supportability basics: backup/restore verification, retention policies, observability of the platform itself.

Review artifact:

- `PHASE5_PRODUCT_GAPS_REVIEW_REPORT.md`

P0 decision pack:

- `AGENT_IDENTITY_AND_ENROLLMENT_DECISION.md`
- `TENANT_SECRET_MANAGEMENT_DECISION.md`
- `PLATFORM_SUPPORTABILITY_POLICY_DRAFT.md`
- `REALTIME_TRANSPORT_DECISION.md`
- `ENTERPRISE_AUTH_ROADMAP_DECISION.md`
- `COMMERCIAL_PLATFORM_ROADMAP_DECISION.md`

Initial implementation slice:

- `migrations/versions/011_agents_tenant_secrets_and_supportability.py`
- `tests/test_phase5_p0_foundations.py`

Current implementation slice:

- `migrations/versions/012_tenant_settings.py`
- `tests/test_phase5_product_surfaces.py`
- `RESTORE_DRILL_CHECKLIST.md`
- `migrations/versions/013_incident_operator_fields.py`
- `tests/test_phase5_operator_surfaces.py`
- `migrations/versions/014_incident_case_comments.py`
- `tests/test_phase5_incident_case_management.py`

Implementation notes:

- Tenant settings now exist as a first-class model/API with tenant-scoped `GET/PATCH /api/tenant-settings`.
- Workflow history now has both read APIs and frontend operator visibility, and audit now includes a merged operations timeline.
- Notification delivery history now has detail + re-delivery support in both API and frontend operator flows.
- Incident case-management v1 now includes assignment/status/resolution plus tenant-scoped incident comments/notes.
- Supportability now includes a metrics surface and an automated restore-drill endpoint, with a matching operator checklist document.
- Realtime, enterprise-auth, and commercial/platform roadmap decisions are now documented as separate Phase 5 decision files.

### Exit Criteria

- Overlooked platform capabilities are converted into backlog items with ownership.
- Product direction is clearer before large-scale new implementation begins.
- The next execution cycle has a practical P0/P1/P2 backlog file.

### Primary Inputs

- `MASTER_ROADMAP.md`
- `README.md`
- `FEATURE_COVERAGE_MAP.md`
- `PROGRESS_TRACKER.md`
- `PHASE6_EXECUTION_BACKLOG.md`

---

## Recommended Execution Order

Work in this order:

1. Phase 0
2. Phase 1
3. Phase 2
4. Phase 3
5. Phase 4
6. Phase 5

Why this order:

- Phase 0 removes confusion.
- Phase 1 makes backend work reliable.
- Phase 2 makes frontend stable and testable.
- Phase 3 converts partial work into real delivery.
- Phase 4 makes deployment repeatable.
- Phase 5 protects the roadmap from blind spots.

---

## Suggested Working Cadence

For each phase:

1. Pick 3-5 checklist items.
2. Implement code changes.
3. Run targeted validation.
4. Update docs and trackers.
5. Commit only after the checklist slice is truly complete.

Weekly review:

- [ ] What moved from blocked to done?
- [ ] What still lacks validation?
- [ ] Which docs became outdated this week?
- [ ] Which "implemented" items are still only foundations?
- [ ] What should be deferred until stabilization is complete?

---

## Immediate Next Slice

Start here first:

- [x] Productize log ingestion into durable `LogSource` / `LogEntry` storage.
- [x] Add durable `IncidentRecord`, `WorkflowRun`, and `NotificationDelivery` history where the live alert/automation/task paths execute.
- [x] Complete pending automation action backends (`script_execute`, `webhook_call`) or explicitly defer them with product-level constraints.
- [x] Review reliability services for adapter-only/runtime-gap behavior.
- [x] Add feature-level acceptance criteria for alerts, automation, logs, reliability, AI, updates, and releases.

This is the highest-value Phase 3 slice because it converts foundations into operator-visible product behavior and keeps the docs honest about what is truly durable versus still adapter-only.

---

## Phase 6 Kickoff Status

Phase 5 is now materially complete enough to hand off into the Phase 6 execution backlog in `PHASE6_EXECUTION_BACKLOG.md`.

Current Phase 6 reality:

- [x] `P0-A1: Tenant Feature Flags And Entitlements V1` is implemented and validated.
- [x] `P0-B1: Realtime SSE v1 for alerts + operations timeline` is implemented and validated.
- [x] `P0-C1: Enterprise Auth V1 local hardening kickoff` is implemented and validated.
- [x] `P0-C2: Optional TOTP MFA foundation + auth admin surface` is implemented and validated.
- [x] Durable `TenantEntitlement` and `TenantFeatureFlag` models exist.
- [x] Tenant-scoped `GET /api/tenant-controls` and `PATCH /api/tenant-controls` are implemented.
- [x] One real backend/frontend-gated capability now exists for `incident_case_management_v1`.
- [x] Tenant-scoped SSE endpoints now exist for alerts and operations timeline, with frontend consumers and polling fallback.
- [x] Tenant auth-policy defaults, password policy enforcement, lockout baseline, and session revocation foundation now exist.
- [x] Optional TOTP MFA enrollment, activation, login verification, and tenant/admin visibility now exist.
- [x] The TOTP MFA slice was revalidated on April 7, 2026 with targeted backend auth tests plus a fresh frontend production build.
- [x] OIDC foundation now exists with tenant-scoped provider admin APIs, bounded tenant auth-policy toggles, deterministic test-mode login/callback flow, tenant-secret-backed client secret storage, and RBAC claim mapping.
- [x] Quotas and usage metrics now exist with durable quota/usage models, tenant-admin `tenant-quotas` and `tenant-usage` APIs, enforced limits for monitored systems/tenant secrets/automation workflows, and basic SPA admin visibility.
- [x] Billing/licensing preparation now exists with durable `TenantPlan`, `TenantBillingProfile`, and `TenantLicense` models, tenant-admin `tenant-commercial` APIs, explicit contract boundaries between entitlements/quotas/billing/license state, and basic SPA admin visibility.
- [x] Targeted pytest coverage, frontend build validation, and fresh migration upgrade validation are on record.

Current recommended next slice:

- `P0-B: Logs Investigation V2` from `PHASE7_EXECUTION_BACKLOG.md`
