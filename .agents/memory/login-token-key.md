---
name: Login token key name
description: The auth login response uses access_token not access; scripts must index tokens.access_token.
---

## Rule
When parsing the login response from `POST /api/auth/login`, the JWT is at `response.tokens.access_token`, not `response.tokens.access`.

**Why:** The backend `issue_jwt_tokens()` returns a dict with key `access_token`. Shell/Python scripts that index `['access']` silently get `None`.

**How to apply:** Always use `d['tokens']['access_token']` in scripts; in TypeScript use `data.tokens?.access_token`.
