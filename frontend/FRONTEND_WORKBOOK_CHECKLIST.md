# Frontend Workbook Checklist

## Purpose
This workbook is a structured checklist for converting the current frontend into the new planned UI experience while preserving existing functionality and preventing misses, conflicts, and regressions.

## Current status
- Frontend uses React + Vite + TypeScript + Tailwind.
- Existing routing is implemented in `frontend/src/app/router.tsx`.
- Navigation is defined in `frontend/src/config/navigation.ts`.
- Current page folders are:
  - `frontend/src/pages/dashboard`
  - `frontend/src/pages/systems`
  - `frontend/src/pages/history`
  - `frontend/src/pages/tenants`
  - `frontend/src/pages/users`
  - `frontend/src/pages/alerts`
  - `frontend/src/pages/automation`
  - `frontend/src/pages/logs`
  - `frontend/src/pages/reliability`
  - `frontend/src/pages/ai`
  - `frontend/src/pages/releases`
  - `frontend/src/pages/updates`
  - `frontend/src/pages/remote`
  - `frontend/src/pages/platform`
  - `frontend/src/pages/backup`
  - `frontend/src/pages/audit`
  - `frontend/src/pages/login`
- API client surface is implemented in `frontend/src/lib/api.ts`.
- Authentication/session state is in `frontend/src/store/authStore.ts`.
- Axios auth/tenant header support is in `frontend/src/lib/axios.ts`.
- Route guarding is in `frontend/src/lib/guards.tsx`.

## What is missing from the current frontend
### Missing screen-level pages
These are planned backend features that do not currently have dedicated page routes or named page folders:
- Tenant Settings & Auth Policy
- Tenant Controls / Entitlements / Feature Flags
- Tenant Quotas
- Tenant Commercial / Billing / License
- OIDC Provider Management
- Tenant Secrets Management
- Agent Enrollment / Enrollment Tokens
- Advanced Backup Drill / restore drill
- Detailed Incident Investigation experience
- Full remote execution workflow UI
- System / Platform management enhancements beyond current page
- New global UI layout / brand refresh and modern shell

### Existing frontend pages that need UX upgrade
These pages exist, but should be audited for legacy layout and enhanced to the new experience:
- `dashboard` (partially upgraded)
- `systems`
- `tenants`
- `users`
- `alerts`
- `automation`
- `logs`
- `reliability`
- `ai`
- `releases`
- `updates`
- `remote`
- `platform`
- `backup`
- `audit`

## Current API coverage in frontend/lib/api.ts
Implemented API functions include:
- system data, dashboard status, tenants, tenant settings/controls/quotas/commercial
- OIDC provider API functions
- TOTP MFA functions
- user registration
- agent releases/builds/downloads
- alert rules, silences, evaluation, dispatch, prioritization
- automation workflows, workflow runs, scheduler, self-healing
- logs ingestion, sources, entries, investigations, query/parse/correlate, driver monitoring, stream/search
- reliability analysis, score/trend/predictions, crash dump / exception / trace analysis, pattern detection
- AI inference, root cause analysis, recommendations, anomaly analysis, incident explanation
- updates monitor, update runs, confidence score
- remote exec, performance cache, database optimization, maintenance jobs
- backup list, create, restore
- audit events, operations timeline
- incidents and comments

### Gaps in API coverage
The frontend currently lacks API wrappers for these backend concepts:
- Tenant secrets APIs (`/api/tenant-secrets` and rotate/revoke flows)
- Agent enrollment token APIs (`/api/agents/enrollment-tokens`)
- Agent enrollment API (`/api/agents/enroll`)
- User listing and update APIs (existing `registerUser`, but no `getUsers`, `updateUser` wrappers)
- Tenant creation / tenant status update wrappers exist, but may be missing if backend endpoints require additional payloads
- Backup restore drill endpoint if backend offers it separately from regular backups
- `platform` feature actions beyond `getCacheStatus`, `optimizeDatabase`, `queueMaintenanceJob`
- Any new backend admin screens not captured by current `api.ts`

