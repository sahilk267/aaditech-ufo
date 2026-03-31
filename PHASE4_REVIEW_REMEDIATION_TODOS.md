# Phase 4 Review Remediation Todos

Updated: March 31, 2026

## Purpose

This checklist turns the Phase 4 review findings into concrete follow-up work.

---

## P0 Runtime Fixes

- [x] Fix base Compose Redis wiring so app and Redis health checks use the same passworded connection settings.
- [x] Improve app health reporting so Redis failures show up as degraded instead of looking fully healthy.
- [x] Tighten SPA asset cache behavior so only hashed build assets get long-lived caching.

---

## P1 Deployment-Path Cleanup

- [x] Remove the unused production `frontend` container from the runtime Compose path so production delivery matches the actual app-served SPA architecture.
- [x] Re-validate production compose rendering after the Compose/runtime cleanup.
- [x] Re-review staging checklist wording against the cleaned production shape.

---

## P2 Docs And Tracking Truth Alignment

- [x] Correct stale deployment notes in `FRONTEND_PHASE_1_TO_5_TRACKING.md`.
- [x] Update Phase 4 tracking/reporting files with the remediation results and validation output.
- [x] Add a short note about the current production SPA delivery model so future work does not reintroduce the unused-frontend-container drift.

---

## Validation Targets

- [x] `docker compose -f docker-compose.yml config`
- [x] `docker compose --profile full -f docker-compose.yml -f docker-compose.dev.yml config`
- [x] `docker compose --env-file .env.prod -f docker-compose.yml -f docker-compose.prod.yml config`
- [x] `pytest tests/test_app_bootstrap.py tests/test_spa_serving_and_wave1_redirects.py tests/test_gateway_proxy_contract.py -q`

---

## Notes

- The review found one runtime bug (Redis auth mismatch), one cache-policy bug (non-hashed asset overcaching), one deployment-shape conflict (unused prod frontend container), and stale frontend deployment tracking text.
- Validation completed on March 31, 2026 and the linked tracking files were updated in the same remediation pass.
