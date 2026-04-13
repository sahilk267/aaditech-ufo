# AADITECH UFO - Documentation Index

Updated: April 13, 2026

## Purpose

This file is the navigation map for the repository's documentation.

Use it to answer two questions quickly:

1. Which documents are the current source of truth?
2. Which documents are historical or planning references?

---

## Start Here

If you need the current repo reality, read these first:

| Need | Document |
| --- | --- |
| Current active execution plan | [CURRENT_PHASE_WISE_PROGRESS_PLAN.md](CURRENT_PHASE_WISE_PROGRESS_PLAN.md) |
| Real-time progress and latest validated slice | [PROGRESS_TRACKER.md](PROGRESS_TRACKER.md) |
| Current execution backlog | [PHASE7_EXECUTION_BACKLOG.md](PHASE7_EXECUTION_BACKLOG.md) |
| Current repo-wide status snapshot | [FULL_REPO_REBASELINE_REPORT_2026_04_09.md](FULL_REPO_REBASELINE_REPORT_2026_04_09.md) |
| Feature status vocabulary and coverage | [FEATURE_COVERAGE_MAP.md](FEATURE_COVERAGE_MAP.md) |
| Feature exit criteria | [FEATURE_ACCEPTANCE_CRITERIA.md](FEATURE_ACCEPTANCE_CRITERIA.md) |
| Backend startup / migration / runtime flow | [BACKEND_STARTUP_RUNBOOK.md](BACKEND_STARTUP_RUNBOOK.md) |
| Frontend local dev / build / deployment notes | [frontend/README.md](frontend/README.md) |
| Staging deploy checklist | [STAGING_VERIFICATION_CHECKLIST.md](STAGING_VERIFICATION_CHECKLIST.md) |
| SPA rollback checklist | [SPA_WAVE_ROLLBACK_CHECKLIST.md](SPA_WAVE_ROLLBACK_CHECKLIST.md) |

---

## Current Source Of Truth

Use these during active development and review:

- [CURRENT_PHASE_WISE_PROGRESS_PLAN.md](CURRENT_PHASE_WISE_PROGRESS_PLAN.md)
- [PROGRESS_TRACKER.md](PROGRESS_TRACKER.md)
- [PHASE7_EXECUTION_BACKLOG.md](PHASE7_EXECUTION_BACKLOG.md)
- [FEATURE_COVERAGE_MAP.md](FEATURE_COVERAGE_MAP.md)
- [FEATURE_ACCEPTANCE_CRITERIA.md](FEATURE_ACCEPTANCE_CRITERIA.md)
- [BACKEND_STARTUP_RUNBOOK.md](BACKEND_STARTUP_RUNBOOK.md)
- [frontend/README.md](frontend/README.md)
- [STAGING_VERIFICATION_CHECKLIST.md](STAGING_VERIFICATION_CHECKLIST.md)
- [SPA_WAVE_ROLLBACK_CHECKLIST.md](SPA_WAVE_ROLLBACK_CHECKLIST.md)

Rule:

- Prefer these files over older milestone snapshots when there is wording drift.

---

## Current Strategy And Decision Docs

Use these when working on platform direction or deeper product changes:

- [PHASE5_PRODUCT_GAPS_REVIEW_REPORT.md](PHASE5_PRODUCT_GAPS_REVIEW_REPORT.md)
- [AGENT_IDENTITY_AND_ENROLLMENT_DECISION.md](AGENT_IDENTITY_AND_ENROLLMENT_DECISION.md)
- [TENANT_SECRET_MANAGEMENT_DECISION.md](TENANT_SECRET_MANAGEMENT_DECISION.md)
- [PLATFORM_SUPPORTABILITY_POLICY_DRAFT.md](PLATFORM_SUPPORTABILITY_POLICY_DRAFT.md)
- [REALTIME_TRANSPORT_DECISION.md](REALTIME_TRANSPORT_DECISION.md)
- [ENTERPRISE_AUTH_ROADMAP_DECISION.md](ENTERPRISE_AUTH_ROADMAP_DECISION.md)
- [COMMERCIAL_PLATFORM_ROADMAP_DECISION.md](COMMERCIAL_PLATFORM_ROADMAP_DECISION.md)
- [RESTORE_DRILL_CHECKLIST.md](RESTORE_DRILL_CHECKLIST.md)

