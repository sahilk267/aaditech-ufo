# Feature Acceptance Criteria

Updated: April 10, 2026

## Purpose

This file defines what "good enough to call delivered" means for the major productized areas that are active in Phase 3.

Use it to:

- decide whether a feature can be called `IMPLEMENTED`
- identify the missing work that keeps a feature at `PARTIAL` or `FOUNDATION IMPLEMENTED`
- keep planning, QA, and tracker language aligned

Status labels in this file follow the vocabulary in `FEATURE_COVERAGE_MAP.md` and `PROGRESS_TRACKER.md`.

---

## Alerts

Current status: `IMPLEMENTED`

Acceptance criteria:
- Alert rules can be created, listed, updated, and evaluated per tenant.
- Threshold, anomaly, and pattern alert paths return stable structured responses.
- Alert deduplication, suppression, and escalation work on the live evaluation path.
- Email and webhook delivery run through the queue-backed dispatch path.
- Correlated incidents persist durably as `IncidentRecord`.
- Notification outcomes persist durably as `NotificationDelivery`.
- Operator-facing API coverage exists for the main alert lifecycle.

Still needed before calling it fully mature:
- composite-condition alerts
- richer incident-management workflow beyond current correlation persistence

Primary evidence:
- `tests/test_alerting_api.py`
- `tests/test_alert_notifications.py`

---

## Automation

Current status: `PARTIAL`

Acceptance criteria for `IMPLEMENTED`:
- Workflows can be created, listed, evaluated, executed, and scheduled per tenant.
- Manual, API-triggered, and alert-triggered execution paths all work against the same workflow contract.
- Supported actions have real bounded backends, not placeholder responses.
- Execution history persists durably as `WorkflowRun`.
- Allowlists, timeouts, and dry-run boundaries exist for risky actions.
- Queue-backed execution and inline testing execution both behave consistently.
- Operator-facing tests cover create, execute, schedule, and self-heal flows.

Current blockers:
- broader action catalog is still incomplete
- remote/config/package-management automation remains unimplemented

Primary evidence:
- `tests/test_automation_api.py`
- `server/services/automation_service.py`

---

## Logs

Current status: `PARTIAL`

Acceptance criteria for `IMPLEMENTED`:
- Log sources and log entries persist durably by tenant.
- Ingest, query, parse, correlate, stream, and search APIs work against live stored data.
- Search can return persisted data without depending only on adapter/test-double behavior.
- Correlation can create/update durable incident context where applicable.
- Log workflows are covered in backend and SPA operational-flow validation.
- At least one operator-useful set of source types is supported end-to-end.

Current blockers:
- source coverage is still narrow
- application/security/container/database log product slices are still missing
- broader retention workflows are still missing

Primary evidence:
- `tests/test_logs_api.py`
- `tests/test_phase6_logs_investigation.py`
- `tests/test_frontend_operational_flows.py`

---

## Reliability

Current status: `PARTIAL`

Acceptance criteria for `IMPLEMENTED`:
- Reliability history, score, trend, prediction, and pattern APIs work from real persisted telemetry, not only deterministic doubles.
- Crash-dump parse, exception identification, and stack-trace analysis work against real bounded local-file inputs or another production-grade source.
- Runtime boundaries are tenant-safe and host-safe.
- Operator-facing tests cover both the live local-runtime paths and bounded fallback paths.
- Reliability outputs are usable in dashboard/operator flows, not just as isolated service adapters.

Current blockers:
- broader operator investigation workflows beyond the current persisted run history are still incomplete, but aggregate reporting, recent-failure visibility, and related crash-run drill-down now exist
- broader crash/failure coverage is incomplete
- deeper product-level investigation UX is improved but still incomplete

Primary evidence:
- `tests/test_reliability_api.py`
- `tests/test_phase6_reliability_operator.py`
- `tests/test_phase7_reliability_operator_v2.py`
- `server/services/reliability_service.py`

---

