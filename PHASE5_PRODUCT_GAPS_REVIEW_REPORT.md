# Phase 5 Product Gaps Review Report

Updated: March 31, 2026

## Purpose

This report reviews the unchecked Phase 5 items against the current codebase and documentation.

It answers four questions for each item:

- what already exists
- what is still missing
- what conflict or risk exists if we defer the decision
- what should be decided next

---

## Executive Summary

Phase 5 is mostly a **product-definition gap**, not a broken-code phase.

The repo now has strong technical foundations for:

- tenant isolation
- auth and RBAC
- release distribution
- durable logs, incidents, workflow runs, and notification deliveries
- deployment/runtime validation

But several business-critical and platform-critical decisions are still not first-class in the product:

1. Agent onboarding is still just "know the API key and submit data".
2. Secrets are still global environment configuration, not tenant-scoped managed assets.
3. Tenant settings are not modeled as a configurable product surface.
4. Durable history exists in storage, but operator-facing APIs and UX for those histories are still thin or missing.
5. Real-time behavior has not been formally chosen; the product currently behaves mostly like request/response + polling.
6. Enterprise auth, commercial controls, and supportability policies are not yet planned deeply enough for enterprise rollout.

Recommended decision order:

1. Agent lifecycle + secret management
2. Tenant settings + supportability policy
3. Workflow/delivery/incident operator history surfaces
4. Real-time transport decision
5. Enterprise auth roadmap
6. Commercial roadmap

---

## 1. Agent Enrollment And Provisioning Lifecycle

Current evidence:

- agent authentication is a single global API key in [server/auth.py](/d:/aaditech-ufo/aaditech-ufo/server/auth.py)
- config exposes only `AGENT_API_KEY` in [server/config.py](/d:/aaditech-ufo/aaditech-ufo/server/config.py)
- release distribution exists in [server/services/agent_release_service.py](/d:/aaditech-ufo/aaditech-ufo/server/services/agent_release_service.py) and related release APIs in [server/blueprints/api.py](/d:/aaditech-ufo/aaditech-ufo/server/blueprints/api.py)

What is missing:

- no agent identity model
- no enrollment token or bootstrap token flow
- no per-agent credential issuance
- no agent registration state machine (`pending`, `active`, `revoked`, `rotating`, `retired`)
- no server-side agent inventory separate from telemetry rows
- no "claim host into tenant" provisioning flow

Risk if deferred:

- every agent effectively shares one trust secret
- revoking one agent means rotating the whole fleet secret
- no secure first-install story for enterprise deployments
- no clean answer for re-enrollment, host replacement, or key compromise

Recommendation:

- define an `Agent` first-class model with tenant ownership, enrollment state, and credential metadata
- add one-time enrollment token flow plus issued agent credential flow
- keep existing release/update system, but attach it to registered agent identity

Suggested backlog shape:

- `Agent`
- `AgentCredential`
- `AgentEnrollmentToken`
- `AgentHeartbeat` or last-seen metadata

Priority: `P0`

---

## 2. API Key Rotation And Tenant Secret Management

Current evidence:

- API key validation is global in [server/auth.py](/d:/aaditech-ufo/aaditech-ufo/server/auth.py)
- alert email/webhook, automation webhook allowlists, release directories, and Ollama config all come from process environment in [server/config.py](/d:/aaditech-ufo/aaditech-ufo/server/config.py)

What is missing:

- no per-tenant secret storage
- no key rotation workflow
- no secret versioning
- no secret audit trail beyond generic config usage
- no secure UI/API for managing tenant integrations

Conflicts already visible:

- multi-tenant platform intent exists, but operational secrets are mostly global
- `tenant.manage` exists as a permission, but there is no tenant-owned secrets domain behind it

Risk if deferred:

- tenants cannot safely manage their own webhook/SMTP/integration credentials
- secret rotation becomes ops-heavy and outage-prone
- enterprise customers will ask for scoped credentials and rotation windows

Recommendation:

- decide whether secrets live in DB encrypted-at-rest, external secret manager, or hybrid
- define rotation policy for:
  - agent credentials
  - tenant webhooks
  - SMTP/integration credentials
  - API integrations
- add audit events specifically for secret create/rotate/revoke

Priority: `P0`

---

## 3. Tenant Settings As A First-Class Model/API

Current evidence:

- tenant model is only `name`, `slug`, and `is_active` in [server/models.py](/d:/aaditech-ufo/aaditech-ufo/server/models.py)
- tenant APIs in [server/blueprints/api.py](/d:/aaditech-ufo/aaditech-ufo/server/blueprints/api.py) only create/list/update status
- the frontend "Platform Operations" page in [frontend/src/pages/platform/PlatformPage.tsx](/d:/aaditech-ufo/aaditech-ufo/frontend/src/pages/platform/PlatformPage.tsx) is global cache/database maintenance, not tenant settings

