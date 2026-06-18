---
name: Missing pages directory pattern
description: Pages referenced in router.tsx may not physically exist; always verify with ls before adding a route.
---

## Rule
Before adding a new lazy import to `frontend/src/app/router.tsx`, run `ls frontend/src/pages/` to confirm the target directory and file exist. The `logs/LogsPage.tsx` page was in the router but the directory was missing, breaking the build silently until the next `vite build` run.

**Why:** The router import fails at build time (not runtime), so the error only surfaces during `vite build`, not during dev server warm-up.

**How to apply:** Whenever the build fails with `UNRESOLVED_IMPORT` on a `pages/X/XPage` path, check if the directory exists and create it if missing.
