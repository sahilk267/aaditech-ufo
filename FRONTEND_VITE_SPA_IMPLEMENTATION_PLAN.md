# AADITECH UFO - FRONTEND VITE SPA IMPLEMENTATION PLAN

Updated: March 24, 2026

## 1. Objective

Build a new production-grade frontend as a Vite SPA without replacing the existing Flask backend.

This plan is designed to:

- preserve current backend APIs and RBAC behavior
- avoid routing, auth, and deployment conflicts
- cover all currently implemented backend features
- define exact frontend module boundaries and dependencies
- provide a phased migration path from Jinja templates to SPA

This document is the source of truth for the new frontend implementation.

---

## 2. Final Recommendation

Use this stack:

- Vite
- React 18
- TypeScript
- React Router
- TanStack Query
- React Hook Form
- Zod
- Tailwind CSS
- shadcn/ui
- Recharts
- Axios
- Zustand
- date-fns
- clsx
- lucide-react

Reason:

- Fast build and low operational complexity
- Strong typing across API contracts
- Better handling for data-heavy operator screens
- Better long-term maintainability than Jinja template growth
- Ideal for dashboards, tables, filters, workflows, log explorers, and AI panels

---

## 3. Non-Negotiable Architecture Rules

1. Flask remains the backend system of record.
2. Database access remains server-side only.
3. SPA never talks to the database directly.
4. SPA uses Flask APIs only.
5. Existing Jinja pages remain available during migration.
6. Authentication and RBAC remain enforced on backend, not only in frontend.
7. Frontend route guards are UX helpers only; backend authorization is authoritative.
8. Deployment must avoid same-path conflict with existing web routes.

---

## 4. Deployment Strategy

### 4.1 Recommended production topology

Serve the SPA under a dedicated prefix:

- `/app` for the SPA shell
- `/api/*` continues to be served by Flask API routes
- existing Jinja pages remain at `/`, `/user`, `/admin`, `/history`, `/backup`, `/agent/releases`, `/features`

This avoids route collisions with existing browser routes.

### 4.2 Development topology

- Vite dev server on port `5173`
- Flask on port `5000`
- Vite proxy forwards `/api`, `/health`, and any required auth endpoints to Flask

### 4.3 Production migration phases

Phase 1:

- deploy SPA under `/app`
- keep Jinja pages active

Phase 2:

- migrate operator workflows to `/app/*`
- keep legacy pages as fallback

Phase 3:

- optionally replace selected Jinja pages with redirects to SPA

---

## 5. Dependency Plan

### 5.1 Runtime dependencies

```json
{
  "react": "^18.3.1",
  "react-dom": "^18.3.1",
  "react-router-dom": "^6.30.0",
  "@tanstack/react-query": "^5.68.0",
  "axios": "^1.8.4",
  "zustand": "^5.0.3",
  "react-hook-form": "^7.55.0",
  "zod": "^3.24.2",
  "@hookform/resolvers": "^3.10.0",
  "recharts": "^2.15.1",
  "date-fns": "^4.1.0",
  "clsx": "^2.1.1",
  "tailwind-merge": "^2.6.0",
  "lucide-react": "^0.487.0"
}
```

### 5.2 Dev dependencies

```json
{
  "vite": "^6.2.0",
  "typescript": "^5.8.2",
  "@vitejs/plugin-react": "^4.3.4",
  "tailwindcss": "^3.4.17",
  "postcss": "^8.5.3",
  "autoprefixer": "^10.4.21",
  "eslint": "^9.22.0",
  "@typescript-eslint/eslint-plugin": "^8.27.0",
  "@typescript-eslint/parser": "^8.27.0",
  "prettier": "^3.5.3",
  "vitest": "^3.0.9",
  "@testing-library/react": "^16.3.0",
  "@testing-library/jest-dom": "^6.6.3",
  "@testing-library/user-event": "^14.6.1",
  "msw": "^2.7.3"
}
```

