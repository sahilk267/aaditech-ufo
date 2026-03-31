# Tenant Secret Management Decision

Updated: March 31, 2026

## Purpose

Define the recommended v1 model for tenant-scoped secrets, rotation, and operational ownership.

---

## Problem

The platform is multi-tenant in data and auth, but many operational secrets are still process-global configuration.

That creates a mismatch for:

- webhooks
- SMTP/integration credentials
- future API integrations
- future agent-scoped credentials

---

## Decision Summary

Adopt tenant-scoped secret records as a first-class product capability.

Recommended v1 storage strategy:

- metadata in the application database
- encrypted secret values at rest
- strict server-side write-only handling for raw secret material

Do not expose plaintext secrets back to the UI/API after creation.

---

## Recommended v1 Domain Model

### `TenantSecret`

Recommended fields:

- `id`
- `organization_id`
- `secret_type`
- `name`
- `status`
- `ciphertext`
- `key_version`
- `created_by_user_id`
- `rotated_at`
- `expires_at`
- `last_used_at`
- `created_at`
- `updated_at`

Recommended secret types:

- `webhook_endpoint`
- `smtp_credential`
- `api_integration`
- `agent_enrollment_policy`
- `agent_credential_seed` if needed later

Recommended statuses:

- `active`
- `scheduled_for_rotation`
- `revoked`
- `expired`

### `TenantSecretVersion`

Optional in v1, but recommended if overlap rotation windows are needed.

Use this if one logical secret may have multiple active versions during rotation.

---

## Handling Rules

1. Raw secret value is accepted only on create/rotate.
2. Server stores encrypted value, not plaintext.
3. Read APIs return only metadata, never raw secret.
4. Rotation should support overlap windows where appropriate.
5. All secret actions require `tenant.manage` or a future narrower permission.

---

## Encryption Recommendation

Recommended v1 approach:

- application-managed encryption key from environment or secret manager
- per-record encryption using a stable envelope strategy
- store `key_version` for future re-encryption

If external secret manager adoption is near-term, use a hybrid approach:

- DB stores metadata and references
- secret manager stores values

If external secret manager is not imminent, DB + encrypted-at-rest is the most practical v1.

---

## Rotation Policy Recommendation

### Webhooks

- allow immediate replace
- optionally allow overlap window

### SMTP / API integrations

- support staged rotation
- preserve last-used metadata

### Agent credentials

- rotate per-agent, not per-tenant global secret

---

## API Surface Recommendation

Recommended first APIs:

- `GET /api/tenant-secrets`
- `POST /api/tenant-secrets`
- `POST /api/tenant-secrets/<id>/rotate`
- `POST /api/tenant-secrets/<id>/revoke`
- `GET /api/tenant-secrets/<id>/usage`

Response shape should expose:

- `id`
- `name`
- `secret_type`
- `status`
- `created_at`
- `rotated_at`
- `expires_at`
- `last_used_at`

Never expose:

- plaintext secret
- raw ciphertext

---

## Audit Requirements

Required audit events:

- `tenant.secret.create`
- `tenant.secret.rotate`
- `tenant.secret.revoke`
- `tenant.secret.use`

`tenant.secret.use` can be sampled or summarized if high volume becomes a concern.

---

## Permission Recommendation

Current practical permission:

- `tenant.manage`

Recommended future refinement:

- `tenant.secret.manage`
- `tenant.secret.view_metadata`

---

## Migration Strategy

1. Start with webhook/integration secrets.
2. Move tenant-owned external config out of process-global env vars where appropriate.
3. Keep platform-global infra secrets global:
   - database
   - Redis
   - app signing keys
4. Do not move infrastructure bootstrap secrets into tenant settings.

---

## Explicit Boundary

Not every secret should become tenant-scoped.

Remain platform-global:

- `SECRET_KEY`
- `JWT_SECRET_KEY`
- database credentials
- Redis credentials
- deployment/runtime TLS material unless architecture changes

Become tenant-scoped:

- tenant webhooks
- tenant integration tokens
- tenant notification credentials if the product supports them

---

## Recommended Status

This decision should be treated as `P0` because the current multi-tenant product story is incomplete without it.