What is missing:

- no tenant settings model
- no tenant-level notification preferences
- no tenant-level branding/feature toggles/retention/configuration surface
- no place to store future auth policy, quotas, or onboarding defaults

Risk if deferred:

- future tenant-specific features will leak into scattered env vars or ad hoc JSON
- `tenant.manage` will remain broader than the actual product surfaces behind it

Recommendation:

- add a `TenantSettings` first-class model/API early, even if v1 is small
- start with bounded settings groups:
  - notifications
  - retention
  - branding/basic metadata
  - auth/session policy hooks
  - feature toggles

Priority: `P1`

---

## 4. Workflow Execution History And Audit Timeline UX

Current evidence:

- durable workflow execution history exists as `WorkflowRun` in [server/models.py](/d:/aaditech-ufo/aaditech-ufo/server/models.py)
- durable audit rows exist as `AuditEvent` in [server/models.py](/d:/aaditech-ufo/aaditech-ufo/server/models.py)
- automation execution persists runs in [server/services/automation_service.py](/d:/aaditech-ufo/aaditech-ufo/server/services/automation_service.py)
- audit listing exists in [server/blueprints/api.py](/d:/aaditech-ufo/aaditech-ufo/server/blueprints/api.py)

What is missing:

- no workflow-run list/detail API for operators
- no combined timeline view across workflow runs + audit + alerts + deliveries
- no run filtering by workflow, status, trigger source, or task id in operator UX

Important nuance:

- storage exists, so this is no longer a persistence gap
- this is now a **product-surface gap**

Recommendation:

- add workflow history APIs first
- then add a unified timeline UX plan:
  - automation run events
  - alert dispatch events
  - backup operations
  - auth/admin changes

Priority: `P1`

---

## 5. Notification Delivery History And Retry Visibility

Current evidence:

- durable delivery history exists as `NotificationDelivery` in [server/models.py](/d:/aaditech-ufo/aaditech-ufo/server/models.py)
- queue task persists delivery results in [server/tasks.py](/d:/aaditech-ufo/aaditech-ufo/server/tasks.py)
- alert dispatch API supports retry-related parameters in [server/blueprints/api.py](/d:/aaditech-ufo/aaditech-ufo/server/blueprints/api.py)

What is missing:

- no API to list/view delivery records
- no operator-facing retry visibility screen
- no "redeliver" or "inspect failed delivery" workflow
- no retention policy defined for delivery history

Risk if deferred:

- alerting is technically functional but operationally harder to support
- failed webhook/email diagnosis remains developer-centric instead of operator-usable

Recommendation:

- add read APIs for `NotificationDelivery`
- expose requested vs delivered channels, failures, retry counts, and task ids in UI
- decide whether manual redelivery is needed in v1

Priority: `P1`

---

## 6. Incident / Case Management Layer

Current evidence:

- correlated incidents persist as `IncidentRecord` in [server/models.py](/d:/aaditech-ufo/aaditech-ufo/server/models.py)
- correlated alert evaluation persists incident rows in [server/blueprints/api.py](/d:/aaditech-ufo/aaditech-ufo/server/blueprints/api.py)

What is missing:

- no incident list/detail API for operators
- no assignment, ownership, comment, or note model
- no state transitions beyond stored fields like `status` / `resolved_at`
- no case-management UX

Why this matters:

- current implementation is incident persistence
- enterprise operators will ask for investigation workflow

Recommendation:

- decide whether the product needs:
  - lightweight incident tracking only
  - or a true investigation/case layer
- if lightweight, expose `IncidentRecord` with status transitions and notes
- if full case management is desired, plan a separate `Case` / `CaseComment` / `CaseAssignment` slice

Priority: `P1`

---

## 7. Real-Time Streaming Decision: Polling, SSE, Or WebSocket

Current evidence:

- SPA uses request/response queries in pages like [frontend/src/pages/dashboard/DashboardPage.tsx](/d:/aaditech-ufo/aaditech-ufo/frontend/src/pages/dashboard/DashboardPage.tsx)
- there is no SSE or WebSocket transport surface in the current server search
- legacy pages use browser `setInterval`, which suggests polling-style refresh still exists in older surfaces

What is missing:

- no declared product transport choice
- no server abstraction for real-time subscriptions
- no client subscription layer

Recommendation:

- choose transport per feature instead of platform-wide ideology:
  - polling for low-frequency admin status
  - SSE for alert/log/timeline feeds
  - WebSocket only if bidirectional live control is truly needed later

