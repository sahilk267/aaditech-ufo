# NEXT CYCLE BACKLOG

Updated: April 13, 2026

## Purpose

This file is the active next-cycle backlog source once Phase 7 closeout is complete.
It captures the prioritized productization and operational completion work that should begin after the Phase 7 repo rebaseline and documentation truth sweep.

## Current Context

- Phase 7 implementation slices are complete.
- Phase 7 closeout is active and the repo is being aligned to a fresh current-truth baseline.
- The next cycle should focus on converting the remaining Partial/Foundation areas from Phase 3 and Phase 4 into product-complete, validated capabilities.

## Backlog Rules

- `P0` means highest leverage for the current repo state.
- `P1` means important product completion and validation after the first P0 slice lands.
- `P2` means supportability, polish, and broadened scope work.

## Candidate Next-Cycle Slices

### P0-A: Phase 3 Productization Cleanup

Focus on the remaining Partial/Foundation area completion work in:
- Automation: remote script execution, service restart action flows, full alert-triggered automation, and durable execution history.
- Logs: broader source coverage, richer operator investigation flows, and finished log parsing/search UX.
- Reliability: deeper crash investigation coverage, trend/prediction polish, and investigation drill-down completeness.
- AI / Ollama: anomaly detection, root-cause operational maturity, recommendations, and troubleshooting assistance.
- Updates: full Windows Update monitoring productization and confidence-backed review workflows.

#### First P0-A Tasks

- [x] Review `FEATURE_COVERAGE_MAP.md` and `FEATURE_ACCEPTANCE_CRITERIA.md` for automation, logs, reliability, AI, and updates to confirm scope.
- [x] Complete the `remote script execution` automation action path in `server/services/automation_service.py` and validate via `tests/test_automation_api.py`.
- [x] Finish `service restart` action execution and durable `WorkflowRun` history recording in automation.
- [x] Expand log persistence coverage in `server/services/log_service.py`, `server/models.py`, and `tests/test_logs_api.py`.
- [x] Add targeted regression coverage for saved investigation workflows and log query restore behavior.
- [ ] Validate the corresponding SPA pages for logs, automation, reliability, and AI against the live backend.
- [x] Run targeted Phase 3 candidate validation:
  - `pytest tests/test_automation_api.py tests/test_logs_api.py -q`

### P0-B: Operator/User-Facing Product Completion

- dashboard/metrics analytics productization
- tenant/admin quota and commercial controls polish
- stronger validation and acceptance criteria coverage for the above slices

### P1-A: Remote Infrastructure Control Completion

- complete remote service restart and remote script execution flows
- add remote server management lifecycle actions
- improve safe operator controls and allowlist boundaries

### P1-B: Dashboard and Metrics Productization

- finish historical performance charts, capacity forecasting, and real-time infrastructure views
- add customizable dashboard or operator summary panels where it adds clear value

### P1-C: Multi-Tenant SaaS Hardening

- strengthen tenant isolation, deployment/runtime stability, and admin visibility
- improve staging and rollback verification paths
- capture supportability and handoff documentation for operators

### P2-A: Documentation and Onboarding Support

- update onboarding/docs to reflect fresh current state
- publish exact validation and exit criteria for new next-cycle slices
- archive Phase 7 historical snapshots behind explicit "historical note" framing

## How to Use This File

1. Confirm Phase 7 closeout is complete and the current status docs are aligned.
2. Use `FEATURE_COVERAGE_MAP.md` and `FEATURE_ACCEPTANCE_CRITERIA.md` to shape the next-cycle slice definitions.
3. Turn the highest-leverage P0 candidate into the first active implementation slice.
4. Update `PROGRESS_TRACKER.md` and `CURRENT_PHASE_WISE_PROGRESS_PLAN.md` to point at this file as the active backlog.
