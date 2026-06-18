---
name: AgentsFleetPage import path
description: ModulePage lives at components/common, not components/layout.
---

## Rule
`ModulePage`, `ActionPanel`, `StatCard`, `JsonViewer`, `MutationFeedback`, `ErrorBoundary` all live under `frontend/src/components/common/`, not under `components/layout/`.

`AppShell.tsx` is the only file under `components/layout/`.

**Why:** The layout directory was set up with only the shell; all shared UI primitives went into `common/`.

**How to apply:** When generating new page files, always import from `../../components/common/`, not `../../components/layout/`.