### 5.3 Optional dependencies

- `@monaco-editor/react` for JSON/script editors
- `framer-motion` for polished transitions
- `@tanstack/react-table` for heavy data tables
- `echarts` or `apache-echarts` if reliability/log visualization outgrows Recharts

---

## 6. Frontend Project Structure

```text
frontend/
  index.html
  package.json
  tsconfig.json
  vite.config.ts
  postcss.config.js
  tailwind.config.ts
  src/
    main.tsx
    app/
      App.tsx
      router.tsx
      providers.tsx
      queryClient.ts
    assets/
    config/
      env.ts
      routes.ts
      permissions.ts
    lib/
      axios.ts
      auth.ts
      queryKeys.ts
      format.ts
      guards.ts
      download.ts
    store/
      authStore.ts
      uiStore.ts
    types/
      auth.ts
      tenants.ts
      systems.ts
      alerts.ts
      automation.ts
      logs.ts
      reliability.ts
      ai.ts
      agentReleases.ts
      dashboard.ts
      common.ts
    components/
      layout/
      tables/
      charts/
      forms/
      feedback/
      badges/
      dialogs/
    features/
      auth/
      dashboard/
      systems/
      tenants/
      users/
      alerts/
      automation/
      logs/
      reliability/
      ai/
      updates/
      releases/
      remote/
      platform/
    pages/
      login/
      app-shell/
      dashboard/
      systems/
      tenants/
      users/
      alerts/
      automation/
      logs/
      reliability/
      ai/
      releases/
      remote/
      platform/
      not-found/
```

---

## 7. Core Frontend Infrastructure

### 7.1 Auth model

Primary auth for SPA:

- JWT login using `POST /api/auth/login`
- refresh using `POST /api/auth/refresh`
- logout using `POST /api/auth/logout`
- current user using `GET /api/auth/me`

Store:

- access token in memory store
- refresh token in secure storage strategy selected by security policy

Recommended implementation:

- keep access token in memory
- keep refresh token in `localStorage` only if current threat model allows
- if stricter security is desired later, move refresh handling to backend-set httpOnly cookies

### 7.2 Tenant routing model

Every SPA API request should send:

- `Authorization: Bearer <access_token>` when authenticated
- `X-Tenant-Slug: <tenant_slug>` when tenant context is explicitly selected

Tenant source order in SPA:

1. selected tenant in auth/session store
2. default tenant from login context
3. fallback tenant selector for admin flows

### 7.3 RBAC model

Backend remains authoritative.

Frontend permission usage:

- hide inaccessible navigation items
- disable unavailable actions
- show permission rationale in UI
- route guard based on `user.permissions`

Do not rely on frontend permissions for security.

### 7.4 Query/data model

Use TanStack Query for:

- caching
- stale refresh
- background refetch
- mutation invalidation
- retry control

Recommended stale times:

- dashboard status: 30-45 seconds
- system lists: 30 seconds
- alert rules/workflows: 60 seconds
- tenants/users/roles: 60-120 seconds
- release list: 60 seconds

---

## 8. Backend-to-Frontend Domain Map

### 8.1 Auth and identity

API routes:

- `POST /api/auth/login`
- `POST /api/auth/refresh`
- `POST /api/auth/logout`
- `GET /api/auth/me`
- `GET /api/auth/rbac-check`

DB dependencies:

- `organizations`
- `users`
- `roles`
- `permissions`
- `user_roles`
- `role_permissions`
- `revoked_tokens`

Frontend modules:

- login page
- auth provider
- route guards
- current user profile menu
- permission-aware navigation

### 8.2 Tenant management

API routes:

- `GET /api/tenants`
- `POST /api/tenants`
- `PATCH /api/tenants/:tenant_id/status`

DB dependencies:

- `organizations`

Frontend modules:

- tenant list page
- create tenant modal
- activate/deactivate action
- tenant summary cards