## AI / Ollama

Current status: `PARTIAL`

Acceptance criteria for `IMPLEMENTED`:
- AI-backed routes enforce model allowlists, endpoint validation, and host allowlists.
- Prompt and response size limits are enforced.
- HTTP-backed inference failures degrade safely according to explicit configuration.
- Runtime observability is exposed for supportability: requested adapter, duration, fallback usage, and primary error reason.
- Root cause, recommendations, troubleshooting, learning, anomaly analysis, and incident explanation all use the same safe inference boundary.
- Operator-facing regression coverage exists for both success and failure/fallback paths.

Current blockers:
  - still wrapper-based rather than a fully productionized model-serving platform
  - no richer prompt/version governance or production telemetry pipeline yet
  - no persisted AI decision history beyond current request/response use, though operator-facing audit-derived diagnostics now exist
  - no deeper chat/copilot-style operator workflow yet beyond the current task-oriented routes and diagnostics page

Primary evidence:
  - `tests/test_ollama_api.py`
  - `tests/test_ai_assistant_learning_api.py`
  - `tests/test_alert_suppression_pattern_ai_anomaly.py`
  - `tests/test_phase2_remaining_features.py`
  - `tests/test_phase7_ai_operational_maturity.py`

---

## Updates

Current status: `FOUNDATION IMPLEMENTED`

Acceptance criteria for `IMPLEMENTED`:
- Update monitoring works through a real supported runtime path, not only bounded adapter logic.
- Results can be persisted or otherwise retained for operator review/history.
- Error/failure states are operator-usable and tenant-safe.
- Update information participates in broader product workflows where expected.
- Regression coverage exists for the live runtime path.

Current blockers:
- still adapter-driven and `foundation-v1`
- no broader remediation or policy workflow yet
- rollout/remediation policy workflow is still incomplete

Primary evidence:
- `server/services/update_service.py`
- `server/blueprints/api.py`
- `tests/test_update_monitor_api.py`
- `tests/test_phase6_updates_productization.py`

---

## Releases

Current status: `IMPLEMENTED`

Acceptance criteria:
- Release upload, list, policy, guide, and download flows work consistently.
- Uploaded artifacts are stored durably and downloaded byte-for-byte.
- Deployment-like validation confirms rendered URLs and attachment responses.
- SPA and API flows agree on the release contract where applicable.
- Release handling is covered by targeted regression tests.

Still needed before calling it fully mature:
- staging/production operational adoption and rollout policy refinements

Primary evidence:
- `tests/test_agent_release_api.py`
- `tests/test_agent_release_service.py`

---

## Commercial Controls / Quotas

Current status: `PARTIAL`

Acceptance criteria for `IMPLEMENTED`:
- Tenant admins can read effective quota policies, current usage, and an operator-usable quota health report.
- Quota reporting exposes percentage-used style visibility plus recent enforcement failures.
- Quota enforcement exists on the main resource-creation paths that materially affect plan boundaries.
- The SPA admin surface exposes both quota controls and current quota health, not only raw backend APIs.
- Regression coverage proves both enforcement and reporting behavior.

Current blockers:
- broader quota domains such as retention/storage or execution-volume boundaries are still open
- quotas are not yet tied into a real billing-provider lifecycle or contract enforcement path

Primary evidence:
- `tests/test_phase6_quotas_usage.py`
- `tests/test_phase7_quota_reporting.py`
- `frontend/src/pages/tenants/TenantsPage.tsx`

---

## How To Use This File

- Move a feature to `IMPLEMENTED` only when every acceptance bullet for that area is true in the repo.
- If a feature has real user value but misses one or more acceptance bullets, keep it at `PARTIAL`.
- If only boundaries, schemas, or adapters exist, keep it at `FOUNDATION IMPLEMENTED`.
- When a future task closes one of the listed blockers, update this file, `FEATURE_COVERAGE_MAP.md`, and `PROGRESS_TRACKER.md` together.
