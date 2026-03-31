# Restore Drill Checklist

Updated March 31, 2026 for Phase 5 supportability implementation.

---

## Goal

Run a lightweight, repeatable restore drill that proves backups are readable, integrity-checked, and suitable for a controlled restore rehearsal.

---

## Automated Entry Point

Use the API-first restore drill when a recent backup file already exists:

```bash
curl -X POST \
  -H "X-API-Key: <api-key>" \
  -H "X-Tenant-Slug: default" \
  http://localhost:5000/api/backups/<backup_filename>/restore-drill
```

Expected result:

- `success: true`
- `verification.verified: true`
- checklist items `backup_exists`, `integrity_check`, and `restore_copy_readable` marked `passed`
- checklist item `app_smoke_after_restore` marked `manual_followup_required`

---

## Operator Checklist

1. Confirm a recent backup exists in the configured backup directory.
2. Run `POST /api/backups/<filename>/verify` if you only need a quick integrity check.
3. Run `POST /api/backups/<filename>/restore-drill` for the supportability drill record.
4. Capture the returned checklist and verification payload in the deployment/support ticket.
5. Restore the backup into an isolated environment or copied database path, never directly over live production during a drill.
6. Run minimum smoke checks against the restored copy:
   - `/health`
   - `/api/health`
   - tenant auth/API access
   - one representative operational read path such as alerts, incidents, or logs
7. Record whether schema migrations and startup complete cleanly against the restored copy.
8. Record drill date, operator, backup filename, and any manual follow-up findings.

---

## Evidence To Capture

- backup filename
- backup file timestamp and size
- restore-drill API response payload
- smoke-check results from restored environment
- follow-up tickets if any checklist step required manual remediation

---

## Recommended Cadence

- staging: before first deployment, then monthly
- production: at least quarterly
- after major schema or backup-process changes: run an extra drill

---

## Notes

- The automated restore drill is intentionally non-destructive.
- Full restore confidence still requires a manual isolated restore plus smoke validation.
- This checklist complements [PLATFORM_SUPPORTABILITY_POLICY_DRAFT.md](PLATFORM_SUPPORTABILITY_POLICY_DRAFT.md) and [STAGING_VERIFICATION_CHECKLIST.md](STAGING_VERIFICATION_CHECKLIST.md).
