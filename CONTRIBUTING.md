# Contributing

Thanks for contributing to AADITECH UFO.

## Development Workflow

1. Create a feature branch from `main`.
2. Keep commits small and focused.
3. Add or update tests for every behavior change.
4. Run the relevant test suites locally before opening a PR.
5. Ensure security-sensitive routes include RBAC checks and audit logging.

## Local Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Database Migrations

```bash
flask db migrate -m "describe change"
flask db upgrade
```

Migration guidelines:

- Every model/schema change must include a migration.
- Keep migration scripts deterministic and reviewable.

## Testing Requirements

Run full tests:

```bash
python -m pytest -q
```

Run focused suites while developing:

```bash
python -m pytest tests/test_alert_suppression_pattern_ai_anomaly.py -q
python -m pytest tests/test_phase2_remaining_features.py -q
python -m pytest tests/test_auth_jwt_rbac.py tests/test_audit_logging.py -q
```

## Coding Standards

- Follow existing project style and naming conventions.
- Keep service logic in `server/services/` and HTTP concerns in blueprints.
- Avoid mixing unrelated refactors in feature PRs.
- Add concise docstrings for non-trivial logic.

## Security Checklist (Required)

For any sensitive endpoint:

- Add permission guard (`require_permission` / `require_api_key_or_permission`).
- Emit audit events for success and failure paths.
- Validate untrusted input and reject unsafe payloads.
- Add tests for allowed and denied access paths.

## Pull Request Checklist

- [ ] Feature behavior implemented
- [ ] Tests added/updated and passing
- [ ] Migration included (if schema changed)
- [ ] Docs updated (`README.md`, `.env.example`, or roadmap docs as needed)
- [ ] RBAC + audit checks verified for sensitive APIs
