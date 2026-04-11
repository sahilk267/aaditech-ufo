# Enterprise Auth Roadmap Decision

Updated: April 10, 2026

## Purpose

Define the staged enterprise authentication roadmap without overbuilding ahead of real demand.

## Recommendation

Adopt a three-stage roadmap:

1. Strengthen local auth and session policy first.
2. Add OIDC as the first external identity provider integration.
3. Add SAML only if enterprise demand requires it later.

## Proposed Stages

### Stage 1: Local Auth Hardening

- stronger session policy controls in tenant settings
- password rules and lockout policy
- optional TOTP MFA
- admin-visible session invalidation

### Stage 2: OIDC First

- tenant-scoped OIDC provider config
- login via external IdP
- role/claim mapping into tenant RBAC
- fallback local admin access policy

### Stage 3: SAML If Needed

- only for customers that require legacy enterprise federation
- keep behind enterprise readiness milestone

## Why OIDC First

- better modern ecosystem support
- lower implementation friction than SAML
- aligns with cloud and SaaS enterprise expectations

## Guardrails

- local admin recovery path must always exist
- auth settings should be tenant-scoped
- claim-to-role mapping must be explicit and auditable
- MFA should not depend on SSO rollout to exist

## Status

This decision remains the current enterprise-auth roadmap source of truth and is now partially implemented.

Implemented on April 2, 2026:

- tenant-scoped local auth policy defaults/validation
- password policy baseline
- login lockout baseline
- admin-visible session invalidation via session revocation
- optional TOTP MFA foundation with enrollment, activation, disable, and MFA login challenge verification
- SPA tenant/admin visibility for auth policy and current-user MFA state
- Stage 2 OIDC foundation with tenant-scoped provider CRUD, bounded OIDC auth-policy toggles, deterministic test-mode login/callback flow, tenant-secret-backed client secret storage, and claim-to-role RBAC mapping

Still open in Stage 1:

- fuller auth admin UX around policy/session visibility

Stage 2 status as of April 10, 2026:

- working foundation is now present for tenant-scoped OIDC provider configuration
- the repo can validate login/callback behavior without an external IdP by using test-mode providers
- provider metadata discovery now exists with persisted discovery status/error visibility
- bounded external authorization-code exchange plus userinfo-backed claim retrieval now exist for allowlisted provider hosts
- the SPA tenant admin surface now supports discovery-aware provider setup and metadata refresh actions

Still open in Stage 2:

- richer login-page/operator guidance for end-user SSO initiation
- stricter token or ID-token verification semantics if future production requirements demand them
