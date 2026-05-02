# PHASE_0 AUDIT — Database TODO

Status: open
Priority: P3 (Docs / Runbook)
Owner: unassigned

Source: PHASE_0_AUDIT_REPORT.md (see Database - TODO)

Summary
-------
The project audit notes a "Database (Week 4) - TODO" entry requiring completion. This ticket collects the concrete tasks needed to close that TODO and avoid duplicate implementation effort.

Goals
-----
- Document database schema verification steps for new environments.
- Provide deterministic `flask db upgrade`/migration validation guidance using reproducible SQLite/PG fixtures.
- List required smoke-check SQL queries and expected results for a green DB validation.
- Enumerate any outstanding DB model TODOs found in code or migration templates.

Proposed Steps
--------------
1. Inspect `migrations/` for incomplete `script.py.mako` and note placeholders.
2. Create a reproducible `phase0_db_validation` SQLite fixture and a checklist of commands:

   - `flask --app server.app db upgrade --sql` (verify generated SQL)
   - `flask --app server.app db upgrade` against a clean DB and run smoke queries
3. Add a short section to `PHASE_0_AUDIT_REPORT.md` explaining how to validate locally and in CI.
4. Link tests that must pass post-migration and add a note of owners for DB reviews.

Acceptance Criteria
-------------------
- `PHASE_0_AUDIT_REPORT.md` Database section populated with steps and commands.
- One example run documented and a CI checklist item added to `PROGRESS_TRACKER.md`.

Notes
-----
File reference: [PHASE_0_AUDIT_REPORT.md](PHASE_0_AUDIT_REPORT.md#L316)

If you want, I can open a PR adding the `PHASE_0_AUDIT_REPORT.md` content and the example fixture.