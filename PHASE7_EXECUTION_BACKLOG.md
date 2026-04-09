# Phase 7 Execution Backlog

Updated: April 9, 2026

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

---

## P1

### P1-A: Reliability Operator V2

Goal:

Deepen reliability from persisted runs into stronger operator lifecycle and reporting.

Deliverables:

- richer run filtering/reporting
- stronger crash/exception investigation flow
- clearer trend and score review UX

### P1-B: AI / Ollama Operational Maturity

Goal:

Push AI from guarded foundation into a clearer operational product slice.

Deliverables:

- stronger runtime observability
- provider/fallback visibility
- admin/operator diagnostics around inference behavior

### P1-C: Quota Expansion And Reporting

Goal:

Expand quotas from key hooks into a broader platform control/reporting layer.

Deliverables:

- additional quota domains if justified
- better usage reporting/admin visibility
- clearer acceptance criteria for quotaed resources

---

## P2

### P2-A: Billing Provider Boundary Prep

Goal:

Prepare the draft commercial models for later provider integration without hard-coding a billing vendor too early.

Deliverables:

- provider adapter boundary draft
- stronger plan/license lifecycle semantics
- docs and acceptance updates

### P2-B: Documentation Truth Sweep

Goal:

Reduce trust drift in older large documentation files.

Deliverables:

- refresh older large docs against current source-of-truth files
- archive or flag stale sections
- cleaner onboarding/document navigation

---

## Suggested First Working Slice

Start with:

### `P0-B: Logs Investigation V2`

Why this slice:

- logs is one of the clearest remaining product-depth opportunities
- the repo now has a fresh validation baseline, so deeper product work can proceed safely
- this continues a partial-but-real area instead of opening another foundation track

---

## Exit Criteria For Phase 7 Start

Phase 7 should be considered underway once:

- the fresh rebaseline is recorded
- one `P0` slice is active with dedicated regression proof
- tracker and plan point to this backlog instead of Phase 6 as the active next-cycle source