### 8.3 System inventory and dashboard

API routes:

- `POST /api/submit_data`
- `GET /api/status`
- `GET /api/dashboard/status?host_name=`
- `GET /api/performance/cache/status`
- `POST /api/database/optimize`
- `GET /api/systems` via web bridge route
- `GET /api/system/:system_id` via web bridge route
- `POST /manual_submit`

DB dependencies:

- `system_data`

Frontend modules:

- overview dashboard
- host list table
- host detail page
- manual submit trigger
- cache/optimization status panel

### 8.4 Alerting

API routes:

- `GET /api/alerts/rules`
- `POST /api/alerts/rules`
- `PATCH /api/alerts/rules/:rule_id`
- `POST /api/alerts/evaluate`
- `GET /api/alerts/silences`
- `POST /api/alerts/silences`
- `DELETE /api/alerts/silences/:silence_id`
- `POST /api/alerts/dispatch`
- `POST /api/alerts/prioritize`

DB dependencies:

- `alert_rules`
- `alert_silences`
- `audit_events`

Frontend modules:

- rule list
- create/edit rule drawer
- alert evaluation runner
- active alerts screen
- silence scheduler
- notification dispatch tester
- prioritization board

### 8.5 Automation

API routes:

- `GET /api/automation/workflows`
- `POST /api/automation/workflows`
- `POST /api/automation/evaluate`
- `POST /api/automation/workflows/:workflow_id/execute`
- `POST /api/automation/services/status`
- `POST /api/automation/services/dependencies`
- `POST /api/automation/services/failures`
- `POST /api/automation/services/execute`
- `GET /api/automation/scheduled-jobs`
- `POST /api/automation/scheduled-jobs`
- `POST /api/automation/self-heal`

DB dependencies:

- `automation_workflows`
- `scheduled_jobs`
- `audit_events`

Frontend modules:

- workflow list
- workflow editor
- workflow execution log panel
- service diagnostics panel
- scheduler page
- self-healing dashboard

### 8.6 Logs and event operations

API routes:

- `POST /api/logs/ingest`
- `POST /api/logs/events/query`
- `POST /api/logs/parse`
- `POST /api/logs/events/correlate`
- `POST /api/logs/drivers/monitor`
- `POST /api/logs/drivers/errors`
- `POST /api/logs/events/stream`
- `POST /api/logs/search`

DB dependencies:

- no first-class log persistence model currently exposed in SQLAlchemy models shown here
- depends on service-layer adapters and runtime responses
- audit trail persists in `audit_events`

Frontend modules:

- log source query page
- parsed event inspector
- correlation explorer
- event stream console
- driver monitor page
- log search page

### 8.7 Reliability and crash intelligence

API routes:

- `POST /api/reliability/history`
- `POST /api/reliability/crash-dumps/parse`
- `POST /api/reliability/exceptions/identify`
- `POST /api/reliability/stack-traces/analyze`
- `POST /api/reliability/score`
- `POST /api/reliability/trends/analyze`
- `POST /api/reliability/predictions/analyze`
- `POST /api/reliability/patterns/detect`

DB dependencies:

- current implementation appears service/adaptor driven
- audit trail persists in `audit_events`

Frontend modules:

- reliability timeline page
- crash dump analyzer page
- exception classifier page
- stack trace view
- score and trend dashboard
- reliability pattern explorer

### 8.8 AI and operational intelligence

API routes:

- `POST /api/ai/ollama/infer`
- `POST /api/ai/root-cause/analyze`
- `POST /api/ai/recommendations/generate`
- `POST /api/ai/troubleshooting/assist`
- `POST /api/ai/learning/feedback`
- `POST /api/ai/anomaly/analyze`
- `POST /api/ai/incident/explain`
- `POST /api/ai/confidence/score`

DB dependencies:

- no dedicated AI SQL models exposed in current model file
- audit trail persists in `audit_events`