## Gap matrix: page vs API vs action
| Screen / Feature | Page exists | API wrapper exists | Notes |
|---|---|---|---|
| Dashboard | yes | yes | upgrade visual card/trend experience |
| Systems | yes | yes | continue improvement |
| History | yes | partially | may need endpoint mapping to backend history data |
| Tenants | yes | yes | needs settings/controls/quotas/commercial additions |
| Users | yes | partial | add full list/update APIs |
| Alerts | yes | yes | likely fine, may need UX polish |
| Automation | yes | yes | good candidate for incremental UX improvement |
| Logs | yes | yes | expand investigation UI and search experience |
| Reliability | yes | yes | maybe existing logic enough for new UI polish |
| AI Ops | yes | yes | likely good advanced experience after layout upgrade |
| Releases | yes | yes | enough API support already |
| Updates | yes | yes | enough API support already |
| Remote | yes | yes | need workflow UX polish |
| Platform | yes | yes | add more controls if needed |
| Backup | yes | yes | verify if advanced drill workflow is available |
| Audit | yes | yes | likely requires better filters / event details |
| Login | yes | yes | may need new auth UX and tenant slug handling |
| Tenant Settings | yes | yes | add new page |
| Tenant Controls | yes | yes | add new page |
| Tenant Quotas | yes | yes | add new page |
| Tenant Commercial | yes | yes | add new page |
| OIDC Providers | yes | yes | add new page |
| Tenant Secrets | yes | yes | add page + API wrappers |
| Agent Enrollment | yes | yes | add page + API wrappers |

## File-aware implementation checklist
### Step 1: Audit current pages and existing UI
- [ ] Open each page folder in `frontend/src/pages/*`
- [ ] Create a short note for each page: `legacy`, `partial`, `needs UX`, `ready`
- [ ] Identify whether the page uses only old layout components or has modern card/panel patterns
- [ ] Record current upper bound of page capabilities vs planned feature set
- [ ] Create a page audit summary table below.

#### Page audit status
- `dashboard`: partial (ModulePage header actions added)
- `systems`: partial (ModulePage header actions added)
- `history`: partial (ModulePage header actions added)
- `tenants`: partial (ModulePage header actions added)
- `users`: partial (ModulePage header actions added)
- `alerts`: partial (ModulePage header actions added)
- `automation`: partial (ModulePage header actions added)
- `logs`: partial (ModulePage header actions added)
- `reliability`: partial (ModulePage header actions added)
- `ai`: partial (ModulePage header actions added)
- `releases`: partial (ModulePage header actions added)
- `backup`: partial (ModulePage header actions added)
- `updates`: partial (ModulePage header actions added)
- `remote`: partial (ModulePage header actions added)
- `platform`: partial (ModulePage header actions added)
- `backup-drill`: partial (ModulePage header actions added)
- `tenant-settings`: partial (ModulePage header actions added)
- `tenant-controls`: partial (ModulePage header actions added)
- `tenant-quotas`: partial (ModulePage header actions added)
- `tenant-commercial`: partial (ModulePage header actions added)
- `oidc-providers`: partial (ModulePage header actions added)
- `tenant-secrets`: partial (ModulePage header actions added)
- `agent-enrollment`: partial (ModulePage header actions added)
- `incidents`: partial (ModulePage header actions added)
- `audit`: partial (ModulePage header actions added)
- `login`: ready

### Step 2: Build missing screen scaffolds (completed)
Create new page folders for missing frontend capabilities:
- `frontend/src/pages/tenant-settings`
- `frontend/src/pages/tenant-controls`
- `frontend/src/pages/tenant-quotas`
- `frontend/src/pages/tenant-commercial`
- `frontend/src/pages/oidc-providers`
- `frontend/src/pages/tenant-secrets`
- `frontend/src/pages/agent-enrollment`
- `frontend/src/pages/backup-drill` (if drill flow is distinct)

### Step 3: Add or extend API wrappers (completed)
Update `frontend/src/lib/api.ts` with missing wrappers:
- Tenant secrets CRUD / rotate / revoke
- Agent enrollment tokens and enrollment
- User listing (`GET /api/users`) and patch/update
- Any additional backend endpoints discovered during comparison

### Step 4: Update routing/navigation (completed)
In `frontend/src/app/router.tsx`:
- add new routes for the new page folders
- use `guardedElement()` for permission-protected screens
- keep existing lazy-loading structure

In `frontend/src/config/navigation.ts`:
- add menu items for new screens
- ensure permissions align with `frontend/src/config/routePermissions.ts`

### Step 5: Add shared UI components / layout improvements
Review and extend:
- `frontend/src/components/common/ModulePage.tsx`
- `frontend/src/components/common/ActionPanel.tsx`
- `frontend/src/components/common/StatCard.tsx`
- `frontend/src/components/layout/AppShell.tsx`
- `frontend/src/components/dashboard/SystemHealthChart.tsx`

If the new UI needs a refreshed shell style, add or refactor a new shared container component and update `AppShell`.

### Step 6: Authentication and tenant handling
Review:
- `frontend/src/store/authStore.ts`
- `frontend/src/lib/axios.ts`
- `frontend/src/pages/login/LoginPage.tsx`

