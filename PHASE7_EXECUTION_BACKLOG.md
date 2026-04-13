# Phase 7 Execution Backlog

Updated: April 13, 2026

## Purpose

Turn the post-Phase-6 repo state into a practical next-cycle execution backlog.

This backlog is derived from:

- `FULL_REPO_REBASELINE_REPORT_2026_04_09.md`
- `FEATURE_ACCEPTANCE_CRITERIA.md`
- `ENTERPRISE_AUTH_ROADMAP_DECISION.md`
- `COMMERCIAL_PLATFORM_ROADMAP_DECISION.md`
- `REALTIME_TRANSPORT_DECISION.md`

---

## Backlog Rules

- `P0` means highest leverage for the current repo state.
- `P1` means important product-depth work after the first `P0` slice lands.
- `P2` means strategically useful but lower urgency.
- Every slice should still include code, tests, and doc updates together.

---

## Recommended Execution Order

1. P0-A: Full Validation Rebaseline
2. P0-B: Logs Investigation V2
3. P0-C: OIDC External Maturity
4. P1-A: Reliability Operator V2
5. P1-B: AI / Ollama Operational Maturity
6. P1-C: Quota Expansion And Reporting
7. P2-A: Billing Provider Boundary Prep
8. P2-B: Documentation Truth Sweep

---

## P0

### P0-A: Full Validation Rebaseline

Goal:

Refresh the repo-wide validation baseline so the next cycle starts from current truth instead of historical mixed snapshots.

Deliverables:

- fresh wider/full backend regression snapshot
- current frontend validation snapshot
- tracker and report cleanup for stale historical wording

Primary files:

- `PROGRESS_TRACKER.md`
- `FULL_REPO_REBASELINE_REPORT_2026_04_09.md`
- `CURRENT_PHASE_WISE_PROGRESS_PLAN.md`

Status:

- Completed on April 10, 2026
- Fresh backend validation rebaseline recorded against the current `354`-item suite
- Full-suite `pytest -q` reached `89%` with no failures before the 10-minute timeout, and the remaining tail subset passed separately
- Frontend production build revalidated successfully
- Frontend Vitest suite revalidated successfully with `5 files, 85 passed`
- Tracker/report/active-plan documents now point at the next real execution slice instead of the rebaseline task

### P0-B: Logs Investigation V2

Goal:

Push logs from stored history into a stronger investigation workflow.

Deliverables:

- saved investigation/query support
- richer correlation and source-level filters
- stronger log-entry drill-down and operator flow

Primary files:

- `server/blueprints/api.py`
- `server/models.py`
- `frontend/src/pages/logs/LogsPage.tsx`
- `FEATURE_ACCEPTANCE_CRITERIA.md`

Status:

- Completed on April 10, 2026
- Saved tenant-scoped log investigations now persist filter snapshots, pinned source/entry context, notes, and last match counts
- The SPA logs page now supports saving, restoring, and updating investigations as part of the operator workflow
- Targeted logs/backend contract validation, frontend production build validation, and fresh migration upgrade validation are on record

### P0-C: OIDC External Maturity

Goal:

Move OIDC from deterministic foundation to a more realistic external-provider integration slice.

Deliverables:

- provider metadata/discovery support if chosen
- external token exchange path
- clearer failure/observability surface
- stronger admin guidance and validation

Primary files:

- `server/blueprints/api.py`
- `server/auth.py`
- `ENTERPRISE_AUTH_ROADMAP_DECISION.md`
- `frontend/src/pages/tenants/TenantsPage.tsx`

Status:

- Completed on April 10, 2026
- Tenant-scoped OIDC providers now support discovery metadata refresh, bounded external code exchange, userinfo-backed claim fetches, and persisted discovery/auth status visibility
- The SPA tenant admin surface now supports discovery-aware provider setup and metadata refresh actions for external providers
- Dedicated OIDC maturity regression coverage, frontend production build validation, and fresh migration upgrade validation are on record

---

## P1

### P1-A: Reliability Operator V2

