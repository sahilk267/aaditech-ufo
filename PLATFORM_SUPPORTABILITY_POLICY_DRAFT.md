# Platform Supportability Policy Draft

Updated: March 31, 2026

## Purpose

Define the minimum supportability baseline the platform should meet before broad enterprise rollout.

This draft focuses on:

- backup and restore verification
- retention policy
- observability of the platform itself

---

## Why This Matters

The platform already supports backup, audit retention, queue/cache health, and AI request observability in isolated areas.

What is still missing is a single platform-level supportability policy that says:

- what must be retained
- what must be monitored
- what must be verified regularly

---

## Scope

This draft applies to:

- application runtime
- tenant operational history
- backups and restore drills
- queue and async job health
- release storage
- core security/compliance event trails

---

## 1. Backup And Restore Verification Policy

### Current reality

- backup create/list/restore exists
- UI already notes that dry-run and integrity toggles are advisory only

### Required policy

1. Backups must be creatable on demand.
2. Backups must be enumerable with timestamp and size metadata.
3. Restore must be exercised in a non-production environment on a defined cadence.
4. Restore verification must confirm:
   - DB file or schema is readable
   - migrations still apply cleanly after restore when relevant
   - app can boot against restored state
   - a minimal smoke flow works after restore

### Recommended cadence

- on-demand backups for operators
- weekly restore verification in staging or isolated verification environment
- before major release/cutover events, perform a fresh restore drill

### Required future product gap

- add backend-supported restore verification flow instead of advisory UI-only toggles

### Current implementation update

- `POST /api/backups/<filename>/verify` now provides a backend verification result.
- `POST /api/backups/<filename>/restore-drill` now provides a lightweight non-destructive drill report with checklist evidence.
- The operational procedure is documented in `RESTORE_DRILL_CHECKLIST.md`.

---

## 2. Retention Policy Baseline

Recommended initial retention matrix:

| Data Class | Recommended Baseline |
|---|---|
| Audit events | 90 days minimum |
| Notification deliveries | 30-90 days depending on volume |
| Workflow runs | 30-90 days depending on volume |
| Incident records | retain open incidents; resolved incidents 90+ days |
| Log entries | configurable by source class and storage budget |
| Release artifacts | retain current target + rollback set + recent history |
| Revoked tokens | retain until expiry, then purge |

### Policy notes

- retention must become tenant-configurable only after a platform default exists
- legal/compliance requirements may require longer audit retention later
- logs likely need tiered retention by source type, not one global number

---

## 3. Platform Observability Baseline

The platform should expose operational signals for itself, not just monitored hosts.

### Minimum areas to observe

- app health
- database connectivity
- Redis connectivity
- queue health
- maintenance job failures
- automation execution failures
- alert dispatch failures
- backup/restore failures
- release storage usage
- audit growth

### Recommended metrics/events to expose

- request rate / error rate
- queue enqueue failures
- queue task success/failure counts
- delivery failure counts
- workflow failure counts
- backup success/failure counts
- restore verification success/failure counts
- release artifact count / storage size
- tenant count / active user count high-level stats

### Recommended product direction

- add a platform metrics endpoint or internal admin metrics surface
- keep sensitive content out of metrics
- treat `/health` as readiness visibility, not full observability

---

## 4. Operational Drill Expectations

Minimum recurring drills:

- restore drill
- alert delivery failure drill
- queue degradation drill
- rollback drill for SPA/deployment cutover

Each drill should produce:

- date
- environment
- operator
- result
- findings
- follow-up actions

---

## 5. Recommended Ownership Areas

### Platform Operations

- backup execution
- restore drill cadence
- deployment monitoring

### Product / Platform Engineering

- retention defaults
- observability surface
- support tooling APIs

### Tenant Administration

- tenant-level operational settings once those exist

---

## 6. Immediate Backlog Derived From This Draft

1. Add a restore verification workflow definition.
2. Add retention defaults for workflow runs, delivery history, incidents, and logs.
3. Add read APIs for supportability-relevant histories.
4. Define platform metrics surface for operators.
5. Add a documented recurring restore-drill checklist.

Status update:

- Items 3, 4, and 5 now have an initial implementation foundation in the repo.

---

## Recommended Status

This draft should be treated as `P0` because supportability is now one of the main remaining gaps between a validated codebase and a production-ready platform.
