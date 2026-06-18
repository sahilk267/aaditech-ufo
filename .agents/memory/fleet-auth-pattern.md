---
name: Fleet endpoint auth pattern
description: GET /api/agents uses require_api_key_or_permission; PATCH trust uses require_permission only.
---

## Rule
Fleet management endpoints follow the same pattern as other tenant-scoped resource endpoints:

- `GET /api/agents` — `@require_api_key_or_permission('tenant.manage')` (allows agent API key for machine-to-machine reads)
- `PATCH /api/agents/<id>/trust` — `@require_permission('tenant.manage')` (JWT only; trust changes are human-initiated)

**Why:** Read access is allowed from the agent API key for tools that inspect fleet status. Trust state changes are privileged and require human authentication.

**How to apply:** Keep the same split for any new agent-fleet endpoints.
