# Commercial Platform Roadmap Decision

Updated: April 1, 2026

## Purpose

Define the minimum commercial/platform control model so product boundaries are clear before full billing implementation.

## Recommendation

Implement commercial controls in this order:

1. Tenant entitlements and feature flags.
2. Quotas and usage tracking.
3. Billing and licensing integrations later.

## Phase Order

### Phase A: Entitlements And Feature Flags

- tenant plan tier
- explicit enabled feature set
- rollout/preview flags
- API/UI behavior gated by entitlements, not by ad hoc environment checks

### Phase B: Quotas

- monitored systems count
- release artifact/storage limits
- log retention/storage usage limits
- automation execution volume limits if needed

### Phase C: Billing And Licensing

- subscription records
- invoicing/billing-provider integration
- contract or license enforcement where required

## Why

- feature boundaries must exist before commercial packaging can be reliable
- quotas require product metrics and reporting, but not necessarily billing integration
- full billing is operationally heavier and can come after entitlement clarity

## Recommended Data Domains

- `TenantPlan`
- `TenantEntitlement`
- `TenantFeatureFlag`
- `TenantUsageMetric`
- `TenantQuotaPolicy`

## Status

This decision should be treated as the current commercial/platform roadmap source of truth and is now partially implemented.

Implemented as of April 9, 2026:

- tenant-scoped entitlements and feature flags already exist as the Phase A foundation
- tenant-scoped quota policies and usage metrics now exist as the Phase B foundation
- working admin APIs now exist for quota reads/updates and current usage visibility
- real quota enforcement now exists for monitored systems, tenant secrets, and automation workflow creation

Expanded as of April 11, 2026:

- quota coverage now also includes `alert_rules` and `oidc_providers`
- tenant admins now have a dedicated quota-health report surface with percentage used, near-limit/over-limit visibility, and recent enforcement-event visibility
- the tenant admin SPA now exposes quota summary cards plus recent enforcement history instead of only the basic usage table

Still open in Phase B:

- additional quota domains such as release storage, retention, or execution volume if product pressure justifies them
- any billing/provider integration work from Phase C

Phase C status as of April 9, 2026:

- billing/licensing preparation foundations now exist through `TenantPlan`, `TenantBillingProfile`, and `TenantLicense`
- tenant-admin APIs now expose a draft commercial profile without coupling entitlements or quotas to billing state
- external billing-provider integration, invoicing, and hard contract/license enforcement are still intentionally open