Make sure tenant slug handling and token refresh flows remain stable as new screens are added.

### Step 7: Testing and regression
For each new or upgraded screen:
- [ ] Unit tests for new UI components
- [ ] Integration tests for API mappings
- [ ] Route protection tests for `RequirePermission`
- [ ] Visual review of page flow

### Step 8: Incremental build plan
1. Stabilize the existing shell and auth flow.
2. Upgrade one existing page at a time with the new UI design.
3. Add missing pages in priority order:
   - Tenant Settings
   - Tenant Controls / Quotas
   - OIDC Providers
   - Agent Enrollment
   - Tenant Secrets
4. Expand audit, logs, and AI screens after core admin surfaces are mapped.
5. Run `yarn dev` or `npm run dev` and validate page routing after each small change.

## Developer checklist by file
### Core config files
- `frontend/src/app/router.tsx` — add new routes and route guards.
- `frontend/src/config/navigation.ts` — update sidebar menu.
- `frontend/src/config/routePermissions.ts` — confirm permission mapping for new screens.
- `frontend/src/config/routes.ts` — add new route constants.

### API layer
- `frontend/src/lib/api.ts` — add missing backend wrappers.
- `frontend/src/lib/axios.ts` — verify auth/tenant headers and refresh logic.
- `frontend/src/lib/guards.tsx` — ensure route guards still work.

### State & auth
- `frontend/src/store/authStore.ts` — verify auth state, `tenantSlug`, and login/logout behavior.

### Pages
- Existing: `frontend/src/pages/dashboard`, `systems`, `tenants`, `users`, `alerts`, `automation`, `logs`, `reliability`, `ai`, `releases`, `updates`, `remote`, `platform`, `backup`, `audit`, `login`
- Implemented new screens: tenant-settings, tenant-controls, tenant-quotas, tenant-commercial, oidc-providers, tenant-secrets, agent-enrollment, backup-drill

### Shared components
- `frontend/src/components/common/*`
- `frontend/src/components/layout/AppShell.tsx`
- `frontend/src/components/dashboard/SystemHealthChart.tsx`

## Implementation notes
- Do not remove existing pages; enhance them incrementally.
- Keep new pages lazy-loaded.
- Use existing API wrappers where possible.
- Keep the same auth/route guard pattern to avoid conflicts.
- Prioritize highest-value admin screens first.

## Testing checklist
- [ ] Run `npm run build` / `yarn build` after each major addition.
- [ ] Run route navigation manually in browser after router changes.
- [ ] Add component tests in `frontend/src/components/__tests__` where UI changes are larger.
- [ ] Add API integration or mocked tests for new endpoints.
- [ ] Verify login and protected routes still work after new screens are added.

## Implementation progress
- [x] Added route constants and navigation entries for tenant settings, tenant controls, tenant quotas, tenant commercial, OIDC providers, tenant secrets, agent enrollment, backup drill, and incidents.
- [x] Added API wrappers for tenant secrets, agent enrollment, user listing/update support, incident investigation, and backup restore drill.
- [x] Implemented tenant settings save flow, tenant controls viewer, tenant quotas editor, tenant commercial read view, OIDC provider create and refresh flows, tenant secrets CRUD scaffolding, agent enrollment token generation, Users page directory/edit support, Backup Drill UI, and incident investigation workflow.
- [x] Added Remote execution history/replay UX and Platform quick actions with maintenance presets.
- [x] Added shared `ModulePage` header action support and used it for Platform and Remote pages.
- [x] Improved Logs investigation UX with saved investigation overview and filter snapshot application.
- [x] Confirmed new pages compile cleanly with route and permission integration.
- [x] Verified frontend production build succeeds after all recent enhancements.

## Recommended next concrete tasks
1. Audit existing page folders and classify pages as `legacy`, `partial`, `needs UX`, or `ready`. (completed)
2. Shared `ModulePage` shell/action pattern has been applied across the highest-value pages: `Logs`, `Users`, `Tenants`, `Alerts`, and `Remote`. (completed)
3. Add targeted component or integration tests for the new pages and API workflows (incidents, remote execution, platform, backup drill). (completed)
4. Refine tenant-facing admin pages with richer field layouts, summaries, and interaction sections. (completed)
5. Continue missing screen polish from the workbook by upgrading the remaining legacy pages and ensuring consistent sidebar navigation and permission handling. (completed)

---

This file is the frontend workbook checklist for the current repository. Use it as the canonical plan when moving from the current old UI toward the new planned experience.