Most practical v1 decision:

- default to polling + selective SSE
- avoid WebSocket until a strong bidirectional use case appears

Priority: `P2`

---

## 8. Enterprise Auth Roadmap: MFA, SSO, OIDC, SAML, Session Policy

Current evidence:

- JWT auth, refresh tokens, browser sessions, and RBAC are in [server/auth.py](/d:/aaditech-ufo/aaditech-ufo/server/auth.py)
- there is no OIDC, SAML, MFA, or external IdP integration code in the current repo scan

What is missing:

- MFA model and challenge flow
- SSO provider model/configuration
- SCIM or enterprise provisioning direction
- session policy controls such as max idle, device trust, re-auth for sensitive actions

Risk if deferred:

- product may be technically multi-tenant but not enterprise-buyable
- future auth additions may conflict with current local-user assumptions if not planned soon

Recommendation:

- define a staged auth roadmap:
  - v1: local auth + stronger session policy + optional TOTP MFA
  - v2: OIDC first
  - v3: SAML if enterprise demand requires it

Priority: `P2`

---

## 9. Commercial / Platform Roadmap: Quotas, Billing, Licensing, Feature Flags

Current evidence:

- roadmap vision includes quotas and billing in [MASTER_ROADMAP.md](/d:/aaditech-ufo/aaditech-ufo/MASTER_ROADMAP.md)
- current models/config do not expose quota, billing, license, or feature-flag domain models

What is missing:

- no usage-metering model
- no plan gating or entitlements
- no tenant-level feature flags
- no billing/license records

Risk if deferred:

- product can be built but not packaged commercially
- later feature monetization will require invasive retrofitting

Recommendation:

- at minimum define:
  - entitlements model
  - tenant plan tier
  - feature flags
  - basic usage counters
- full billing integration can remain later, but entitlement boundaries should not

Priority: `P2`

---

## 10. Supportability Basics: Backup Verification, Retention, Platform Observability

Current evidence:

- backup create/list/restore exists in [server/blueprints/api.py](/d:/aaditech-ufo/aaditech-ufo/server/blueprints/api.py) and [server/services/backup_service.py](/d:/aaditech-ufo/aaditech-ufo/server/services/backup_service.py)
- audit retention exists via `purge_audit_events` in [server/tasks.py](/d:/aaditech-ufo/aaditech-ufo/server/tasks.py)
- AI routes expose request-level observability metadata in [server/services/ai_service.py](/d:/aaditech-ufo/aaditech-ufo/server/services/ai_service.py)
- queue/cache health exists partially in [server/queue.py](/d:/aaditech-ufo/aaditech-ufo/server/queue.py) and [server/app.py](/d:/aaditech-ufo/aaditech-ufo/server/app.py)

What is missing:

- no true backup verification workflow on the backend
- the SPA backup page already warns that dry-run/integrity toggles are advisory only in [frontend/src/pages/backup/BackupPage.tsx](/d:/aaditech-ufo/aaditech-ufo/frontend/src/pages/backup/BackupPage.tsx)
- no generalized retention policies for logs, incidents, workflow runs, release artifacts, and delivery history
- no platform metrics export surface for operators/SREs
- no central ops telemetry plan for queue depth, job failures, audit growth, release storage, or tenant activity

Recommendation:

- supportability should become a formal product slice, not scattered utility work
- define:
  - backup verification flow
  - retention matrix by data class
  - internal platform observability metrics/logs/alerts
  - restore drill expectations for staging/ops

Priority: `P0`

---

## Cross-Cutting Conflicts

These are the main architectural tensions surfaced by the review:

1. Multi-tenant product intent vs global secret/config reality
2. Durable storage now exists for multiple operational domains, but operator APIs/UX lag behind
3. Enterprise posture is claimed in the vision docs, but enterprise auth and commercial controls are still undefined
4. Backup/retention/supportability language exists in UI/docs, but productized backend policy is still incomplete

---

## Recommended Next Slice

Do not try to implement all Phase 5 items at once.

Recommended next planning slice:

1. Define agent identity + enrollment + credential rotation model
2. Define tenant settings + tenant secret management model
3. Add read APIs for workflow runs, notification deliveries, and incidents
4. Write a short transport decision doc: polling vs SSE vs WebSocket
5. Write a short supportability policy doc: retention + backup verification + platform observability

---

## Suggested Status After This Review

Phase 5 should still remain **open**.

But it is now clearer how to classify the remaining work:

- `P0`: agent lifecycle, secret management, supportability policy
- `P1`: tenant settings, workflow/delivery/incident product surfaces
- `P2`: realtime transport, enterprise auth roadmap, commercial roadmap
