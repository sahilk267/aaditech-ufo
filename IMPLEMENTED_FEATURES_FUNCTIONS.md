# Implemented Features and Functions (Current State)

Last updated: 2026-03-24

## 1. Core Platform and API

Implemented:
- Flask modular architecture with blueprints:
  - API blueprint in server/blueprints/api.py
  - Web blueprint in server/blueprints/web.py
- Core ingestion endpoint for agent telemetry:
  - POST /api/submit_data
- Platform status and health endpoints:
  - GET /api/status
  - GET /api/health
- Structured validation layer using Marshmallow schemas in server/schemas.py
- Database persistence with SQLAlchemy models in server/models.py

Key implemented functions:
- Data validation and cleaning:
  - validate_system_data
  - validate_and_clean_system_data
- API security decorators and token utilities in server/auth.py

## 2. Authentication, Authorization, and Tenant Isolation

Implemented:
- API key based authentication for agent/API access
- JWT issue/refresh/revoke workflow foundations
- RBAC models and permission checks
- Web permission decorators for protected pages/actions
- Multi-tenant isolation using tenant context and tenant header routing

Key implemented components:
- Tenant context middleware and org scoping
- Role and permission bootstrap helpers
- Protected web/API routes with permission checks

## 3. Agent Release Portal (Versioned .exe Distribution)

Implemented:
- Release portal page:
  - GET /agent/releases
- Release upload endpoint (server-side artifact registration):
  - POST /agent/releases/upload
- Release download endpoint:
  - GET /agent/releases/download/<filename>
- API release list endpoint:
  - GET /api/agent/releases
- API release upload endpoint (CI/CD friendly):
  - POST /api/agent/releases/upload
- API release download endpoint (agent/self-update):
  - GET /api/agent/releases/download/<filename>
- Release policy endpoints:
  - GET /api/agent/releases/policy
  - PUT /api/agent/releases/policy
- Guided update/downgrade endpoint:
  - GET /api/agent/releases/guide?current_version=<x.y.z>
- Versioned artifact naming convention:
  - aaditech-agent-<version>.exe
- Server-side release listing and metadata extraction in server/services/agent_release_service.py
- Server-side release policy persistence and recommendation logic in server/services/agent_release_service.py

Key implemented functions:
- list_releases
- save_uploaded_release
- register_release_file
- resolve_download_path

## 4. Agent Build and Publish Tooling

Implemented:
- Windows build helper script:
  - scripts/build_agent_windows.ps1
- Server publish helper script:
  - scripts/publish_agent_release.sh
- GitHub Actions workflow for auto-build/auto-publish:
  - .github/workflows/agent-release-publish.yml

Current behavior:
- Agent can be built version-wise on build machine
- Built .exe can be uploaded/published and downloaded from portal
- Older versions remain downloadable, enabling manual downgrade by installing an older version
- CI can auto-build versioned `.exe` on tag (`agent-v*`) and publish artifact/release
- CI can auto-publish built `.exe` to server API when deployment secrets are configured
- Server-side guided downgrade/upgrade recommendation is now available via release policy API

## 5. Alerting, Automation, and Operations Foundations

Implemented:
- Alert rule CRUD/evaluation foundations
- Alert dedup/correlation/escalation foundations
- Alert notification queue hooks
- Automation workflow foundations and scheduled job model/API foundations
- Remote execution foundation with allowlist controls
- Audit logging foundations for sensitive operations

## 6. Reliability, Logs, and AI Foundations

Implemented foundations:
- Reliability analysis service scaffolding
- Log ingestion/parser/search adapter boundaries
- AI service wrappers for anomaly/root-cause/recommendation/troubleshooting foundations
- Dashboard aggregation and confidence scoring foundations

## 7. Performance and Deployment Foundations

Implemented:
- Cache status endpoint and cache service wiring
- Database optimization endpoint foundation
- Docker image build setup:
  - Dockerfile
  - docker-compose.gateway.yml
- GitHub workflow for Docker publish:
  - .github/workflows/docker-publish.yml

Validated now:
- docker compose -f docker-compose.gateway.yml build succeeds in current workspace

## 8. Current Known Pending Items

Test suite pending (as of latest run):
- tests/test_alerting_api.py::test_evaluate_alert_rules_returns_anomaly_alerts
- tests/test_database.py::TestSystemDataModel::test_system_data_with_all_fields
- tests/test_database.py::TestSystemDataModel::test_system_data_json_fields

Important note on agent lifecycle automation:
- Versioned upload/download is implemented.
- CI-triggered agent auto-build and auto-publish workflow is implemented.
- Server-side guided downgrade policy is implemented.
- Full forced remote in-place downgrade execution on client hosts is still out-of-scope for current release (client-side updater/orchestrator not yet implemented).
