# Aaditech UFO Client Agent

This folder contains the client-side telemetry agent and packaging scripts.

## Files

- `agent.py` - Runtime telemetry collector and sender
- `build.spec` - PyInstaller build spec for Windows executable
- `uninstaller.nsi` - NSIS uninstaller template

## Environment Variables

Set these on client machine (or in local `.env` near executable):

- `SERVER_BASE_URL` (example: `http://your-server:5000`)
- `AGENT_SUBMIT_PATH` (default: `/api/submit_data`)
- `AGENT_API_KEY` (must match server)
- `TENANT_HEADER` (default: `X-Tenant-Slug`)
- `TENANT_SLUG` (tenant identifier)
- `AGENT_REPORT_INTERVAL_SECONDS` (default: `60`)
- `AGENT_REQUEST_TIMEOUT_SECONDS` (default: `10`)

## Local Run

```bash
python agent.py
```

## Build EXE (Windows)

```bash
pyinstaller build.spec --clean
```

or run the centralized build script from repository root:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_agent_windows.ps1 -Version 1.0.0
```

Expected output executable:

- `dist/aaditech-agent.exe`
- `dist/aaditech-agent-<version>.exe`

## Publish to Server Portal (Versioned)

After building the executable, register it into the server release portal:

```bash
./scripts/publish_agent_release.sh --file dist/aaditech-agent.exe --version 1.0.0
```

Portal users can then download from:

- `/agent/releases`

## Notes

- Agent posts JSON payload to `POST /api/submit_data`.
- It sends `X-API-Key` and optional tenant header if `TENANT_SLUG` is set.
- For multi-tenant deployments, set `TENANT_SLUG` per client environment.