Frontend modules:

- AI playground
- root cause analyzer
- recommendations view
- troubleshooting assistant chat panel
- learning feedback form
- anomaly explainer panel
- incident explainer panel
- confidence scoring panel

### 8.9 Updates and remote ops

API routes:

- `POST /api/updates/monitor`
- `POST /api/remote/exec`
- `POST /api/jobs/maintenance`

DB dependencies:

- audit trail persists in `audit_events`
- maintenance may affect `revoked_tokens` and `audit_events`

Frontend modules:

- update monitor page
- remote exec console
- maintenance jobs control panel

### 8.10 Agent release lifecycle

API routes:

- `GET /api/agent/releases`
- `POST /api/agent/releases/upload`
- `GET /api/agent/releases/download/:filename`
- `GET /api/agent/releases/policy`
- `PUT /api/agent/releases/policy`
- `GET /api/agent/releases/guide?current_version=`

Web routes:

- `GET /agent/releases`
- `POST /agent/releases/upload`
- `GET /agent/releases/download/:filename`
- `GET /features/download-built-agent`
- `POST /features/build-agent`

DB dependencies:

- release artifacts are filesystem-based
- policy is filesystem-based
- audit trail persists in `audit_events`

Frontend modules:

- releases list
- release upload form
- release policy editor
- guided update viewer
- agent build trigger screen

---

## 9. Complete SPA Route Map

Recommended SPA route tree:

```text
/app
/app/login
/app/dashboard
/app/systems
/app/systems/:systemId
/app/tenants
/app/users
/app/alerts
/app/alerts/rules
/app/alerts/silences
/app/alerts/priorities
/app/automation
/app/automation/workflows
/app/automation/services
/app/automation/scheduled-jobs
/app/automation/self-heal
/app/logs
/app/logs/query
/app/logs/search
/app/logs/stream
/app/logs/drivers
/app/reliability
/app/reliability/history
/app/reliability/crash-dumps
/app/reliability/exceptions
/app/reliability/trends
/app/ai
/app/ai/playground
/app/ai/root-cause
/app/ai/recommendations
/app/ai/troubleshooting
/app/ai/incidents
/app/releases
/app/releases/policy
/app/updates
/app/remote
/app/platform
/app/platform/cache
/app/platform/maintenance
/app/platform/audit
```

---

## 10. Permission Map for Frontend Guards

Current permission codes discovered in backend and seed flow:

- `dashboard.view`
- `tenant.manage`
- `system.submit`
- `backup.manage`
- `automation.manage`

Frontend route guard map:

- dashboard, systems, history, releases, reliability read screens: `dashboard.view`
- tenant management, user management, release policy, agent build: `tenant.manage`
- manual submit actions: `system.submit`
- backup actions: `backup.manage`
- alerts, automation, logs, AI ops, updates, remote ops, maintenance: `automation.manage`

Note:

The backend currently uses `automation.manage` as the primary permission for many advanced operational APIs. The SPA should reflect that exactly unless backend permissions are later split into finer scopes.

---

## 11. Page-by-Page Implementation Plan

### 11.1 Login page

Features:

- tenant slug input
- email/password login
- token storage
- bootstrap current user state via `/api/auth/me`

API calls:

- `POST /api/auth/login`
- `GET /api/auth/me`

### 11.2 Dashboard page

Features:

- system counts
- aggregate health cards
- host quick links
- cache hit indicator if dashboard aggregate API used

API calls:

- `GET /api/status`
- `GET /api/dashboard/status?host_name=`
- `GET /api/systems` bridge

### 11.3 Systems pages

Features:

- host inventory table
- host detail panel
- manual submit

API calls:

- `GET /api/systems`
- `GET /api/system/:id`
- `POST /manual_submit`

### 11.4 Tenants page

Features:

- tenant list
- create tenant
- toggle active state

API calls:

