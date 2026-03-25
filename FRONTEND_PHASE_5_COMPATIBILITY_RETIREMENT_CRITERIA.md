# Frontend Phase 5 — Compatibility Route Retirement Criteria

Updated: March 25, 2026

## Purpose

Define explicit retirement criteria for each legacy compatibility route so the deprecation timeline is measurable and operators have clear signal when to migrate off legacy paths.

## Route Retirement Sequence

### Wave 1 Routes (Enabled via `SPA_WAVE_1_ENABLED=true`)

These routes are redirected to SPA equivalents when wave-1 is active:
- `/` → `/app/dashboard`
- `/user` → `/app/systems`
- `/user/<serial_number>` → `/app/systems?serial=<serial_number>`
- `/history` → `/app/history`
- `/backup` → `/app/backup`

**Retirement Criteria for Wave 1 Routes:**
- Wave-1 redirects have been active for 2+ weeks in production
- Zero 5xx errors on redirect endpoints  
- Support volume shows <1 ticket/week asking about legacy paths
- Monitoring shows <5% traffic to redirected routes in final week
- All operators have been notified and dashboard/history/backup workflows verified on SPA

**Retirement Date:** 2 weeks post-activation + approval from ops team

**Retirement Action:**
- Remove redirect handlers from `/`, `/user`, `/user/<serial_number>`, `/history`, `/backup`
- Remove associated legacy Jinja templates
- Retain static file routing for any legacy assets until final cleanup

---

### Remaining Compatibility Routes (No redirect, kept as fallback)

These remain as HTML fallback pages for the initial cutover window:

#### `/login` and `/logout`
**Purpose:** Session-auth compatibility for operators still using legacy HTML routes

**Retirement Criteria:**
- Both web-session routes AND all other compatibility HTML routes are retired
- No production traffic to session-only auth (all users on SPA JWT)
- JWT refresh interceptor is validated in production for ≥4 weeks

**Retirement Date:** After dual-mode auth is no longer needed (2-3 months post-wave-1)

**Retirement Action:**
- Remove `/login` and `/logout` POST/GET handlers
- Keep `/login` as informational redirect to SPA login only
- Remove web session middleware entirely if no other Jinja routes remain

#### `/admin` and `/features`
**Purpose:** Aggregated compatibility surfaces for operators needing distributed SPA workflows in one place

**Retention Criteria:**
Keep as compatibility pages through post-cutover stabilization (3-6 months), then revisit based on:
- Support tickets mentioning `/admin` or `/features` per week
- Traffic ratio: legacy compat pages vs SPA equivalent modules
- Operator feedback on distributed vs aggregated workflow preference

**Retirement Options:**
1. Full deprecation: Remove both routes, force navigation to specific SPA modules
2. Lightweight migration: Replace with informational landing page linking to SPA modules
3. Extended compatibility: Keep as-is if support volume stays low

**Retirement Decision Window:** 6-month mark post-wave-1 activation

---

## Monitoring and Rollback Signals

### Pre-Retirement Monitoring (Active Until Retirement Date)

Track these metrics weekly:
- HTTP request count by path (legacy vs SPA)
- 4xx/5xx error rates by path
- Session auth success/failure rates
- Response times (legacy vs SPA equivalents)
- Browser console errors on redirected routes

### Automatic Rollback Triggers

Revert wave-1 redirects immediately if any of these occur:
- 5xx error rate on redirected route exceeds 2% for 1 hour
- Auth failure rate exceeds 5% on SPA
- Support ticket volume spikes to >5 per day mentioning redirects
- Operator-reported data loss or state wipeout on SPA

**Rollback Procedure:**
1. Set `SPA_WAVE_1_ENABLED=false`
2. Restart application
3. Verify legacy Jinja routes are again accepting traffic
4. Capture error logs and operator feedback
5. Fix underlying SPA parity/auth issue before re-attempting wave

**Target Rollback Time:** <5 minutes

---

## Phase 5 Cutover Execution Checklist

Before advancing each wave, validate:

- [ ] Production SPA build is current and tested
- [ ] `/app` hard-refresh serving works on clean browser (no cache)
- [ ] SPA auth (JWT + refresh) works end-to-end in production-like environment
- [ ] Tenant context propagation is correct via `X-Tenant-Slug` header
- [ ] Legacy Jinja routes' `require_web_permission` still gates access
- [ ] Audit logging captures both legacy and SPA route access
- [ ] Rollback toggle (`SPA_WAVE_1_ENABLED`) is tested and documented
- [ ] Operator runbook created for emergency rollback
- [ ] Support team trained on new SPA URLs and rollback procedures
- [ ] Monitoring dashboard shows legacy vs SPA traffic split

---

## Post-Retirement Cleanup

After each route is retired:

1. Remove deprecated route handlers from web blueprint
2. Remove associated Jinja templates from version control
3. Update operator documentation and help center
4. Close any GitHub issues/PRs related to legacy routes
5. Archive cutover notes in ARCHIVE/ folder

---

## Success Criteria (Full Migration Complete)

The Phase 5 frontend migration is considered **successful** when:

✅ All wave-1 routes are retired and removed from codebase  
✅ `/login` and `/logout` are removed or converted to informational pages  
✅ `/admin` and `/features` are either retired or converted to SPA landing pages  
✅ 100% of operator traffic is on `/app/*` routes  
✅ No remaining Jinja templates for operational workflows  
✅ SPA backend compatibility is locked and tested  
✅ Legacy session-auth middleware is removed  
✅ All operators confirm workflows are working on SPA  
