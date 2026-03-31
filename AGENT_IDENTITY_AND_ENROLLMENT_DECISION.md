# Agent Identity And Enrollment Decision

Updated: March 31, 2026

## Purpose

Define the recommended Phase 5 v1 model for agent identity, enrollment, provisioning, and credential rotation.

---

## Problem

Today the platform treats agent trust mostly as a shared API key problem.

That is enough for bootstrap demos, but not enough for enterprise rollout because:

- all agents effectively share one trust boundary
- revocation is fleet-wide instead of per-agent
- there is no secure first-install enrollment flow
- there is no inventory model for provisioned agents

---

## Decision Summary

Adopt a first-class agent identity model with:

1. one-time enrollment tokens
2. per-agent issued credentials
3. durable agent inventory and lifecycle state
4. rotation and revocation support

Do not keep the long-term design centered on one global `AGENT_API_KEY`.

---

## Recommended v1 Domain Model

### `Agent`

Core identity record.

Recommended fields:

- `id`
- `organization_id`
- `display_name`
- `hostname`
- `serial_number`
- `platform`
- `agent_version`
- `enrollment_state`
- `trust_state`
- `last_seen_at`
- `last_ip`
- `created_at`
- `updated_at`

Recommended states:

- `pending`
- `active`
- `revoked`
- `retired`

### `AgentCredential`

Represents an issued machine credential.

Recommended fields:

- `id`
- `agent_id`
- `credential_fingerprint`
- `issued_at`
- `expires_at`
- `revoked_at`
- `rotation_reason`
- `status`

Recommended statuses:

- `active`
- `superseded`
- `revoked`
- `expired`

### `AgentEnrollmentToken`

Short-lived bootstrap token used once during install/claim.

Recommended fields:

- `id`
- `organization_id`
- `token_fingerprint`
- `created_by_user_id`
- `intended_hostname_pattern`
- `expires_at`
- `used_at`
- `status`

Recommended statuses:

- `issued`
- `used`
- `expired`
- `revoked`

### `AgentHeartbeat`

Optional separate table if historical heartbeat retention is wanted.

If not needed in v1, keep only `last_seen_at` / `last_ip` on `Agent`.

---

## Recommended Enrollment Flow

### Flow A: Admin-issued enrollment token

1. Tenant admin creates an enrollment token.
2. Token is time-bounded and optionally hostname-scoped.
3. Agent starts with that bootstrap token.
4. Server creates `Agent` in `pending` or `active`.
5. Server issues long-term agent credential.
6. Agent discards enrollment token after first successful enrollment.

### Flow B: Re-enrollment / host replacement

1. Existing agent is lost, rebuilt, or replaced.
2. Admin creates a new enrollment token or explicitly reactivates the record.
3. Old credential is revoked.
4. New credential is issued and linked to same or replacement agent record.

---

## Authentication Shape

### Short term

Keep compatibility with current `X-API-Key` path for legacy/bootstrap flows.

### Target v1

Agent requests should authenticate with a per-agent credential:

- either signed token
- or opaque secret with fingerprinted server-side validation

Recommended practical v1:

- opaque agent secret
- store only fingerprint/hash server-side
- send via dedicated header such as `X-Agent-Credential`

---

## Lifecycle Operations

Required operator actions:

- list agents by tenant
- revoke one agent
- rotate one agent credential
- retire one agent
- see last-seen and version drift

Not required in first v1:

- full mutual TLS
- certificate PKI
- auto-approval of untrusted enrollments

---

## API Surface Recommendation

Recommended first APIs:

- `POST /api/agents/enrollment-tokens`
- `GET /api/agents`
- `POST /api/agents/enroll`
- `POST /api/agents/<id>/rotate-credential`
- `POST /api/agents/<id>/revoke`
- `PATCH /api/agents/<id>`

---

## Audit Requirements

Every lifecycle step should emit audit events:

- `agent.enrollment_token.create`
- `agent.enroll`
- `agent.credential.rotate`
- `agent.revoke`
- `agent.retire`

---

## Migration Strategy

1. Introduce models and admin APIs first.
2. Keep legacy global API key support temporarily.
3. Add agent enrollment endpoint and per-agent credential validation.
4. Migrate agent code to use issued credentials.
5. Deprecate global agent API key from steady-state runtime.

---

## Explicit Non-Goals For v1

- certificate authority management
- device attestation
- full zero-touch enterprise enrollment
- cross-tenant fleet federation

---

## Recommended Status

This decision should be treated as a `P0` prerequisite before large-scale agent rollout.