---

## Architecture And Vision

Use these to understand the larger product direction, not day-to-day status:

- [README.md](README.md)
- [MASTER_ROADMAP.md](MASTER_ROADMAP.md)
- [UPDATED_ARCHITECTURE.md](UPDATED_ARCHITECTURE.md)
- [ADVANCED_WINDOWS_TROUBLESHOOTING.md](ADVANCED_WINDOWS_TROUBLESHOOTING.md)
- [IMPLEMENTATION_REFERENCE_GUIDE.md](IMPLEMENTATION_REFERENCE_GUIDE.md)
- [WEEK_BY_WEEK_CHECKLIST.md](WEEK_BY_WEEK_CHECKLIST.md)

---

## Frontend-Specific Docs

- [FRONTEND_VITE_SPA_IMPLEMENTATION_PLAN.md](FRONTEND_VITE_SPA_IMPLEMENTATION_PLAN.md)
- [FRONTEND_PHASE_1_TO_5_TRACKING.md](FRONTEND_PHASE_1_TO_5_TRACKING.md)
- [FRONTEND_PHASE_5_CUTOVER_PLAYBOOK.md](FRONTEND_PHASE_5_CUTOVER_PLAYBOOK.md)
- [FRONTEND_PHASE_5_COMPATIBILITY_RETIREMENT_CRITERIA.md](FRONTEND_PHASE_5_COMPATIBILITY_RETIREMENT_CRITERIA.md)
- [frontend/README.md](frontend/README.md)

Note:

- `FRONTEND_PHASE_1_TO_5_TRACKING.md` is now primarily a historical frontend migration record. For the current active state, check [PROGRESS_TRACKER.md](PROGRESS_TRACKER.md) and [PHASE7_EXECUTION_BACKLOG.md](PHASE7_EXECUTION_BACKLOG.md).

---

## Deployment And Operations

- [BACKEND_STARTUP_RUNBOOK.md](BACKEND_STARTUP_RUNBOOK.md)
- [STAGING_VERIFICATION_CHECKLIST.md](STAGING_VERIFICATION_CHECKLIST.md)
- [SPA_WAVE_ROLLBACK_CHECKLIST.md](SPA_WAVE_ROLLBACK_CHECKLIST.md)
- [PHASE4_REVIEW_REMEDIATION_TODOS.md](PHASE4_REVIEW_REMEDIATION_TODOS.md)
- [RESTORE_DRILL_CHECKLIST.md](RESTORE_DRILL_CHECKLIST.md)
- [DOCKER_DEPLOYMENT_GUIDE.md](DOCKER_DEPLOYMENT_GUIDE.md)

---

## Historical Snapshots

These are useful context, but they are not the primary truth source for current execution:

- [ARCHIVE/README_CURRENT_STATE.md](ARCHIVE/README_CURRENT_STATE.md)
- [FULL_REPO_REBASELINE_REPORT_2026_04_01.md](FULL_REPO_REBASELINE_REPORT_2026_04_01.md)
- [FULL_REPO_REBASELINE_REPORT_2026_04_09.md](FULL_REPO_REBASELINE_REPORT_2026_04_09.md)

Interpretation rule:

- If a historical snapshot conflicts with the active plan or tracker, follow the active plan/tracker.

---

## Documentation Truth Rules

- Do not treat roadmap or vision language as delivery proof.
- Do not treat historical rebaseline files as live status without checking the tracker.
- When a slice lands, update the active plan, tracker, and the most relevant feature-specific doc together.
- If a document becomes historical, label it clearly instead of silently letting it drift.
