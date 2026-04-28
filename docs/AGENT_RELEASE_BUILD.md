# Agent Release Build & Distribution

This document describes the three supported ways to produce and publish the Aaditech UFO Windows
agent (`aaditech-agent-<version>.exe`) and how those `.exe` files are served to enrolled agents.

## Why a dedicated build pipeline is required

The agent is bundled with **PyInstaller**, which **cannot cross-compile** a Windows `.exe` from
a Linux or macOS host. Running the in-app *Build Agent Binary* button on a non-Windows server will
succeed, but the artifact it produces is a native binary for the server platform, not a deployable
Windows executable. Enrolled Windows hosts will not be able to run that artifact.

To produce a real `.exe`, the build **must** happen on a Windows machine.

---

## Option 1 — GitHub Actions (recommended for production)

A workflow lives at `.github/workflows/agent-release-publish.yml` and runs on `windows-latest`.

### Trigger by tag

```bash
# Tag your commit with the agent version
git tag agent-v1.0.0
git push origin agent-v1.0.0
```

The workflow extracts the version from the tag (`agent-v1.0.0` → `1.0.0`), validates the format
(`[A-Za-z0-9._-]{1,64}`), builds the executable, and:

1. Uploads `aaditech-agent-<version>.exe` as a CI artifact (downloadable from the Actions run).
2. Creates a GitHub Release named `Agent v<version>` with auto-generated release notes and the
   `.exe` attached.
3. **Optionally** pushes the same `.exe` to your running server's release API if the following
   repository secrets are set:

| Secret                       | Example                                                            |
| ---------------------------- | ------------------------------------------------------------------ |
| `AGENT_RELEASE_UPLOAD_URL`   | `https://your-app.replit.app/api/agent/releases/upload`            |
| `AGENT_RELEASE_API_KEY`      | An API key with the `tenant.manage` permission                     |
| `AGENT_RELEASE_TENANT_SLUG`  | Optional. Defaults to `default`                                    |

### Trigger manually

From the GitHub Actions tab → *Agent Release Build and Publish* → *Run workflow*. Provide the
version string when prompted.

---

## Option 2 — Local Windows machine (manual)

For ad-hoc builds without GitHub:

```powershell
# Requires Python 3.12 and Git
git clone <this-repo>
cd <repo>
powershell -ExecutionPolicy Bypass -File .\scripts\build_agent_windows.ps1 -Version 1.0.0
```

The script installs PyInstaller (if missing) and writes
`agent\dist\aaditech-agent-1.0.0.exe`. Upload that file via the *Releases* page in the UI or via
the API:

```bash
curl -X POST "https://your-app.replit.app/api/agent/releases/upload" \
     -H "X-API-Key: <key with tenant.manage>" \
     -H "X-Tenant-Slug: default" \
     -F "version=1.0.0" \
     -F "release_file=@agent\dist\aaditech-agent-1.0.0.exe"
```

---

## Option 3 — Manual upload through the SPA

1. Sign in at `/app/login` with an account holding the `tenant.manage` permission.
2. Open the *Agent Releases* page.
3. In the **Upload Release (.exe)** card, type the version (e.g. `1.0.0`), pick the `.exe` file,
   and click *Upload .exe*.

The server normalizes the file to `aaditech-agent-<version>.exe` and stores it under
`instance/agent_releases/`. Validation rules:

- Version must match `^[A-Za-z0-9._-]{1,64}$`
- File extension must be `.exe`
- File size must not exceed `AGENT_RELEASE_MAX_MB` (default 256 MB)

---

## How agents discover releases

Once one or more `.exe` files exist, three endpoints become useful:

| Endpoint                                          | Purpose                                                              |
| ------------------------------------------------- | -------------------------------------------------------------------- |
| `GET /api/agent/releases`                         | List all available versions and their download URLs.                 |
| `GET /api/agent/releases/guide?current_version=X` | Per-agent upgrade/downgrade recommendation based on policy + latest. |
| `GET /api/agent/releases/download/<filename>`     | Authenticated download of a specific `.exe`.                         |
| `PUT /api/agent/releases/policy`                  | Set `target_version` for guided upgrades (requires `tenant.manage`). |

All endpoints require either a valid session or an API key with `dashboard.view` (read) or
`tenant.manage` (write).

---

## Server-side build button (advanced / non-Windows)

The *Server Build Operations* card in the SPA still works on the Linux server, but its purpose is
limited:

- Smoke-testing that the PyInstaller config and agent source compile cleanly.
- Producing a Linux/macOS binary for development scenarios.

The API response now includes a `windows_compatible` flag and a `guidance` string that the SPA
renders as a yellow banner so operators are not confused into shipping the wrong artifact.

---

## Current agent capabilities (`agent/agent.py`)

A built `.exe` includes:

- Hostname / serial-number / IP / model collection (Windows uses `wmic`)
- Live CPU + RAM + per-core + per-partition disk metrics via `psutil`
- Lightweight benchmark calculation
- HTTP submission to the server's `/api/submit_data`
- Configurable via `SERVER_BASE_URL`, `AGENT_API_KEY`, `TENANT_SLUG` env vars

Capabilities **not yet** in the agent (server APIs exist, agent client logic does not):

- Log forwarding
- Remote command execution / self-healing actions
- Local alert-rule evaluation
- Self-update (the guide endpoint exists, the agent does not yet act on it)
- Service start/stop/restart management
- TLS/cert pinning, exponential-backoff retries, offline buffering
- Packaged Windows installer / uninstaller (`agent/uninstaller.nsi` exists but is not wired into
  the build)

These are tracked in the platform roadmap and will land in subsequent agent iterations.
