# SPA Wave Rollback Checklist

Updated: March 30, 2026

## Purpose

Use this checklist if a staged or production SPA wave activation causes routing, auth, deep-link, or hard-refresh issues and you need to return traffic to the legacy Jinja routes quickly.

This checklist matches the current repo behavior:

- `/app` remains the SPA shell path
- legacy routes can be switched between direct rendering and redirect behavior with `SPA_WAVE_1_ENABLED`
- current wave-1 legacy routes are `/`, `/user`, `/user/<serial_number>`, `/history`, and `/backup`

---

## 1. Rollback Triggers

Rollback if any of these appear after wave activation:

- [ ] `/app` hard refresh starts returning `404` or `503`
- [ ] `/`, `/user`, `/history`, or `/backup` redirect loops appear
- [ ] `/user/<serial_number>` stops preserving the serial deep link into `/app/systems?serial=...`
- [ ] browser session auth fails across redirected compatibility routes
- [ ] gateway/app route behavior differs from what passed in staging
- [ ] SPA shell loads but critical navigation or API bootstrapping is broken for users

---

## 2. Immediate Rollback Lever

Primary rollback action:

- [ ] Set `SPA_WAVE_1_ENABLED=False` in the active deployment environment

Expected effect:

- `/`, `/user`, `/user/<serial_number>`, `/history`, and `/backup` stop redirecting to `/app/...`
- legacy Jinja-backed routes become primary again
- `/app` remains available for isolated validation without being the default redirect target

---

## 3. Rollback Procedure

1. Confirm the incident and record the failing route, exact URL, and user-visible symptom.
2. Disable wave-1 by setting `SPA_WAVE_1_ENABLED=False` in the active deployment configuration.
3. Redeploy or restart only the service(s) needed to reload Flask config.
4. Verify the rollback before announcing recovery.

---

## 4. Verification After Rollback

Verify:

- [ ] `GET /` no longer redirects to `/app/dashboard`
- [ ] `GET /user` no longer redirects to `/app/systems`
- [ ] `GET /user/<serial_number>` no longer redirects to `/app/systems?serial=...`
- [ ] `GET /history` no longer redirects to `/app/history`
- [ ] `GET /backup` no longer redirects to `/app/backup`
- [ ] legacy pages render or require login in the normal pre-wave way
- [ ] `/app` still serves the SPA shell for debugging and isolated validation
- [ ] `/health` and `/api/health` remain healthy

---

## 5. Evidence To Capture

- [ ] timestamp of activation
- [ ] timestamp rollback started
- [ ] environment/config diff showing `SPA_WAVE_1_ENABLED` change
- [ ] screenshots or curl output for the failing route before rollback
- [ ] screenshots or curl output for the recovered route after rollback
- [ ] relevant app and gateway logs for the failure window

---

## 6. Safe Re-Enable Criteria

Do not re-enable the wave until all are true:

- [ ] the root cause is identified
- [ ] the failing path has a code fix or config fix
- [ ] the relevant SPA/gateway/deep-link regression tests pass
- [ ] the staging checklist passes again
- [ ] a narrower retry plan is chosen if the previous activation scope was too broad

---

## 7. Commands And Checks To Re-Run

Recommended validation before retrying:

```bash
pytest tests/test_spa_serving_and_wave1_redirects.py tests/test_gateway_proxy_contract.py tests/test_app_bootstrap.py -q
docker compose --env-file .env.prod -f docker-compose.yml -f docker-compose.prod.yml config
docker compose --env-file .env.prod --profile full -f docker-compose.yml -f docker-compose.prod.yml config
```

Operational spot checks after retry:

- [ ] `/gateway/health`
- [ ] `/health`
- [ ] `/api/health`
- [ ] `/app`
- [ ] `/app/dashboard`
- [ ] `/user/<serial_number>`

---

## 8. Scope Reminder

This rollback checklist is for route-wave activation and compatibility redirects.

If the problem is instead:

- missing frontend assets
- gateway misconfiguration
- broken release downloads
- migration/startup failure

then use this checklist together with:

- `STAGING_VERIFICATION_CHECKLIST.md`
- `BACKEND_STARTUP_RUNBOOK.md`