- `GET /api/tenants`
- `POST /api/tenants`
- `PATCH /api/tenants/:id/status`

### 11.5 Users page

Features:

- tenant user table
- create user/admin
- role assignments
- active/inactive badges

API calls:

- `POST /features/create-user` can be used during transition
- preferred long-term backend enhancement: dedicated user CRUD APIs

Important note:

There is no complete REST user-management API surface yet. The current create-user flow exists as a web form endpoint in Flask. For the SPA to fully own user management, backend should add:

- `GET /api/users`
- `POST /api/users`
- `PATCH /api/users/:id`
- `GET /api/roles`

These are recommended backend prerequisites for a complete SPA user management module.

### 11.6 Alerts pages

Features:

- rules table
- create/edit modal
- evaluate alerts
- silence list
- prioritize results
- dispatch action form

API calls:

- all alerting APIs listed in section 8.4

### 11.7 Automation pages

Features:

- workflow builder
- workflow execution
- service health tabs
- scheduler
- self-healing preview/result panel

API calls:

- all automation APIs listed in section 8.5

### 11.8 Logs pages

Features:

- event query
- raw response explorer
- parsed record table
- correlation clusters
- search with result previews
- stream batch cursor view
- driver inventory and errors view

API calls:

- all log APIs listed in section 8.6

### 11.9 Reliability pages

Features:

- history records
- score cards
- trend chart
- prediction chart
- pattern summary
- crash dump deep dive
- exception and stack trace output panels

API calls:

- all reliability APIs listed in section 8.7

### 11.10 AI pages

Features:

- prompt playground
- root cause analysis form
- recommendations generator
- troubleshooting assistant panel
- anomaly explanation viewer
- incident explanation viewer
- learning feedback capture
- confidence score widget

API calls:

- all AI APIs listed in section 8.8

### 11.11 Releases page

Features:

- release table
- upload release
- download release
- set target version policy
- view guide response for current version
- trigger server-side build if desired

API calls:

- all release APIs listed in section 8.10

### 11.12 Platform operations pages

Features:

- cache backend status
- DB optimize action
- maintenance job trigger
- audit activity viewer

API calls:

- `GET /api/performance/cache/status`
- `POST /api/database/optimize`
- `POST /api/jobs/maintenance`

Important note:

There is no audit-events listing API yet. If an audit viewer is required in SPA, backend should add a read-only paginated endpoint for `audit_events`.

---

## 12. Database Dependency Map

The SPA depends on these backend persistence objects indirectly through APIs.

### 12.1 Strongly exposed SQLAlchemy models

- `Organization`
- `User`
- `Role`
- `Permission`
- `RevokedToken`
- `AuditEvent`
- `AlertRule`
- `AlertSilence`
- `AutomationWorkflow`
- `ScheduledJob`
- `SystemData`

### 12.2 Filesystem-backed domain dependencies

- agent releases directory
- release policy JSON
- crash dump roots and runtime adapters

### 12.3 Frontend data ownership rule

Frontend owns:

- presentational state
- cached API data
- view filters
- local forms
- selected tenant/host/workflow context

Frontend does not own:

- canonical auth data
- RBAC truth
- database mutation rules
- file storage policies

---

## 13. Required Backend Additions for a Truly Complete SPA

The backend is strong, but a few gaps remain if the SPA must completely replace legacy UI.

These additions are recommended before final migration:

1. User management APIs
- `GET /api/users`
- `POST /api/users`
- `PATCH /api/users/:id`
- `GET /api/roles`

2. Backup APIs normalized under `/api`
- current backup operations are web-route based
- recommended:
  - `GET /api/backups`
  - `POST /api/backups`
  - `POST /api/backups/:filename/restore`

3. Audit events listing API
- `GET /api/audit-events`

4. Optional system history API normalization
- current history is mostly page-driven
- recommended:
  - `GET /api/systems/:id/history`

