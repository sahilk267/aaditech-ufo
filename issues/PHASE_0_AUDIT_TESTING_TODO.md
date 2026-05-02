# PHASE_0 AUDIT — Testing TODO

Status: open
Priority: P3 (Docs / Runbook)
Owner: unassigned

Source: PHASE_0_AUDIT_REPORT.md (see Testing - TODO)

Summary
-------
The audit lists testing as TODO. This ticket defines the required testing validation steps, CI checklist items, and guidance to ensure the codebase verifies correctly after future changes.

Goals
-----
- Define which test suites are required for local validation and CI gating.
- Document how to run the entire `pytest -q` suite and interpret common warnings/errors.
- Describe reproduction steps for flaky tests and how to isolate failures.
- Add recommended CI resources / timeout considerations for the full-suite run.

Proposed Steps
--------------
1. List the core test commands and a minimal fast-check subset (already present in `PROGRESS_TRACKER.md`).
2. Document how to run the full tests locally and recommended hardware/time expectations (e.g., ~20 minutes for full suite on dev machine).
3. Add a short troubleshooting guide for common failures (database, Redis, env vars) and how to reproduce in isolation.
4. Add an entry to `PHASE_0_AUDIT_REPORT.md` linking to this testing checklist.

Acceptance Criteria
-------------------
- `PHASE_0_AUDIT_REPORT.md` Testing section populated with commands and references.
- `PROGRESS_TRACKER.md` contains an explicit item for full-suite validation and CI gating.

Notes
-----
File reference: [PHASE_0_AUDIT_REPORT.md](PHASE_0_AUDIT_REPORT.md#L326)

I can draft the `PHASE_0_AUDIT_REPORT.md` additions and a small `ci/README.md` snippet if you want me to proceed.