Goal:

Deepen reliability from persisted runs into stronger operator lifecycle and reporting.

Deliverables:

- richer run filtering/reporting
- stronger crash/exception investigation flow
- clearer trend and score review UX

Status:

- Completed on April 10, 2026
- Reliability runs now support richer filtering by dump and error reason, plus latest-per-type reporting
- Operator-facing reliability reporting now includes aggregate summaries, recent failures, latest score/trend/prediction views, and related crash investigation runs
- The SPA reliability page now exposes operator summary panels, recent failures, crash timelines, and related-run drill-down flows
- Dedicated reliability operator V2 regression coverage, frontend production build validation, and fresh migration upgrade validation are on record

### P1-B: AI / Ollama Operational Maturity

Goal:

Push AI from guarded foundation into a clearer operational product slice.

Deliverables:

- stronger runtime observability
- provider/fallback visibility
- admin/operator diagnostics around inference behavior

Status:

- Completed on April 10, 2026
- Added tenant-scoped `/api/ai/operations/report` diagnostics built from live AI audit history
- AI SPA now surfaces operational summary cards, provider/fallback visibility, recent operations, and recent failures
- Targeted backend AI suites, frontend production build, and fresh migration upgrade validation are on record

### P1-C: Quota Expansion And Reporting

Goal:

Expand quotas from key hooks into a broader platform control/reporting layer.

Deliverables:

- additional quota domains if justified
- better usage reporting/admin visibility
- clearer acceptance criteria for quotaed resources

Status:

- Completed on April 11, 2026
- Expanded quota coverage to additional live domains: `alert_rules` and `oidc_providers`
- Added tenant-scoped quota health reporting with usage percentage, near-limit/over-limit status, and recent enforcement visibility
- The SPA tenant admin page now shows quota summary cards and recent enforcement events instead of only the basic usage table
- Targeted backend quota/reporting validation and frontend production build validation are on record

---

## P2

### P2-A: Billing Provider Boundary Prep

Goal:

Prepare the draft commercial models for later provider integration without hard-coding a billing vendor too early.

Deliverables:

- provider adapter boundary draft
- stronger plan/license lifecycle semantics
- docs and acceptance updates

Status:

- Completed on April 11, 2026
- Added a tenant-scoped billing provider boundary draft with supported-provider capabilities, sync-readiness flags, and outbound contract preview data
- Tightened commercial patch semantics around plan status, billing cycle, provider name, license status, enforcement mode, and ISO date fields
- The SPA tenant admin surface now shows provider readiness, supported-provider capabilities, and lifecycle semantics
- Targeted backend billing-boundary validation and frontend production build validation are on record

### P2-B: Documentation Truth Sweep

Goal:

Reduce trust drift in older large documentation files.

Deliverables:

- refresh older large docs against current source-of-truth files
- archive or flag stale sections
- cleaner onboarding/document navigation

Status:

- Completed on April 13, 2026
- Refreshed the docs index so it now clearly separates current source-of-truth files from historical snapshots and planning references
- Updated `README.md`, `FRONTEND_PHASE_1_TO_5_TRACKING.md`, and `CURRENT_PHASE_WISE_PROGRESS_PLAN.md` so their status framing matches the current Phase 7 reality
- Added explicit historical framing to the April 9 repo rebaseline snapshot to reduce trust drift during onboarding and review

---

## Suggested First Working Slice

Start with:

### `Phase 7 Closeout Rebaseline And Next-Cycle Backlog Refresh`

Why this slice:

- Phase 7 implementation slices are now complete
- the repo now benefits more from a fresh rebaseline and next-cycle planning refresh than from another ad hoc feature slice
- the documentation truth sweep reduced drift, so the next backlog can start from a cleaner base

---

## Exit Criteria For Phase 7 Start

Phase 7 should be considered underway once:

- the fresh rebaseline is recorded
- one post-rebaseline `P0` slice is completed with dedicated regression proof
- tracker and plan point to this backlog instead of Phase 6 as the active next-cycle source