5. Optional role/permission reference APIs
- `GET /api/roles`
- `GET /api/permissions`

These changes are not blockers for starting the SPA, but they are required to fully retire old Jinja admin flows.

---

## 14. Zero-Conflict Delivery Plan

### Phase A - Foundation

Deliver:

- frontend project bootstrap
- auth shell
- layout
- route guards
- API client
- query provider

No backend conflict risk.

### Phase B - Current feature parity

Deliver:

- dashboard
- systems
- releases
- tenant list
- alerts shell
- automation shell

Keep existing Jinja pages active.

### Phase C - Operational depth

Deliver:

- logs
- reliability
- AI
- remote exec
- maintenance

### Phase D - Full migration

Deliver:

- user management via proper APIs
- backup module via proper APIs
- audit viewer
- deprecate legacy templates selectively

---

## 15. Suggested Delivery Order

1. Frontend foundation and auth
2. Dashboard and systems
3. Tenant and user management
4. Agent releases and release policy
5. Alerts
6. Automation and scheduled jobs
7. Logs and event explorer
8. Reliability and crash analysis
9. AI operations suite
10. Remote ops and platform tools
11. Backup and audit completion

---

## 16. Vite Configuration Plan

Recommended Vite proxy setup:

```ts
server: {
  port: 5173,
  proxy: {
    '/api': 'http://127.0.0.1:5000',
    '/health': 'http://127.0.0.1:5000',
    '/manual_submit': 'http://127.0.0.1:5000',
    '/agent': 'http://127.0.0.1:5000',
    '/features': 'http://127.0.0.1:5000'
  }
}
```

Production options:

1. Build SPA and serve static assets from Flask static folder under `/app`
2. Serve SPA separately from Nginx and reverse proxy `/api` to Flask

Preferred for this repo:

- Nginx serves SPA static bundle
- Flask serves API
- gateway routes `/app` to SPA bundle and `/api` to Flask

---

## 17. API Client Design

Create a shared axios client with:

- base URL from environment
- Authorization injection
- tenant header injection
- refresh-token retry interceptor
- 401 redirect to `/app/login`
- 403 permission error handling
- standard error normalization

Normalized API error shape in frontend:

```ts
type ApiError = {
  status: number;
  error: string;
  message?: string;
  details?: Record<string, string[]> | string;
};
```

---

## 18. Testing Plan

### 18.1 Frontend unit tests

- auth store
- route guards
- API adapters
- Zod schema parsing
- table/filter helpers

### 18.2 Integration tests

- login flow
- dashboard data load
- create tenant
- create alert rule
- create workflow
- upload release

### 18.3 Contract tests

- mock server contracts mirror Flask responses
- verify all required fields against real backend samples

### 18.4 E2E tests later

- Cypress or Playwright after route stability

---

## 19. UI/UX Design Direction

Use a more serious operator-console style, not plain CRUD Bootstrap.

Design direction:

- left navigation rail
- command center top bar
- contextual host/tenant selectors
- dense but readable tables
- split-pane diagnostics for logs and crash traces
- strong status color system
- high-contrast operational cards
- reusable filter bar patterns

Do not recreate the existing basic header-link layout.

---

## 20. Completion Definition

The new SPA is considered complete when:

1. all currently implemented backend capabilities have an SPA entry point or intentional admin-only exclusion
2. auth and RBAC work with no route leaks
3. all critical legacy pages have SPA replacements
4. deployment has no route conflict with Flask
5. tenant context is stable across all requests
6. release management, alerting, automation, logs, reliability, AI, remote ops, and platform ops are accessible from the SPA
7. missing backend APIs listed in section 13 are added or formally deferred

---

## 21. Final Build Decision

Build a new Vite SPA now.

Do not continue scaling the current Jinja frontend as the primary operator UI.

Keep Flask backend, keep current routes, migrate in phases, and use `/app` as the new frontend namespace.
