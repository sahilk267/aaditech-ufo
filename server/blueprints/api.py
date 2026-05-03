"""
API Blueprint
REST API endpoints for agent data submission and system management
"""

import ast
import json
import logging
import os
import platform
import re
import time
from urllib.parse import urlencode, urlparse
from hashlib import sha1
from datetime import UTC, datetime
import requests
from flask import current_app
from flask import Blueprint, request, jsonify, g, send_file, abort, url_for, Response, stream_with_context, redirect
from sqlalchemy import func, or_, text
from werkzeug.utils import secure_filename
from ..extensions import limiter
from ..auth import (
    build_totp_provisioning_uri,
    require_api_key,
    default_auth_policy,
    generate_totp_secret,
    get_effective_auth_policy,
    hash_password,
    is_user_locked_out,
    issue_mfa_challenge_token,
    issue_oidc_state_token,
    verify_password,
    issue_jwt_tokens,
    record_failed_login,
    require_refresh_token,
    require_jwt_auth,
    require_permission,
    require_api_key_or_permission,
    revoke_token,
    revoke_user_sessions,
    reset_login_state,
    tenant_entitlement_enabled,
    tenant_feature_flag_enabled,
    verify_totp_code,
    validate_password_against_policy,
    start_web_session,
    decode_jwt_token,
)
from ..schemas import validate_and_clean_system_data
from ..models import (
    db,
    SystemData,
    Organization,
    User,
    UserTotpFactor,
    Role,
    Permission,
    AuditEvent,
    AlertRule,
    LogSource,
    LogEntry,
    LogInvestigation,
    IncidentRecord,
    IncidentCaseComment,
    TenantSetting,
    TenantOidcProvider,
    TenantSecret,
    TenantEntitlement,
    TenantFeatureFlag,
    TenantQuotaPolicy,
    TenantUsageMetric,
    TenantPlan,
    TenantBillingProfile,
    TenantLicense,
    Agent,
    AgentCommand,
    AgentServerPin,
    AutomationWorkflow,
    WorkflowRun,
    NotificationDelivery,
    ReliabilityRun,
    UpdateRun,
)
from ..audit import log_audit_event
from ..queue import (
    get_queue_status,
    enqueue_maintenance_job,
    enqueue_alert_notification_job,
    enqueue_automation_workflow_job,
)
from ..services import (
    AlertService,
    AutomationService,
    LogService,
    ReliabilityService,
    AIService,
    UpdateService,
    ConfidenceService,
    DashboardService,
    RemoteExecutorService,
    PerformanceService,
    AgentReleaseService,
    BackupService,
    AgentIdentityService,
    TenantSecretService,
    MfaService,
)
from marshmallow import ValidationError

logger = logging.getLogger(__name__)


def _build_artifact_metadata(binary_path) -> dict[str, object]:
    runtime_platform = (platform.system() or 'unknown').lower()
    artifact_extension = binary_path.suffix.lower() if getattr(binary_path, 'suffix', None) else ''
    artifact_kind = 'windows_executable' if artifact_extension == '.exe' else 'native_binary'
    windows_compatible = runtime_platform == 'windows' and artifact_extension == '.exe'
    if runtime_platform == 'windows':
        guidance = (
            'Server is running on Windows. Native build produces a deployable .exe.'
        )
    else:
        guidance = (
            'PyInstaller cannot cross-compile a Windows .exe from this runtime. '
            'The artifact above is a native binary for the server platform only. '
            'To produce a Windows .exe: run the GitHub Actions workflow '
            '"Agent Release Build and Publish" (windows-latest runner), or execute '
            'scripts/build_agent_windows.ps1 on a Windows machine, then upload the '
            'resulting .exe via the Releases page.'
        )
    return {
        'runtime_platform': runtime_platform,
        'artifact_extension': artifact_extension,
        'artifact_kind': artifact_kind,
        'windows_compatible': windows_compatible,
        'guidance': guidance,
    }

api_bp = Blueprint('api', __name__, url_prefix='/api')


def _slugify(name: str) -> str:
    """Convert tenant/org name to a URL-safe slug."""
    normalized = re.sub(r'[^a-zA-Z0-9\s-]', '', name).strip().lower()
    return re.sub(r'[\s_-]+', '-', normalized).strip('-')


def _get_or_create_permission(code: str, description: str = '') -> Permission:
    permission = Permission.query.filter_by(code=code).first()
    if permission:
        return permission
    permission = Permission(code=code, description=description)
    db.session.add(permission)
    db.session.flush()
    return permission


def _get_or_create_default_admin_role(organization_id: int) -> Role:
    role = Role.query.filter_by(organization_id=organization_id, name='admin').first()
    if not role:
        role = Role(
            organization_id=organization_id,
            name='admin',
            description='Default tenant administrator role',
            is_system=True,
        )

        db.session.add(role)
        db.session.flush()

    existing_codes = {permission.code for permission in role.permissions}
    required_permissions = [
        ('tenant.manage', 'Manage tenant settings and users'),
        ('dashboard.view', 'View dashboard data'),
        ('system.submit', 'Submit or refresh local system data'),
        ('backup.manage', 'Create and restore backups'),
        ('automation.manage', 'Create and execute automation workflows'),
    ]

    for code, description in required_permissions:
        if code not in existing_codes:
            role.permissions.append(_get_or_create_permission(code, description))

    return role


def _default_retention_settings() -> dict:
    return {
        'audit_events_days': int(current_app.config.get('AUDIT_RETENTION_DAYS', 90)),
        'notification_deliveries_days': int(current_app.config.get('NOTIFICATION_DELIVERY_RETENTION_DAYS', 60)),
        'workflow_runs_days': int(current_app.config.get('WORKFLOW_RUN_RETENTION_DAYS', 60)),
        'resolved_incidents_days': int(current_app.config.get('RESOLVED_INCIDENT_RETENTION_DAYS', 90)),
        'log_entries_days': int(current_app.config.get('LOG_ENTRY_RETENTION_DAYS', 30)),
    }


def _validate_auth_policy(auth_policy: dict) -> dict[str, list[str]]:
    """Validate bounded tenant auth policy fields."""
    errors: dict[str, list[str]] = {}
    schema = {
        'min_password_length': ('int', 8, 128),
        'lockout_threshold': ('int', 1, 20),
        'lockout_minutes': ('int', 1, 1440),
        'session_max_age_minutes': ('int', 15, 60 * 24 * 30),
        'require_uppercase': ('bool', None, None),
        'require_lowercase': ('bool', None, None),
        'require_number': ('bool', None, None),
        'require_symbol': ('bool', None, None),
        'totp_mfa_enabled': ('bool', None, None),
        'oidc_enabled': ('bool', None, None),
        'local_admin_fallback_enabled': ('bool', None, None),
    }
    for key, value in auth_policy.items():
        if key not in schema:
            errors[key] = ['Unsupported auth policy key.']
            continue
        kind, minimum, maximum = schema[key]
        if kind == 'bool':
            if not isinstance(value, bool):
                errors[key] = ['Must be a boolean.']
        else:
            if not isinstance(value, int):
                errors[key] = ['Must be an integer.']
            elif value < minimum or value > maximum:
                errors[key] = [f'Must be between {minimum} and {maximum}.']
    return errors


def _get_or_create_tenant_settings(organization_id: int) -> TenantSetting:
    settings = TenantSetting.query.filter_by(organization_id=organization_id).first()
    if settings is None:
        settings = TenantSetting(
            organization_id=organization_id,
            notification_settings={},
            retention_settings=_default_retention_settings(),
            branding_settings={},
            auth_policy=default_auth_policy(),
            feature_flags={},
        )
        db.session.add(settings)
        db.session.commit()
    return settings


def _serialize_tenant_settings(settings: TenantSetting) -> dict:
    """Return tenant settings with effective auth-policy defaults merged in."""
    payload = settings.to_dict()
    payload['auth_policy'] = {**default_auth_policy(), **(payload.get('auth_policy') or {})}
    return payload


def _validate_relative_redirect_uri(value: str) -> str:
    redirect_uri = str(value or '').strip()
    if not redirect_uri:
        return ''
    if not redirect_uri.startswith('/') or redirect_uri.startswith('//'):
        return ''
    return redirect_uri


def _utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _oidc_allowed_hosts() -> set[str]:
    raw_hosts = str(current_app.config.get('OIDC_ALLOWED_HOSTS', '') or '').strip()
    return {item.strip().lower() for item in raw_hosts.split(',') if item.strip()}


def _oidc_host_allowed(provider: TenantOidcProvider, target_url: str) -> bool:
    parsed = urlparse(str(target_url or '').strip())
    hostname = (parsed.hostname or '').lower()
    if not hostname:
        return False
    if hostname in {'localhost', '127.0.0.1'}:
        return True
    allowed_hosts = _oidc_allowed_hosts()
    issuer_host = (urlparse(str(provider.issuer or '').strip()).hostname or '').lower()
    return hostname == issuer_host or hostname in allowed_hosts


def _oidc_validate_outbound_url(provider: TenantOidcProvider, target_url: str) -> None:
    parsed = urlparse(str(target_url or '').strip())
    if parsed.scheme not in {'http', 'https'}:
        raise ValidationError({'provider': ['OIDC endpoint must use http:// or https://.']})
    if not _oidc_host_allowed(provider, target_url):
        raise ValidationError({'provider': ['OIDC endpoint host is not allowlisted for this provider.']})


def _default_discovery_endpoint(issuer: str) -> str:
    return f"{str(issuer or '').rstrip('/')}/.well-known/openid-configuration"


def _load_oidc_secret(provider: TenantOidcProvider) -> str | None:
    secret_name = str(provider.client_secret_secret_name or '').strip()
    if not secret_name:
        return None
    secret = TenantSecret.query.filter_by(
        organization_id=provider.organization_id,
        secret_type='oidc_client',
        name=secret_name,
    ).first()
    if secret is None:
        return None
    return TenantSecretService.decrypt_value(secret.ciphertext, current_app.config)


def _record_oidc_discovery(provider: TenantOidcProvider, status: str, error_message: str | None = None) -> None:
    provider.last_discovery_status = status
    provider.last_discovery_at = _utcnow_naive()
    provider.last_error = error_message[:500] if error_message else None
    db.session.add(provider)
    db.session.commit()


def _record_oidc_auth(provider: TenantOidcProvider, status: str, error_message: str | None = None) -> None:
    provider.last_auth_status = status
    provider.last_auth_at = _utcnow_naive()
    provider.last_error = error_message[:500] if error_message else None
    db.session.add(provider)
    db.session.commit()


def _discover_oidc_provider_metadata(provider: TenantOidcProvider) -> dict:
    discovery_url = str(provider.discovery_endpoint or '').strip() or _default_discovery_endpoint(provider.issuer)
    _oidc_validate_outbound_url(provider, discovery_url)
    response = requests.get(discovery_url, timeout=int(current_app.config.get('OIDC_DISCOVERY_TIMEOUT_SECONDS', 5)))
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValidationError({'provider': ['OIDC discovery response must be an object.']})
    provider.discovery_endpoint = discovery_url
    provider.authorization_endpoint = str(payload.get('authorization_endpoint') or provider.authorization_endpoint or '').strip()
    provider.token_endpoint = str(payload.get('token_endpoint') or provider.token_endpoint or '').strip() or None
    provider.userinfo_endpoint = str(payload.get('userinfo_endpoint') or provider.userinfo_endpoint or '').strip() or None
    provider.jwks_uri = str(payload.get('jwks_uri') or provider.jwks_uri or '').strip() or None
    provider.end_session_endpoint = str(payload.get('end_session_endpoint') or provider.end_session_endpoint or '').strip() or None
    db.session.add(provider)
    db.session.commit()
    _record_oidc_discovery(provider, 'success')
    return provider.to_dict()


def _exchange_external_oidc_code(provider: TenantOidcProvider, code: str, redirect_uri: str) -> dict:
    token_endpoint = str(provider.token_endpoint or '').strip()
    if not token_endpoint:
        raise ValidationError({'provider': ['OIDC token endpoint is not configured.']})
    _oidc_validate_outbound_url(provider, token_endpoint)
    client_secret = _load_oidc_secret(provider)
    if not client_secret:
        raise ValidationError({'provider': ['OIDC client secret is not configured.']})
    response = requests.post(
        token_endpoint,
        data={
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': redirect_uri,
            'client_id': provider.client_id,
            'client_secret': client_secret,
        },
        timeout=int(current_app.config.get('OIDC_HTTP_TIMEOUT_SECONDS', 8)),
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValidationError({'provider': ['OIDC token response must be an object.']})
    return payload


def _fetch_external_oidc_claims(provider: TenantOidcProvider, token_payload: dict) -> dict:
    userinfo_endpoint = str(provider.userinfo_endpoint or '').strip()
    access_token = str(token_payload.get('access_token') or '').strip()
    if userinfo_endpoint and access_token:
        _oidc_validate_outbound_url(provider, userinfo_endpoint)
        response = requests.get(
            userinfo_endpoint,
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=int(current_app.config.get('OIDC_HTTP_TIMEOUT_SECONDS', 8)),
        )
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict):
            return payload
    raise ValidationError({'provider': ['OIDC external login requires a reachable userinfo endpoint and access token.']})


def _validate_oidc_provider_payload(payload: dict, partial: bool = False) -> dict[str, list[str]]:
    errors: dict[str, list[str]] = {}
    required_fields = ['name', 'issuer', 'client_id']
    url_fields = ['issuer', 'discovery_endpoint', 'authorization_endpoint', 'token_endpoint', 'userinfo_endpoint']

    for field_name in required_fields:
        if partial and field_name not in payload:
            continue
        if not str(payload.get(field_name) or '').strip():
            errors[field_name] = ['Field required.']

    requires_auth_endpoint = True
    if partial:
        if 'authorization_endpoint' in payload:
            requires_auth_endpoint = not bool(str(payload.get('authorization_endpoint') or '').strip()) and 'discovery_endpoint' not in payload
        else:
            requires_auth_endpoint = False
    elif not str(payload.get('authorization_endpoint') or '').strip() and not str(payload.get('discovery_endpoint') or '').strip():
        errors['authorization_endpoint'] = ['Provide authorization_endpoint or discovery_endpoint.']
        requires_auth_endpoint = False

    if requires_auth_endpoint and 'authorization_endpoint' in payload and not str(payload.get('authorization_endpoint') or '').strip():
        errors['authorization_endpoint'] = ['Field required.']

    for field_name in url_fields:
        if field_name not in payload:
            continue
        value = str(payload.get(field_name) or '').strip()
        if value and not (value.startswith('http://') or value.startswith('https://')):
            errors[field_name] = ['Must start with http:// or https://.']

    if 'scopes' in payload:
        scopes = payload.get('scopes')
        if not isinstance(scopes, list) or not all(str(item or '').strip() for item in scopes):
            errors['scopes'] = ['Must be a list of non-empty strings.']

    for field_name in ['claim_mappings', 'role_mappings', 'test_claims']:
        if field_name in payload and not isinstance(payload.get(field_name), dict):
            errors[field_name] = ['Must be an object.']

    for field_name in ['test_mode', 'is_enabled', 'is_default']:
        if field_name in payload and not isinstance(payload.get(field_name), bool):
            errors[field_name] = ['Must be a boolean.']

    return errors


def _get_oidc_provider_for_tenant(provider_id: int, organization_id: int) -> TenantOidcProvider | None:
    return TenantOidcProvider.query.filter_by(id=provider_id, organization_id=organization_id).first()


def _extract_claim_value(claims: dict, key: str, fallback: str = ''):
    value = claims.get(key, fallback)
    if isinstance(value, list):
        return value
    return value


def _apply_oidc_role_mapping(provider: TenantOidcProvider, claims: dict) -> list[Role]:
    mappings = provider.role_mappings or {}
    claim_mappings = provider.claim_mappings or {}
    groups_claim_key = str(claim_mappings.get('groups') or 'groups')
    raw_groups = _extract_claim_value(claims, groups_claim_key, [])
    groups = raw_groups if isinstance(raw_groups, list) else [raw_groups]
    normalized_groups = {str(item).strip() for item in groups if str(item).strip()}
    mapped_role_names: set[str] = set()

    for group_name, role_names in mappings.items():
        if str(group_name).strip() not in normalized_groups:
            continue
        if isinstance(role_names, list):
            mapped_role_names.update(str(item).strip() for item in role_names if str(item).strip())
        elif str(role_names).strip():
            mapped_role_names.add(str(role_names).strip())

    roles: list[Role] = []
    if mapped_role_names:
        roles = (
            Role.query
            .filter(Role.organization_id == provider.organization_id, Role.name.in_(sorted(mapped_role_names)))
            .all()
        )
    if not roles:
        roles = [_get_or_create_default_admin_role(provider.organization_id)]
    return roles


def _upsert_oidc_user(tenant: Organization, provider: TenantOidcProvider, claims: dict) -> tuple[User, bool]:
    claim_mappings = provider.claim_mappings or {}
    email_key = str(claim_mappings.get('email') or 'email')
    full_name_key = str(claim_mappings.get('full_name') or 'name')
    email = str(_extract_claim_value(claims, email_key, '') or '').strip().lower()
    full_name = str(_extract_claim_value(claims, full_name_key, '') or '').strip()
    if not email:
        raise ValidationError({'claims': ['Mapped email claim is required.']})

    user = User.query.filter_by(organization_id=tenant.id, email=email).first()
    created = False
    if user is None:
        created = True
        user = User(
            organization_id=tenant.id,
            email=email,
            full_name=full_name or email.split('@')[0],
            password_hash=hash_password(f'oidc-{tenant.slug}-{provider.id}-{email}'),
            is_active=True,
        )
        db.session.add(user)
        db.session.flush()
    elif full_name:
        user.full_name = full_name

    user.roles = _apply_oidc_role_mapping(provider, claims)
    user.is_active = True
    db.session.add(user)
    db.session.commit()
    return user, created


def _store_or_rotate_oidc_secret(provider: TenantOidcProvider | None, payload: dict) -> str | None:
    raw_secret = str(payload.get('client_secret') or '').strip()
    if not raw_secret:
        return provider.client_secret_secret_name if provider is not None else None

    secret_name = str(payload.get('client_secret_secret_name') or '').strip()
    if not secret_name:
        base_name = str(payload.get('name') or (provider.name if provider else 'provider')).strip().lower().replace(' ', '-')
        secret_name = f'oidc-{base_name}-client-secret'

    existing = TenantSecret.query.filter_by(
        organization_id=g.tenant.id,
        secret_type='oidc_client',
        name=secret_name,
    ).first()
    if existing is None:
        _, errors = TenantSecretService.create_secret(
            g.tenant.id,
            {
                'secret_type': 'oidc_client',
                'name': secret_name,
                'secret_value': raw_secret,
            },
            current_app.config,
            created_by_user_id=getattr(g, 'current_user', None).id if getattr(g, 'current_user', None) else None,
        )
        if errors:
            raise ValidationError(errors)
    else:
        _, errors, _ = TenantSecretService.rotate_secret(
            g.tenant.id,
            existing.id,
            {'secret_value': raw_secret},
            current_app.config,
        )
        if errors:
            raise ValidationError(errors)

    return secret_name


def _tenant_control_defaults() -> dict:
    return {
        'entitlements': {
            'case_management_v1': {'enabled': True, 'limit_value': None, 'metadata': {}},
        },
        'feature_flags': {
            'incident_case_management_v1': {'enabled': True, 'description': 'Enable incident comments and investigation notes.'},
        },
    }


def _tenant_quota_defaults() -> dict:
    return {
        'monitored_systems': {'limit_value': None, 'is_enforced': False, 'metadata': {'unit': 'systems'}},
        'automation_workflows': {'limit_value': None, 'is_enforced': False, 'metadata': {'unit': 'workflows'}},
        'tenant_secrets': {'limit_value': None, 'is_enforced': False, 'metadata': {'unit': 'secrets'}},
        'enrolled_agents': {'limit_value': None, 'is_enforced': False, 'metadata': {'unit': 'agents'}},
        'alert_rules': {'limit_value': None, 'is_enforced': False, 'metadata': {'unit': 'rules'}},
        'oidc_providers': {'limit_value': None, 'is_enforced': False, 'metadata': {'unit': 'providers'}},
    }


def _get_effective_tenant_controls(organization_id: int) -> dict:
    defaults = _tenant_control_defaults()
    effective = {
        'entitlements': {key: dict(value) for key, value in defaults['entitlements'].items()},
        'feature_flags': {key: dict(value) for key, value in defaults['feature_flags'].items()},
    }

    entitlements = TenantEntitlement.query.filter_by(organization_id=organization_id).order_by(TenantEntitlement.entitlement_key.asc()).all()
    flags = TenantFeatureFlag.query.filter_by(organization_id=organization_id).order_by(TenantFeatureFlag.flag_key.asc()).all()

    for entitlement in entitlements:
        effective['entitlements'][entitlement.entitlement_key] = {
            'enabled': bool(entitlement.is_enabled),
            'limit_value': entitlement.limit_value,
            'metadata': entitlement.metadata_json or {},
        }

    for flag in flags:
        effective['feature_flags'][flag.flag_key] = {
            'enabled': bool(flag.is_enabled),
            'description': flag.description,
        }

    return {
        'defaults': defaults,
        'effective': effective,
        'entitlement_rows': [item.to_dict() for item in entitlements],
        'feature_flag_rows': [item.to_dict() for item in flags],
    }


def _get_effective_tenant_quotas(organization_id: int) -> dict:
    defaults = _tenant_quota_defaults()
    effective = {key: dict(value) for key, value in defaults.items()}
    rows = (
        TenantQuotaPolicy.query
        .filter_by(organization_id=organization_id)
        .order_by(TenantQuotaPolicy.quota_key.asc())
        .all()
    )
    for item in rows:
        effective[item.quota_key] = {
            'limit_value': item.limit_value,
            'is_enforced': bool(item.is_enforced),
            'metadata': item.metadata_json or {},
        }
    return {
        'defaults': defaults,
        'effective': effective,
        'quota_rows': [item.to_dict() for item in rows],
    }


def _compute_usage_snapshot(organization_id: int) -> dict[str, dict]:
    return {
        'monitored_systems': {
            'current_value': SystemData.query.filter_by(organization_id=organization_id).count(),
            'metadata': {'source': 'system_data'},
        },
        'automation_workflows': {
            'current_value': AutomationWorkflow.query.filter_by(organization_id=organization_id).count(),
            'metadata': {'source': 'automation_workflows'},
        },
        'tenant_secrets': {
            'current_value': TenantSecret.query.filter_by(organization_id=organization_id, status='active').count(),
            'metadata': {'source': 'tenant_secrets', 'status': 'active'},
        },
        'enrolled_agents': {
            'current_value': Agent.query.filter_by(organization_id=organization_id).count(),
            'metadata': {'source': 'agents'},
        },
        'alert_rules': {
            'current_value': AlertRule.query.filter_by(organization_id=organization_id).count(),
            'metadata': {'source': 'alert_rules'},
        },
        'oidc_providers': {
            'current_value': TenantOidcProvider.query.filter_by(organization_id=organization_id).count(),
            'metadata': {'source': 'tenant_oidc_providers'},
        },
    }


def _sync_tenant_usage_metrics(organization_id: int) -> dict:
    snapshot = _compute_usage_snapshot(organization_id)
    now = datetime.now(UTC).replace(tzinfo=None)
    rows: list[TenantUsageMetric] = []
    for metric_key, item in snapshot.items():
        row = TenantUsageMetric.query.filter_by(organization_id=organization_id, metric_key=metric_key).first()
        if row is None:
            row = TenantUsageMetric(organization_id=organization_id, metric_key=metric_key)
        row.current_value = int(item.get('current_value') or 0)
        row.metadata_json = item.get('metadata') if isinstance(item.get('metadata'), dict) else {}
        row.measured_at = now
        db.session.add(row)
        rows.append(row)
    db.session.commit()
    return {
        'measured_at': now.isoformat(),
        'metrics': [row.to_dict() for row in rows],
        'current': {
            row.metric_key: {
                'current_value': row.current_value,
                'metadata': row.metadata_json or {},
            }
            for row in rows
        },
    }


def _build_tenant_quota_report(organization_id: int, limit: int = 10) -> dict:
    quotas = _get_effective_tenant_quotas(organization_id)
    usage = _sync_tenant_usage_metrics(organization_id)
    report_rows: list[dict] = []
    enforced_count = 0
    over_limit_count = 0
    near_limit_count = 0

    for quota_key, quota in quotas['effective'].items():
        current_value = int(usage['current'].get(quota_key, {}).get('current_value') or 0)
        limit_value = quota.get('limit_value')
        percent_used = None
        status = 'unlimited'
        if limit_value is not None and int(limit_value) >= 0:
            safe_limit = max(int(limit_value), 1)
            percent_used = round((current_value / safe_limit) * 100, 1)
            if current_value > int(limit_value):
                status = 'over_limit'
                over_limit_count += 1
            elif percent_used >= 80:
                status = 'near_limit'
                near_limit_count += 1
            else:
                status = 'ok'
        if quota.get('is_enforced'):
            enforced_count += 1
            if status == 'unlimited':
                status = 'enforced_unlimited'

        report_rows.append({
            'quota_key': quota_key,
            'current_value': current_value,
            'limit_value': limit_value,
            'is_enforced': bool(quota.get('is_enforced')),
            'percent_used': percent_used,
            'status': status,
            'metadata': quota.get('metadata') or {},
            'usage_metadata': usage['current'].get(quota_key, {}).get('metadata') or {},
        })

    enforcement_events = (
        AuditEvent.query
        .filter(
            ((AuditEvent.tenant_id == organization_id) | (AuditEvent.tenant_id.is_(None)))
            & (AuditEvent.action == 'quota.enforce')
            & (AuditEvent.outcome == 'failure')
        )
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
        .limit(limit)
        .all()
    )
    recent_enforcement_events = [
        {
            'id': event.id,
            'created_at': event.created_at.isoformat() if event.created_at else None,
            'quota_key': (event.event_metadata or {}).get('quota_key'),
            'details': (
                (event.event_metadata or {}).get('details')
                if isinstance((event.event_metadata or {}).get('details'), dict)
                else (
                    ast.literal_eval((event.event_metadata or {}).get('details'))
                    if isinstance((event.event_metadata or {}).get('details'), str)
                    and str((event.event_metadata or {}).get('details')).startswith('{')
                    else None
                )
            ),
            'metadata': event.event_metadata or {},
        }
        for event in enforcement_events
    ]

    report_rows.sort(key=lambda item: (0 if item['status'] == 'over_limit' else 1 if item['status'] == 'near_limit' else 2, item['quota_key']))
    return {
        'generated_at': datetime.now(UTC).isoformat(),
        'summary': {
            'quota_count': len(report_rows),
            'enforced_count': enforced_count,
            'over_limit_count': over_limit_count,
            'near_limit_count': near_limit_count,
            'recent_enforcement_count': len(recent_enforcement_events),
        },
        'quotas': report_rows,
        'recent_enforcement_events': recent_enforcement_events,
    }


def _get_or_create_tenant_commercial_profile(organization_id: int) -> tuple[TenantPlan, TenantBillingProfile, TenantLicense]:
    plan = TenantPlan.query.filter_by(organization_id=organization_id).first()
    billing = TenantBillingProfile.query.filter_by(organization_id=organization_id).first()
    license_row = TenantLicense.query.filter_by(organization_id=organization_id).first()
    changed = False
    if plan is None:
        plan = TenantPlan(
            organization_id=organization_id,
            plan_key='starter',
            display_name='Starter',
            status='active',
            metadata_json={},
        )
        db.session.add(plan)
        changed = True
    if billing is None:
        billing = TenantBillingProfile(
            organization_id=organization_id,
            provider_name='manual',
            metadata_json={},
        )
        db.session.add(billing)
        changed = True
    if license_row is None:
        license_row = TenantLicense(
            organization_id=organization_id,
            license_status='draft',
            enforcement_mode='advisory',
            metadata_json={},
        )
        db.session.add(license_row)
        changed = True
    if changed:
        db.session.commit()
    return plan, billing, license_row


def _commercial_provider_catalog() -> dict[str, dict]:
    return {
        'manual': {
            'kind': 'manual',
            'supports_customer_sync': False,
            'supports_subscription_sync': False,
            'supports_license_sync': False,
        },
        'stripe': {
            'kind': 'billing_provider',
            'supports_customer_sync': True,
            'supports_subscription_sync': True,
            'supports_license_sync': False,
        },
        'paddle': {
            'kind': 'billing_provider',
            'supports_customer_sync': True,
            'supports_subscription_sync': True,
            'supports_license_sync': False,
        },
        'test_billing_double': {
            'kind': 'test_double',
            'supports_customer_sync': True,
            'supports_subscription_sync': True,
            'supports_license_sync': True,
        },
    }


def _build_tenant_commercial_provider_boundary(plan: TenantPlan, billing: TenantBillingProfile, license_row: TenantLicense) -> dict:
    provider_name = (billing.provider_name or 'manual').strip() or 'manual'
    provider_catalog = _commercial_provider_catalog()
    provider_info = provider_catalog.get(provider_name, {
        'kind': 'unknown',
        'supports_customer_sync': False,
        'supports_subscription_sync': False,
        'supports_license_sync': False,
    })

    customer_ready = bool(billing.provider_customer_ref or plan.external_customer_ref)
    subscription_ready = bool(plan.external_subscription_ref)
    license_ready = bool(license_row.license_status in {'trial', 'active', 'expired', 'suspended'})

    return {
        'current_provider': provider_name,
        'provider_capabilities': provider_info,
        'supported_providers': provider_catalog,
        'sync_readiness': {
            'customer_ready': customer_ready,
            'subscription_ready': subscription_ready,
            'license_ready': license_ready,
            'can_sync_customer': bool(provider_info.get('supports_customer_sync') and customer_ready),
            'can_sync_subscription': bool(provider_info.get('supports_subscription_sync') and subscription_ready),
            'can_sync_license': bool(provider_info.get('supports_license_sync') and license_ready),
        },
        'outbound_contract_preview': {
            'customer': {
                'external_customer_ref': billing.provider_customer_ref or plan.external_customer_ref,
                'billing_email': billing.billing_email,
                'billing_name': billing.billing_name,
                'country_code': billing.country_code,
            },
            'subscription': {
                'plan_key': plan.plan_key,
                'display_name': plan.display_name,
                'status': plan.status,
                'billing_cycle': plan.billing_cycle,
                'external_subscription_ref': plan.external_subscription_ref,
            },
            'license': {
                'license_status': license_row.license_status,
                'seat_limit': license_row.seat_limit,
                'enforcement_mode': license_row.enforcement_mode,
                'expires_at': license_row.expires_at.isoformat() if license_row.expires_at else None,
            },
        },
    }


def _serialize_tenant_commercial_profile(organization_id: int) -> dict:
    plan, billing, license_row = _get_or_create_tenant_commercial_profile(organization_id)
    return {
        'plan': plan.to_dict(),
        'billing_profile': billing.to_dict(),
        'license': license_row.to_dict(),
        'contract_boundaries': {
            'entitlements_source': 'tenant_entitlements',
            'quotas_source': 'tenant_quota_policies',
            'billing_source': 'tenant_plans + tenant_billing_profiles',
            'license_source': 'tenant_licenses',
        },
        'provider_boundary': _build_tenant_commercial_provider_boundary(plan, billing, license_row),
        'lifecycle_semantics': {
            'allowed_plan_statuses': ['draft', 'trial', 'active', 'past_due', 'suspended', 'canceled'],
            'allowed_billing_cycles': ['monthly', 'annual', 'usage_based'],
            'allowed_license_statuses': ['draft', 'trial', 'active', 'expired', 'suspended'],
            'allowed_enforcement_modes': ['advisory', 'soft_block', 'hard_block'],
        },
    }


def _enforce_tenant_quota(organization_id: int, quota_key: str, prospective_value: int) -> tuple[bool, dict | None]:
    policy = TenantQuotaPolicy.query.filter_by(organization_id=organization_id, quota_key=quota_key).first()
    if policy is None or not bool(policy.is_enforced) or policy.limit_value is None:
        return True, None
    if int(prospective_value) <= int(policy.limit_value):
        return True, None
    return False, {
        'quota_key': quota_key,
        'limit_value': int(policy.limit_value),
        'current_value': max(int(prospective_value) - 1, 0),
        'requested_value': int(prospective_value),
        'message': f"Quota exceeded for {quota_key}. Limit is {int(policy.limit_value)}.",
    }


def _build_operations_timeline(tenant_id: int, limit: int) -> list[dict]:
    timeline: list[tuple[datetime, dict]] = []

    audit_events = (
        AuditEvent.query
        .filter((AuditEvent.tenant_id == tenant_id) | (AuditEvent.tenant_id.is_(None)))
        .order_by(AuditEvent.created_at.desc())
        .limit(limit)
        .all()
    )
    for event in audit_events:
        timestamp = event.created_at or datetime.min
        timeline.append((
            timestamp,
            {
                'kind': 'audit_event',
                'id': event.id,
                'timestamp': timestamp.isoformat() if event.created_at else None,
                'title': event.action,
                'status': event.outcome,
                'details': event.event_metadata or {},
            },
        ))

    workflow_runs = (
        WorkflowRun.query
        .filter_by(organization_id=tenant_id)
        .order_by(WorkflowRun.executed_at.desc())
        .limit(limit)
        .all()
    )
    for run in workflow_runs:
        timestamp = run.executed_at or run.created_at or datetime.min
        timeline.append((
            timestamp,
            {
                'kind': 'workflow_run',
                'id': run.id,
                'timestamp': timestamp.isoformat() if timestamp else None,
                'title': f"Workflow {run.workflow_id}",
                'status': run.status,
                'details': {
                    'workflow_id': run.workflow_id,
                    'trigger_source': run.trigger_source,
                    'dry_run': run.dry_run,
                    'task_id': run.task_id,
                    'error_reason': run.error_reason,
                },
            },
        ))

    deliveries = (
        NotificationDelivery.query
        .filter_by(organization_id=tenant_id)
        .order_by(NotificationDelivery.created_at.desc())
        .limit(limit)
        .all()
    )
    for delivery in deliveries:
        timestamp = delivery.created_at or datetime.min
        timeline.append((
            timestamp,
            {
                'kind': 'notification_delivery',
                'id': delivery.id,
                'timestamp': timestamp.isoformat() if delivery.created_at else None,
                'title': 'Alert delivery',
                'status': delivery.status,
                'details': {
                    'delivery_scope': delivery.delivery_scope,
                    'channels_requested': delivery.channels_requested or [],
                    'delivered_channels': delivery.delivered_channels or [],
                    'failure_count': delivery.failure_count,
                },
            },
        ))

    incidents = (
        IncidentRecord.query
        .filter_by(organization_id=tenant_id)
        .order_by(IncidentRecord.last_seen_at.desc())
        .limit(limit)
        .all()
    )
    for incident in incidents:
        timestamp = incident.last_seen_at or incident.created_at or datetime.min
        timeline.append((
            timestamp,
            {
                'kind': 'incident',
                'id': incident.id,
                'timestamp': timestamp.isoformat() if timestamp else None,
                'title': incident.title,
                'status': incident.status,
                'details': {
                    'severity': incident.severity,
                    'hostname': incident.hostname,
                    'assigned_to_user_id': incident.assigned_to_user_id,
                },
            },
        ))

    timeline.sort(key=lambda item: item[0], reverse=True)
    return [item for _, item in timeline[:limit]]


def _build_alerts_stream_snapshot(tenant_id: int, limit: int) -> dict:
    deliveries = NotificationDelivery.query.filter_by(organization_id=tenant_id).order_by(
        NotificationDelivery.created_at.desc()
    ).limit(limit).all()
    incidents = IncidentRecord.query.filter_by(organization_id=tenant_id).order_by(
        IncidentRecord.last_seen_at.desc()
    ).limit(limit).all()

    return {
        'generated_at': datetime.now(UTC).isoformat(),
        'deliveries': [item.to_dict() for item in deliveries],
        'incidents': [item.to_dict() for item in incidents],
        'counts': {
            'deliveries': NotificationDelivery.query.filter_by(organization_id=tenant_id).count(),
            'incidents_total': IncidentRecord.query.filter_by(organization_id=tenant_id).count(),
            'incidents_open': IncidentRecord.query.filter(
                IncidentRecord.organization_id == tenant_id,
                IncidentRecord.status.in_(['open', 'acknowledged']),
            ).count(),
        },
    }


def _sse_message(event: str, data: dict, event_id: str | None = None) -> str:
    lines = [f'event: {event}']
    if event_id:
        lines.append(f'id: {event_id}')
    payload = json.dumps(data, separators=(',', ':'))
    lines.extend(f'data: {line}' for line in payload.splitlines() or ['{}'])
    return '\n'.join(lines) + '\n\n'


def _stream_snapshot_response(event: str, payload_builder, retry_ms: int = 10000) -> Response:
    stream_lifetime = max(int(current_app.config.get('SSE_STREAM_LIFETIME_SECONDS', 25) or 25), 0)
    ping_interval = max(int(current_app.config.get('SSE_STREAM_PING_SECONDS', 10) or 10), 1)
    is_testing = bool(current_app.config.get('TESTING'))

    def generate():
        yield f'retry: {retry_ms}\n\n'
        snapshot = payload_builder()
        yield _sse_message(event, snapshot, event_id=str(int(time.time() * 1000)))

        if is_testing or stream_lifetime == 0:
            return

        deadline = time.monotonic() + stream_lifetime
        while time.monotonic() < deadline:
            time.sleep(min(ping_interval, max(deadline - time.monotonic(), 0)))
            if time.monotonic() >= deadline:
                break
            yield ': keep-alive\n\n'

    response = Response(stream_with_context(generate()), mimetype='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['Connection'] = 'keep-alive'
    response.headers['X-Accel-Buffering'] = 'no'
    return response


def _coerce_log_datetime(value: str | None) -> datetime | None:
    """Normalize observed log timestamps to naive UTC datetimes when possible."""
    text_value = str(value or '').strip()
    if not text_value:
        return None

    if text_value.endswith('Z'):
        text_value = f"{text_value[:-1]}+00:00"

    try:
        parsed = datetime.fromisoformat(text_value)
    except ValueError:
        return None

    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(UTC).replace(tzinfo=None)
    return parsed


def _serialize_log_source_with_summary(source: LogSource) -> dict:
    """Serialize a log source with lightweight investigation summary fields."""
    entry_query = LogEntry.query.filter_by(
        organization_id=source.organization_id,
        log_source_id=source.id,
    )
    entry_count = entry_query.count()
    latest_entry = entry_query.order_by(LogEntry.observed_at.desc(), LogEntry.created_at.desc(), LogEntry.id.desc()).first()
    severity_rows = (
        db.session.query(LogEntry.severity, func.count(LogEntry.id))
        .filter_by(organization_id=source.organization_id, log_source_id=source.id)
        .group_by(LogEntry.severity)
        .all()
    )
    capture_kind_rows = (
        db.session.query(LogEntry.capture_kind, func.count(LogEntry.id))
        .filter_by(organization_id=source.organization_id, log_source_id=source.id)
        .group_by(LogEntry.capture_kind)
        .all()
    )

    payload = source.to_dict()
    payload.update({
        'entry_count': entry_count,
        'last_entry_at': (
            latest_entry.observed_at.isoformat()
            if latest_entry and latest_entry.observed_at
            else latest_entry.created_at.isoformat() if latest_entry and latest_entry.created_at else None
        ),
        'latest_message': latest_entry.message if latest_entry else None,
        'severity_breakdown': {
            str(severity or 'unknown'): count
            for severity, count in severity_rows
        },
        'capture_kinds': {
            str(capture_kind or 'unknown'): count
            for capture_kind, count in capture_kind_rows
        },
    })
    return payload


def _apply_log_entry_filters(query, organization_id: int, filters: dict | None = None):
    """Apply shared tenant-scoped log entry filters from query args or a saved filter snapshot."""
    query = query.filter_by(organization_id=organization_id)
    filters = filters or {}

    source_id = filters.get('source_id') if filters else request.args.get('source_id')
    if source_id and str(source_id).isdigit():
        query = query.filter_by(log_source_id=int(source_id))

    source_name = str((filters.get('source_name') if filters else request.args.get('source_name')) or '').strip()
    if source_name:
        query = query.filter(LogEntry.source_name == source_name)

    severity = str((filters.get('severity') if filters else request.args.get('severity')) or '').strip().lower()
    if severity:
        query = query.filter(LogEntry.severity == severity)

    capture_kind = str((filters.get('capture_kind') if filters else request.args.get('capture_kind')) or '').strip()
    if capture_kind:
        query = query.filter(LogEntry.capture_kind == capture_kind)

    event_id = str((filters.get('event_id') if filters else request.args.get('event_id')) or '').strip()
    if event_id:
        query = query.filter(LogEntry.event_id == event_id)

    query_text = str((filters.get('query_text') if filters else request.args.get('query_text')) or '').strip()
    if query_text:
        query = query.filter(
            or_(
                LogEntry.message.ilike(f'%{query_text}%'),
                LogEntry.raw_entry.ilike(f'%{query_text}%'),
            )
        )

    return query


def _persist_correlated_incidents(organization_id: int, correlated_alerts: list[dict]) -> dict[str, list[int] | int]:
    """Upsert durable incident records for correlated alert groups."""
    if not correlated_alerts:
        return {'persisted_count': 0, 'incident_ids': []}

    now = datetime.now(UTC).replace(tzinfo=None)
    incident_ids: list[int] = []

    for item in correlated_alerts:
        metrics = sorted(str(metric) for metric in (item.get('metrics') or []) if metric)
        fingerprint_seed = f"{item.get('system_id') or 'none'}|{item.get('hostname') or 'unknown'}|{','.join(metrics)}"
        fingerprint = sha1(fingerprint_seed.encode('utf-8')).hexdigest()

        incident = (
            IncidentRecord.query
            .filter_by(
                organization_id=organization_id,
                fingerprint=fingerprint,
                status='open',
            )
            .first()
        )

        if incident is None:
            incident = IncidentRecord(
                organization_id=organization_id,
                fingerprint=fingerprint,
                system_id=item.get('system_id'),
                hostname=item.get('hostname'),
                severity=item.get('correlation_severity') or 'warning',
                status='open',
                title=f"Correlated incident on {item.get('hostname') or 'unknown host'}",
                alert_count=int(item.get('alert_count') or 0),
                metric_count=int(item.get('metric_count') or len(metrics)),
                occurrence_count=1,
                metrics=metrics,
                sample_alerts=list(item.get('sample_alerts') or [])[:5],
                first_seen_at=now,
                last_seen_at=now,
            )
            db.session.add(incident)
        else:
            incident.severity = item.get('correlation_severity') or incident.severity
            incident.alert_count = int(item.get('alert_count') or 0)
            incident.metric_count = int(item.get('metric_count') or len(metrics))
            incident.metrics = metrics
            incident.sample_alerts = list(item.get('sample_alerts') or [])[:5]
            incident.last_seen_at = now
            incident.occurrence_count = int(incident.occurrence_count or 0) + 1

        db.session.flush()
        incident_ids.append(incident.id)

    db.session.commit()
    return {
        'persisted_count': len(incident_ids),
        'incident_ids': incident_ids,
    }


def _summarize_reliability_result(diagnostic_type: str, result: dict | None) -> dict:
    """Build a compact operator summary for a reliability execution."""
    result = result or {}
    summary: dict[str, object] = {}

    if diagnostic_type == 'history':
        summary['record_count'] = result.get('record_count', 0)
        records = result.get('records') or []
        if records:
            summary['latest_event'] = (records[0] or {}).get('message')
    elif diagnostic_type == 'score':
        score = result.get('reliability_score') or {}
        summary['current_score'] = score.get('current_score')
        summary['health_band'] = score.get('health_band')
    elif diagnostic_type == 'trend':
        trend = result.get('trend') or {}
        summary['direction'] = trend.get('direction')
        summary['slope'] = trend.get('slope')
    elif diagnostic_type == 'prediction':
        prediction = result.get('prediction') or {}
        summary['predicted_score'] = prediction.get('predicted_score')
        summary['confidence_band'] = prediction.get('confidence_band')
    elif diagnostic_type == 'patterns':
        patterns = result.get('patterns') or {}
        summary['primary_pattern'] = patterns.get('primary_pattern')
        summary['point_count'] = patterns.get('point_count')
    elif diagnostic_type == 'crash_dump_parse':
        parsed = result.get('parsed_dump') or {}
        summary['dump_type'] = parsed.get('dump_type')
        summary['primary_module'] = parsed.get('primary_module')
    elif diagnostic_type == 'exception_identify':
        identified = result.get('identified_exception') or {}
        summary['exception_name'] = identified.get('exception_name')
        summary['confidence'] = identified.get('confidence')
    elif diagnostic_type == 'stack_trace_analyze':
        stack_trace = result.get('stack_trace') or {}
        summary['frame_count'] = stack_trace.get('frame_count')
        summary['top_frame'] = stack_trace.get('top_frame')

    return summary


def _record_reliability_run(
    organization_id: int,
    diagnostic_type: str,
    host_name: str,
    request_payload: dict,
    result: dict | None,
    error: str | None,
    dump_name: str | None = None,
) -> ReliabilityRun:
    """Persist a reliability diagnostic execution for operator history surfaces."""
    run = ReliabilityRun(
        organization_id=organization_id,
        diagnostic_type=diagnostic_type,
        host_name=host_name,
        dump_name=dump_name,
        adapter=(result or {}).get('adapter'),
        status='success' if not error else 'failure',
        error_reason=error,
        request_payload=request_payload or {},
        result_payload=result or {},
        summary=_summarize_reliability_result(diagnostic_type, result),
    )
    db.session.add(run)
    db.session.commit()
    return run


def _serialize_reliability_run_with_related(item: ReliabilityRun) -> dict:
    payload = item.to_dict()
    related_query = ReliabilityRun.query.filter(
        ReliabilityRun.organization_id == item.organization_id,
        ReliabilityRun.id != item.id,
        ReliabilityRun.host_name == item.host_name,
    )
    if item.dump_name:
        related_query = related_query.filter_by(dump_name=item.dump_name)
    related_runs = (
        related_query
        .order_by(ReliabilityRun.created_at.desc(), ReliabilityRun.id.desc())
        .limit(5)
        .all()
    )
    payload['related_runs'] = [related.to_dict() for related in related_runs]
    return payload


def _build_reliability_report(organization_id: int, host_name: str | None = None) -> dict:
    query = ReliabilityRun.query.filter_by(organization_id=organization_id)
    if host_name:
        query = query.filter_by(host_name=host_name)

    runs = query.order_by(ReliabilityRun.created_at.desc(), ReliabilityRun.id.desc()).limit(100).all()
    status_counts: dict[str, int] = {}
    diagnostic_counts: dict[str, int] = {}
    failure_reasons: dict[str, int] = {}
    latest_by_type: dict[str, dict] = {}
    host_counts: dict[str, int] = {}
    recent_failures: list[dict] = []

    for run in runs:
        status_counts[run.status] = status_counts.get(run.status, 0) + 1
        diagnostic_counts[run.diagnostic_type] = diagnostic_counts.get(run.diagnostic_type, 0) + 1
        host_counts[run.host_name] = host_counts.get(run.host_name, 0) + 1
        if run.error_reason:
            failure_reasons[run.error_reason] = failure_reasons.get(run.error_reason, 0) + 1
        latest_by_type.setdefault(run.diagnostic_type, run.to_dict())
        if run.status != 'success' and len(recent_failures) < 5:
            recent_failures.append(run.to_dict())

    latest_score = latest_by_type.get('score', {}).get('summary', {}) if latest_by_type.get('score') else {}
    latest_trend = latest_by_type.get('trend', {}).get('summary', {}) if latest_by_type.get('trend') else {}
    latest_prediction = latest_by_type.get('prediction', {}).get('summary', {}) if latest_by_type.get('prediction') else {}
    crash_related = [
        run.to_dict()
        for run in runs
        if run.diagnostic_type in {'crash_dump_parse', 'exception_identify', 'stack_trace_analyze'}
    ][:6]

    return {
        'status_counts': status_counts,
        'diagnostic_counts': diagnostic_counts,
        'failure_reasons': failure_reasons,
        'host_counts': host_counts,
        'latest_by_type': latest_by_type,
        'latest_score': latest_score,
        'latest_trend': latest_trend,
        'latest_prediction': latest_prediction,
        'crash_related_runs': crash_related,
        'recent_failures': recent_failures,
        'total_runs_considered': len(runs),
    }


def _summarize_update_result(result: dict | None) -> dict:
    """Build a compact operator summary for update monitoring."""
    result = result or {}
    updates = result.get('updates') or []
    classifications: dict[str, int] = {}
    for item in updates:
        if not isinstance(item, dict):
            continue
        classification = str(item.get('classification') or 'other')
        classifications[classification] = classifications.get(classification, 0) + 1

    return {
        'status_summary': result.get('status_summary'),
        'latest_installed_on': result.get('latest_installed_on'),
        'update_count': result.get('update_count', 0),
        'classifications': classifications,
    }


def _record_update_run(
    organization_id: int,
    host_name: str,
    result: dict | None,
    error: str | None,
) -> UpdateRun:
    """Persist a tenant-scoped update monitoring execution."""
    result = result or {}
    run = UpdateRun(
        organization_id=organization_id,
        host_name=host_name,
        adapter=result.get('adapter'),
        status='success' if not error else 'failure',
        error_reason=error,
        update_count=int(result.get('update_count') or 0),
        latest_installed_on=result.get('latest_installed_on'),
        updates_payload=result,
        summary=_summarize_update_result(result),
    )
    db.session.add(run)
    db.session.commit()
    return run


def _serialize_user(user: User) -> dict:
    return {
        'id': user.id,
        'organization_id': user.organization_id,
        'email': user.email,
        'full_name': user.full_name,
        'is_active': user.is_active,
        'roles': [
            {
                'id': role.id,
                'name': role.name,
                'description': role.description,
                'permissions': [permission.code for permission in role.permissions],
            }
            for role in user.roles
        ],
        'created_at': user.created_at.isoformat() if user.created_at else None,
        'updated_at': user.updated_at.isoformat() if user.updated_at else None,
    }


@api_bp.route('/submit_data', methods=['POST'])
@limiter.limit("10 per minute")
@require_api_key
def submit_data():
    """
    Submit system data from agent.
    
    Request JSON:
        - serial_number: System serial number (required)
        - hostname: System hostname (required)
        - system_info: System hardware details (required)
        - performance_metrics: CPU, RAM, disk metrics (required)
        - benchmark_results: Benchmark scores (required)
        - last_update: Last update timestamp (required)
        - status: System status (required)
    
    Returns:
        - 200: Success with submitted data
        - 400: Validation error
        - 401: Missing API key
        - 403: Invalid API key
        - 429: Rate limit exceeded
        - 500: Server error
    """
    try:
        data = request.get_json() or {}
        
        # Log incoming data
        logger.info(f"Received data submission from {request.remote_addr}")
        
        # Validate input data
        try:
            validated_data = validate_and_clean_system_data(data)
        except ValidationError as e:
            logger.warning(f"Validation error: {e.messages}")
            return jsonify({
                'error': 'Validation failed',
                'details': e.messages
            }), 400

        allowed, quota_error = _enforce_tenant_quota(
            g.tenant.id,
            'monitored_systems',
            prospective_value=SystemData.query.filter_by(organization_id=g.tenant.id).count() + 1,
        )
        if not allowed:
            log_audit_event('quota.enforce', outcome='failure', quota_key='monitored_systems', details=quota_error)
            return jsonify({'error': 'Quota exceeded', 'details': {'quota': quota_error}}), 403
        
        # Create and save new system data record
        validated_data['organization_id'] = g.tenant.id
        new_system = SystemData(**validated_data)
        db.session.add(new_system)
        db.session.commit()
        
        logger.info(f"Data saved for system: {validated_data.get('hostname')}")
        
        return jsonify({
            'status': 'success',
            'message': 'Data submitted successfully',
            'system_id': new_system.id
        }), 200
    
    except Exception as e:
        logger.error(f"Error submitting data: {e}", exc_info=True)
        db.session.rollback()
        return jsonify({
            'error': 'Data submission failed',
            'details': str(e)
        }), 500


@api_bp.route('/status', methods=['GET'])
@require_api_key_or_permission('dashboard.view')
def status():
    """
    Get API status.
    
    Returns:
        - 200: API is operational
    """
    return jsonify({
        'status': 'operational',
        'message': 'API is running',
        'version': '1.0.0',
        'queue': get_queue_status(current_app),
        'cache': PerformanceService.cache_status(),
        'gateway': {
            'request_id': getattr(g, 'request_id', None),
            'proxy_fix_enabled': bool(current_app.config.get('ENABLE_PROXY_FIX', True)),
        },
    }), 200


@api_bp.route('/performance/cache/status', methods=['GET'])
@require_api_key_or_permission('dashboard.view')
def get_cache_status():
    """Get active cache layer status (Redis/memory) for Phase 4 monitoring."""
    status = PerformanceService.cache_status()
    log_audit_event('performance.cache.status', outcome='success', backend=status.get('backend'))
    return jsonify({'status': 'success', 'cache': status}), 200


@api_bp.route('/database/optimize', methods=['POST'])
@limiter.limit("30 per hour")
@require_api_key_or_permission('tenant.manage')
def optimize_database_queries():
    """Run lightweight database optimization commands for the configured backend."""
    database_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
    try:
        result = PerformanceService.optimize_database(database_uri)
    except Exception as exc:
        db.session.rollback()
        log_audit_event('database.optimize', outcome='failure', reason='optimizer_error', details=str(exc))
        return jsonify({'error': 'Database optimization failed', 'details': str(exc)}), 500

    log_audit_event(
        'database.optimize',
        outcome='success' if result.get('status') == 'success' else 'skipped',
        backend=result.get('backend'),
        action_count=len(result.get('actions', [])),
    )
    status_code = 200 if result.get('status') == 'success' else 202
    return jsonify({'status': 'success', 'optimization': result}), status_code


@api_bp.route('/agent/releases', methods=['GET'])
@require_api_key_or_permission('dashboard.view')
def list_agent_releases_api():
    """List versioned Windows agent releases for API clients."""
    releases = AgentReleaseService.list_releases(current_app.config, current_app.instance_path)
    release_payload = []
    for release in releases:
        item = release.to_dict()
        item['download_url'] = url_for('api.download_agent_release_api', filename=release.filename)
        release_payload.append(item)

    log_audit_event('agent.release.list', outcome='success', release_count=len(release_payload))
    return jsonify({'status': 'success', 'count': len(release_payload), 'releases': release_payload}), 200


@api_bp.route('/agent/releases/upload', methods=['POST'])
@limiter.limit("30 per hour")
@require_api_key_or_permission('tenant.manage')
def upload_agent_release_api():
    """Upload versioned agent release via API (CI/CD friendly endpoint)."""
    release_file = request.files.get('release_file')
    version = str(request.form.get('version') or '').strip()

    if release_file is None:
        log_audit_event('agent.release.upload.api', outcome='failure', reason='file_missing', version=version)
        return jsonify({'error': 'Validation failed', 'details': {'release_file': ['Field required.']}}), 400

    max_mb = int(current_app.config.get('AGENT_RELEASE_MAX_MB', 256))
    max_bytes = max_mb * 1024 * 1024
    if request.content_length and request.content_length > max_bytes:
        log_audit_event('agent.release.upload.api', outcome='failure', reason='file_too_large', version=version)
        return jsonify({'error': 'Validation failed', 'details': {'release_file': [f'Max size is {max_mb} MB.']}}), 400

    try:
        release = AgentReleaseService.save_uploaded_release(
            release_file,
            version,
            current_app.config,
            current_app.instance_path,
        )
    except ValueError as exc:
        log_audit_event('agent.release.upload.api', outcome='failure', reason=str(exc), version=version)
        return jsonify({'error': 'Validation failed', 'details': {'version': [str(exc)]}}), 400
    except Exception as exc:
        log_audit_event('agent.release.upload.api', outcome='failure', reason='server_error', version=version)
        return jsonify({'error': 'Upload failed', 'details': str(exc)}), 500

    payload = release.to_dict()
    payload['download_url'] = url_for('api.download_agent_release_api', filename=release.filename)
    log_audit_event('agent.release.upload.api', outcome='success', version=release.version, filename=release.filename)
    return jsonify({'status': 'success', 'release': payload}), 201


@api_bp.route('/agent/build/status', methods=['GET'])
@require_api_key_or_permission('dashboard.view')
def get_agent_build_status_api():
    """Report whether a server-built agent binary is currently available."""
    binary_path = AgentReleaseService.resolve_built_binary_path(current_app.root_path)
    metadata = _build_artifact_metadata(binary_path)
    payload = {
        'binary_available': binary_path.exists() and binary_path.is_file(),
        'binary_name': binary_path.name,
        **metadata,
    }
    return jsonify({'status': 'success', 'build': payload}), 200


@api_bp.route('/agent/build', methods=['POST'])
@limiter.limit("5 per hour")
@require_api_key_or_permission('tenant.manage')
def build_agent_binary_api():
    """Trigger server-side PyInstaller build for agent binary."""
    result = AgentReleaseService.build_agent_binary(current_app.root_path, timeout_seconds=180)

    if not result.get('success'):
        log_audit_event('agent.build.api', outcome='failure', reason=result.get('reason'), details=result.get('details'))
        reason = str(result.get('reason') or '')
        if reason in {'spec_not_found', 'pyinstaller_missing'}:
            return jsonify({'error': 'Build unavailable', 'details': result}), 503
        if reason == 'build_timeout':
            return jsonify({'error': 'Build timeout', 'details': result}), 504
        return jsonify({'error': 'Build failed', 'details': result}), 500

    log_audit_event('agent.build.api', outcome='success', binary_path=result.get('binary_path'))
    binary_path = AgentReleaseService.resolve_built_binary_path(current_app.root_path)
    metadata = _build_artifact_metadata(binary_path)
    response_status = 'success' if metadata.get('windows_compatible') else 'success_non_windows'
    return jsonify({'status': response_status, 'build': {**result, **metadata}}), 200


@api_bp.route('/agent/build/download', methods=['GET'])
@limiter.limit("30 per hour")
@require_api_key_or_permission('dashboard.view')
def download_built_agent_binary_api():
    """Download latest server-built agent binary."""
    binary_path = AgentReleaseService.resolve_built_binary_path(current_app.root_path)
    if not binary_path.exists() or not binary_path.is_file():
        log_audit_event('agent.build.download.api', outcome='failure', reason='not_found')
        return jsonify({'error': 'Built binary not found'}), 404

    log_audit_event('agent.build.download.api', outcome='success', filename=binary_path.name)
    return send_file(binary_path, as_attachment=True, download_name=binary_path.name)


@api_bp.route('/agent/releases/download/<path:filename>', methods=['GET'])
@require_api_key_or_permission('dashboard.view')
def download_agent_release_api(filename):
    """Download versioned agent release for agent/self-update flows."""
    file_path = AgentReleaseService.resolve_download_path(filename, current_app.config, current_app.instance_path)
    if file_path is None:
        log_audit_event('agent.release.download.api', outcome='failure', reason='not_found', filename=filename)
        abort(404)

    log_audit_event('agent.release.download.api', outcome='success', filename=file_path.name)
    return send_file(file_path, as_attachment=True, download_name=file_path.name)


@api_bp.route('/agent/releases/policy', methods=['GET'])
@require_api_key_or_permission('dashboard.view')
def get_agent_release_policy_api():
    """Return active server-side release policy used by guide endpoint."""
    policy = AgentReleaseService.get_policy(current_app.config, current_app.instance_path)
    return jsonify({'status': 'success', 'policy': policy}), 200


@api_bp.route('/agent/releases/policy', methods=['PUT'])
@limiter.limit("60 per hour")
@require_api_key_or_permission('tenant.manage')
def set_agent_release_policy_api():
    """Set server-side target version for guided upgrade/downgrade."""
    payload = request.get_json(silent=True) or {}
    target_version = str(payload.get('target_version') or '').strip()
    notes = str(payload.get('notes') or '').strip()

    try:
        policy = AgentReleaseService.set_policy(
            target_version,
            notes,
            current_app.config,
            current_app.instance_path,
        )
    except ValueError as exc:
        log_audit_event('agent.release.policy.update', outcome='failure', reason=str(exc), target_version=target_version)
        return jsonify({'error': 'Validation failed', 'details': {'target_version': [str(exc)]}}), 400

    log_audit_event('agent.release.policy.update', outcome='success', target_version=policy.get('target_version'))
    return jsonify({'status': 'success', 'policy': policy}), 200


@api_bp.route('/agent/releases/guide', methods=['GET'])
@require_api_key_or_permission('dashboard.view')
def get_agent_release_guide_api():
    """Return guided update/downgrade decision for a given current version."""
    current_version = str(request.args.get('current_version') or '').strip()
    guide = AgentReleaseService.build_update_guide(current_version, current_app.config, current_app.instance_path)

    for release in guide.get('releases', []):
        release['download_url'] = url_for('api.download_agent_release_api', filename=release.get('filename', ''))
    for release in guide.get('downgrade_candidates', []):
        release['download_url'] = url_for('api.download_agent_release_api', filename=release.get('filename', ''))

    recommended = str(guide.get('recommended_version') or '').strip()
    recommended_release = next((item for item in guide.get('releases', []) if item.get('version') == recommended), None)
    if recommended_release:
        guide['recommended_download_url'] = recommended_release.get('download_url')
    else:
        guide['recommended_download_url'] = None

    log_audit_event(
        'agent.release.guide',
        outcome='success',
        current_version=current_version,
        recommended_version=guide.get('recommended_version'),
        recommended_action=guide.get('action'),
    )
    return jsonify({'status': 'success', 'guide': guide}), 200


# ---------------------------------------------------------------------------
# Remote command execution (T5)
# ---------------------------------------------------------------------------

ALLOWED_COMMAND_TYPES = frozenset({
    'ping',                # diagnostic no-op
    'restart_service',     # payload: {"service_name": "MyService"}
    'restart_agent',       # payload: {"delay_seconds": 1} -> schedules agent restart
    'rotate_logs',         # payload: {"path": "C:/Logs/app.log"}
    'collect_diagnostics', # payload: {} -> agent returns recent log/metric snapshot
    'run_powershell',      # payload: {"script": "Get-Service MyService"} -- requires whitelist
})


def _resolve_org_id_from_context() -> int | None:
    """Best-effort tenant id lookup from request context."""
    org = getattr(g, 'organization', None)
    if org and getattr(org, 'id', None):
        return int(org.id)
    user = getattr(g, 'current_user', None)
    if user and getattr(user, 'organization_id', None):
        return int(user.organization_id)
    # Fallback to default tenant.
    default_org = Organization.query.filter_by(slug=current_app.config.get('DEFAULT_TENANT_SLUG', 'default')).first()
    return int(default_org.id) if default_org else None


@api_bp.route('/agent/commands', methods=['POST'])
@limiter.limit("60 per hour")
@require_api_key_or_permission('automation.manage')
def queue_agent_command_api():
    """Admin queues a remote command for an agent. Whitelisted command types only."""
    payload = request.get_json(silent=True) or {}
    command_type = (payload.get('command_type') or '').strip()
    target_serial = (payload.get('target_serial_number') or '').strip() or None
    cmd_payload = payload.get('payload') or {}
    expires_in = int(payload.get('expires_in_seconds') or 3600)

    if command_type not in ALLOWED_COMMAND_TYPES:
        return jsonify({
            'error': 'Validation failed',
            'details': {'command_type': [f'Must be one of: {sorted(ALLOWED_COMMAND_TYPES)}']},
        }), 400

    if not isinstance(cmd_payload, dict):
        return jsonify({'error': 'Validation failed', 'details': {'payload': ['Must be an object.']}}), 400

    org_id = _resolve_org_id_from_context()
    if org_id is None:
        return jsonify({'error': 'Tenant context unavailable'}), 400

    agent_id = None
    if target_serial:
        agent = Agent.query.filter_by(organization_id=org_id, serial_number=target_serial).first()
        if agent:
            agent_id = agent.id

    user = getattr(g, 'current_user', None)
    cmd = AgentCommand(
        organization_id=org_id,
        agent_id=agent_id,
        target_serial_number=target_serial,
        command_type=command_type,
        payload=cmd_payload,
        status='pending',
        requested_by_user_id=getattr(user, 'id', None),
        expires_at=_utcnow_naive() + _timedelta_seconds(expires_in),
    )
    db.session.add(cmd)
    db.session.commit()

    log_audit_event('agent.command.queued', outcome='success', command_id=cmd.id, command_type=command_type)
    return jsonify({'status': 'success', 'command': cmd.to_dict()}), 201


@api_bp.route('/agent/commands', methods=['GET'])
@require_api_key_or_permission('automation.manage')
def list_agent_commands_api():
    """Admin lists queued/dispatched/completed commands. No side-effects."""
    org_id = _resolve_org_id_from_context()
    if org_id is None:
        return jsonify({'commands': [], 'allowed_command_types': sorted(ALLOWED_COMMAND_TYPES)}), 200

    status_filter = (request.args.get('status') or '').strip().lower() or None
    type_filter = (request.args.get('command_type') or '').strip() or None
    serial_filter = (request.args.get('target_serial_number') or '').strip() or None

    try:
        limit = max(1, min(int(request.args.get('limit') or 50), 200))
    except (TypeError, ValueError):
        limit = 50

    query = AgentCommand.query.filter(AgentCommand.organization_id == org_id)
    if status_filter:
        query = query.filter(AgentCommand.status == status_filter)
    if type_filter:
        query = query.filter(AgentCommand.command_type == type_filter)
    if serial_filter:
        query = query.filter(AgentCommand.target_serial_number == serial_filter)

    rows = query.order_by(AgentCommand.created_at.desc()).limit(limit).all()
    return jsonify({
        'commands': [cmd.to_dict() for cmd in rows],
        'allowed_command_types': sorted(ALLOWED_COMMAND_TYPES),
        'count': len(rows),
    }), 200


@api_bp.route('/agent/commands/pending', methods=['GET'])
@require_api_key_or_permission('dashboard.view')
def list_pending_agent_commands_api():
    """Agent polls this endpoint to fetch its pending commands."""
    serial = (request.args.get('serial_number') or '').strip()
    org_id = _resolve_org_id_from_context()
    if org_id is None:
        return jsonify({'commands': []}), 200

    now = _utcnow_naive()
    query = AgentCommand.query.filter(
        AgentCommand.organization_id == org_id,
        AgentCommand.status == 'pending',
    )
    if serial:
        query = query.filter(
            (AgentCommand.target_serial_number == serial) | (AgentCommand.target_serial_number.is_(None))
        )

    commands = []
    for cmd in query.order_by(AgentCommand.created_at.asc()).limit(25).all():
        if cmd.expires_at and cmd.expires_at < now:
            cmd.status = 'expired'
            cmd.completed_at = now
            continue
        cmd.status = 'dispatched'
        cmd.dispatched_at = now
        commands.append(cmd.to_dict())
    db.session.commit()
    return jsonify({'commands': commands}), 200


@api_bp.route('/agent/commands/<int:command_id>/result', methods=['POST'])
@require_api_key_or_permission('dashboard.view')
def submit_agent_command_result_api(command_id: int):
    """Agent reports the outcome of a previously dispatched command."""
    cmd = AgentCommand.query.get(command_id)
    if cmd is None:
        return jsonify({'error': 'Command not found'}), 404

    payload = request.get_json(silent=True) or {}
    status = (payload.get('status') or '').strip().lower()
    if status not in ('success', 'failure'):
        return jsonify({'error': 'Validation failed', 'details': {'status': ['Must be success or failure.']}}), 400

    cmd.status = 'completed' if status == 'success' else 'failed'
    cmd.result = payload.get('result') if isinstance(payload.get('result'), (dict, list)) else {'raw': payload.get('result')}
    cmd.error_message = (payload.get('error') or None) if status == 'failure' else None
    cmd.completed_at = _utcnow_naive()
    db.session.commit()

    log_audit_event(
        'agent.command.result',
        outcome=status,
        command_id=cmd.id,
        command_type=cmd.command_type,
    )
    return jsonify({'status': 'recorded', 'command': cmd.to_dict()}), 200


# ---------------------------------------------------------------------------
# TLS pinning + API key rotation (T6)
# ---------------------------------------------------------------------------


@api_bp.route('/agent/cert/pin', methods=['GET'])
@require_api_key_or_permission('dashboard.view')
def get_agent_cert_pin_api():
    """Return the active server certificate SHA-256 pin for the tenant, if any."""
    org_id = _resolve_org_id_from_context()
    if org_id is None:
        return jsonify({'pin': None}), 200
    pin = AgentServerPin.query.filter_by(organization_id=org_id, is_active=True).order_by(AgentServerPin.id.desc()).first()
    return jsonify({'pin': pin.to_dict() if pin else None}), 200


@api_bp.route('/agent/cert/pin', methods=['PUT'])
@require_api_key_or_permission('tenant.manage')
def upsert_agent_cert_pin_api():
    """Admin sets/rotates the cert pin. Optional ``label`` for human readability."""
    payload = request.get_json(silent=True) or {}
    sha = (payload.get('cert_sha256') or '').strip().lower().replace(':', '')
    label = (payload.get('label') or '').strip() or None
    if len(sha) != 64 or any(c not in '0123456789abcdef' for c in sha):
        return jsonify({'error': 'Validation failed', 'details': {'cert_sha256': ['Must be 64 hex chars.']}}), 400

    org_id = _resolve_org_id_from_context()
    if org_id is None:
        return jsonify({'error': 'Tenant context unavailable'}), 400

    now = _utcnow_naive()
    AgentServerPin.query.filter_by(organization_id=org_id, is_active=True).update(
        {'is_active': False, 'rotated_at': now}, synchronize_session=False,
    )
    pin = AgentServerPin(organization_id=org_id, cert_sha256=sha, label=label, is_active=True)
    db.session.add(pin)
    db.session.commit()
    log_audit_event('agent.cert.pin.set', outcome='success', pin_id=pin.id)
    return jsonify({'pin': pin.to_dict()}), 200


@api_bp.route('/agent/key/rotate', methods=['POST'])
@require_api_key_or_permission('tenant.manage')
def rotate_agent_key_api():
    """Issue a fresh agent API key. Returns it once; not stored in plaintext.

    The agent immediately persists the new key in its keystore. Old key remains
    valid for ``grace_seconds`` to give the agent a window to apply.
    """
    import secrets

    payload = request.get_json(silent=True) or {}
    grace_seconds = max(0, int(payload.get('grace_seconds') or 300))

    new_key = secrets.token_urlsafe(48)

    log_audit_event(
        'agent.key.rotate',
        outcome='success',
        new_key_fingerprint=sha1(new_key.encode('utf-8')).hexdigest()[:12],
        grace_seconds=grace_seconds,
    )
    return jsonify({
        'new_api_key': new_key,
        'grace_seconds': grace_seconds,
        'rotated_at': datetime.now(UTC).isoformat(),
    }), 200


def _timedelta_seconds(seconds: int):
    from datetime import timedelta
    return timedelta(seconds=int(seconds))


@api_bp.route('/jobs/maintenance', methods=['POST'])
@limiter.limit("20 per hour")
@require_api_key_or_permission('tenant.manage')
def queue_maintenance_job():
    """Queue a maintenance workflow for asynchronous processing."""
    payload = request.get_json(silent=True) or {}
    job_name = (payload.get('job') or '').strip()

    if not job_name:
        log_audit_event('queue.maintenance.enqueue', outcome='failure', reason='job_missing')
        return jsonify({'error': 'Validation failed', 'details': {'job': ['Field required.']}}), 400

    enqueue_kwargs = {}
    if 'retention_days' in payload:
        enqueue_kwargs['retention_days'] = payload.get('retention_days')

    try:
        result = enqueue_maintenance_job(current_app, job_name, **enqueue_kwargs)
    except ValueError:
        log_audit_event('queue.maintenance.enqueue', outcome='failure', reason='unknown_job', job=job_name)
        return jsonify({'error': 'Validation failed', 'details': {'job': ['Unknown maintenance job.']}}), 400
    except Exception as exc:
        logger.error("Failed to enqueue maintenance job '%s': %s", job_name, exc, exc_info=True)
        log_audit_event('queue.maintenance.enqueue', outcome='failure', reason='enqueue_error', job=job_name)
        return jsonify({'error': 'Queue unavailable', 'details': str(exc)}), 503

    if not result.get('accepted'):
        log_audit_event(
            'queue.maintenance.enqueue',
            outcome='failure',
            reason=result.get('reason', 'queue_disabled'),
            job=job_name,
        )
        return jsonify({'error': 'Queue disabled', 'details': result}), 503

    log_audit_event(
        'queue.maintenance.enqueue',
        outcome='success',
        job=job_name,
        task_name=result.get('task_name'),
        task_id=result.get('task_id'),
    )
    return jsonify({'status': 'accepted', 'job': result}), 202


@api_bp.route('/health', methods=['GET'])
def health():
    """
    Health check endpoint (no auth required).
    
    Returns:
        - 200: Service is healthy
    """
    try:
        # Check database connection
        db.session.execute(text('SELECT 1'))
        return jsonify({
            'status': 'healthy',
            'database': 'connected'
        }), 200
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'database': 'disconnected',
            'error': str(e)
        }), 503


@api_bp.route('/tenants', methods=['GET'])
@require_api_key_or_permission('tenant.manage')
def list_tenants():
    """List all tenant organizations."""
    organizations = Organization.query.order_by(Organization.created_at.desc()).all()
    log_audit_event('tenant.list', outcome='success', tenant_count=len(organizations))
    return jsonify({
        'status': 'success',
        'count': len(organizations),
        'tenants': [org.to_dict() for org in organizations],
        'current_tenant': g.tenant.to_dict(),
    }), 200


@api_bp.route('/tenant-settings', methods=['GET'])
@require_api_key_or_permission('tenant.manage')
def get_tenant_settings_api():
    """Return first-class tenant settings for the current tenant."""
    settings = _get_or_create_tenant_settings(g.tenant.id)
    return jsonify({'status': 'success', 'tenant_settings': _serialize_tenant_settings(settings)}), 200


@api_bp.route('/tenant-settings', methods=['PATCH'])
@limiter.limit("30 per hour")
@require_api_key_or_permission('tenant.manage')
def update_tenant_settings_api():
    """Patch bounded groups of tenant settings."""
    payload = request.get_json(silent=True) or {}
    settings = _get_or_create_tenant_settings(g.tenant.id)
    errors = {}

    field_names = [
        'notification_settings',
        'retention_settings',
        'branding_settings',
        'auth_policy',
        'feature_flags',
    ]
    touched = False
    for field_name in field_names:
        if field_name not in payload:
            continue
        value = payload.get(field_name)
        if not isinstance(value, dict):
            errors[field_name] = ['Must be an object.']
            continue
        if field_name == 'auth_policy':
            auth_policy_errors = _validate_auth_policy(value)
            if auth_policy_errors:
                errors[field_name] = ['Contains invalid auth policy values.']
                for key, field_errors in auth_policy_errors.items():
                    errors[f'auth_policy.{key}'] = field_errors
                continue
        setattr(settings, field_name, value)
        touched = True

    if errors:
        log_audit_event('tenant.settings.update', outcome='failure', reason='validation_failed', details=errors)
        return jsonify({'error': 'Validation failed', 'details': errors}), 400

    if touched:
        db.session.add(settings)
        db.session.commit()
        log_audit_event('tenant.settings.update', outcome='success', tenant_settings_id=settings.id)

    return jsonify({'status': 'success', 'tenant_settings': _serialize_tenant_settings(settings)}), 200


@api_bp.route('/auth/oidc/providers', methods=['GET'])
@require_api_key_or_permission('tenant.manage')
def list_oidc_providers_api():
    """List tenant-scoped OIDC providers for auth administration."""
    providers = (
        TenantOidcProvider.query
        .filter_by(organization_id=g.tenant.id)
        .order_by(TenantOidcProvider.name.asc())
        .all()
    )
    return jsonify({
        'status': 'success',
        'count': len(providers),
        'providers': [provider.to_dict() for provider in providers],
    }), 200


@api_bp.route('/auth/oidc/providers', methods=['POST'])
@limiter.limit("30 per hour")
@require_api_key_or_permission('tenant.manage')
def create_oidc_provider_api():
    """Create a tenant-scoped OIDC provider config."""
    allowed, quota_error = _enforce_tenant_quota(
        g.tenant.id,
        'oidc_providers',
        prospective_value=TenantOidcProvider.query.filter_by(organization_id=g.tenant.id).count() + 1,
    )
    if not allowed:
        log_audit_event('quota.enforce', outcome='failure', quota_key='oidc_providers', details=quota_error)
        return jsonify({'error': 'Quota exceeded', 'details': {'quota': quota_error}}), 403

    payload = request.get_json(silent=True) or {}
    errors = _validate_oidc_provider_payload(payload, partial=False)
    if errors:
        log_audit_event('auth.oidc.provider.create', outcome='failure', reason='validation_failed', details=errors)
        return jsonify({'error': 'Validation failed', 'details': errors}), 400

    provider = TenantOidcProvider(
        organization_id=g.tenant.id,
        name=str(payload.get('name') or '').strip(),
        issuer=str(payload.get('issuer') or '').strip(),
        client_id=str(payload.get('client_id') or '').strip(),
        discovery_endpoint=str(payload.get('discovery_endpoint') or '').strip() or None,
        authorization_endpoint=str(payload.get('authorization_endpoint') or '').strip(),
        token_endpoint=str(payload.get('token_endpoint') or '').strip() or None,
        userinfo_endpoint=str(payload.get('userinfo_endpoint') or '').strip() or None,
        scopes=[str(item).strip() for item in (payload.get('scopes') or ['openid', 'profile', 'email']) if str(item).strip()],
        claim_mappings=payload.get('claim_mappings') if isinstance(payload.get('claim_mappings'), dict) else {},
        role_mappings=payload.get('role_mappings') if isinstance(payload.get('role_mappings'), dict) else {},
        test_mode=bool(payload.get('test_mode', False)),
        test_claims=payload.get('test_claims') if isinstance(payload.get('test_claims'), dict) else {},
        is_enabled=bool(payload.get('is_enabled', True)),
        is_default=bool(payload.get('is_default', False)),
    )

    try:
        provider.client_secret_secret_name = _store_or_rotate_oidc_secret(None, payload)
        if provider.is_default:
            (
                TenantOidcProvider.query
                .filter(TenantOidcProvider.organization_id == g.tenant.id, TenantOidcProvider.is_default.is_(True))
                .update({'is_default': False}, synchronize_session=False)
            )
        db.session.add(provider)
        db.session.commit()
        if provider.discovery_endpoint and not provider.test_mode:
            _discover_oidc_provider_metadata(provider)
    except ValidationError as exc:
        db.session.rollback()
        details = exc.messages if isinstance(exc.messages, dict) else {'provider': [str(exc)]}
        log_audit_event('auth.oidc.provider.create', outcome='failure', reason='validation_failed', details=details)
        return jsonify({'error': 'Validation failed', 'details': details}), 400
    except requests.RequestException as exc:
        db.session.rollback()
        db.session.add(provider)
        db.session.commit()
        _record_oidc_discovery(provider, 'error', str(exc))
        details = {'provider': [f'OIDC discovery failed: {exc}']}
        log_audit_event('auth.oidc.provider.create', outcome='failure', reason='discovery_failed', details=details)
        return jsonify({'error': 'OIDC discovery failed', 'details': details, 'provider': provider.to_dict()}), 502
    except Exception:
        db.session.rollback()
        raise

    log_audit_event('auth.oidc.provider.create', outcome='success', provider_id=provider.id, provider_name=provider.name)
    return jsonify({'status': 'success', 'provider': provider.to_dict()}), 201


@api_bp.route('/auth/oidc/providers/<int:provider_id>', methods=['PATCH'])
@limiter.limit("60 per hour")
@require_api_key_or_permission('tenant.manage')
def update_oidc_provider_api(provider_id: int):
    """Patch a tenant-scoped OIDC provider config."""
    provider = _get_oidc_provider_for_tenant(provider_id, g.tenant.id)
    if provider is None:
        return jsonify({'error': 'OIDC provider not found'}), 404

    payload = request.get_json(silent=True) or {}
    errors = _validate_oidc_provider_payload(payload, partial=True)
    if errors:
        log_audit_event('auth.oidc.provider.update', outcome='failure', reason='validation_failed', provider_id=provider_id, details=errors)
        return jsonify({'error': 'Validation failed', 'details': errors}), 400

    for field_name in ['name', 'issuer', 'client_id', 'authorization_endpoint']:
        if field_name in payload:
            setattr(provider, field_name, str(payload.get(field_name) or '').strip())
    if 'discovery_endpoint' in payload:
        provider.discovery_endpoint = str(payload.get('discovery_endpoint') or '').strip() or None
    for field_name in ['token_endpoint', 'userinfo_endpoint']:
        if field_name in payload:
            setattr(provider, field_name, str(payload.get(field_name) or '').strip() or None)
    if 'scopes' in payload:
        provider.scopes = [str(item).strip() for item in (payload.get('scopes') or []) if str(item).strip()]
    if 'claim_mappings' in payload:
        provider.claim_mappings = payload.get('claim_mappings') or {}
    if 'role_mappings' in payload:
        provider.role_mappings = payload.get('role_mappings') or {}
    if 'test_mode' in payload:
        provider.test_mode = bool(payload.get('test_mode'))
    if 'test_claims' in payload:
        provider.test_claims = payload.get('test_claims') or {}
    if 'is_enabled' in payload:
        provider.is_enabled = bool(payload.get('is_enabled'))
    if 'is_default' in payload:
        provider.is_default = bool(payload.get('is_default'))

    try:
        provider.client_secret_secret_name = _store_or_rotate_oidc_secret(provider, payload)
        if provider.is_default:
            (
                TenantOidcProvider.query
                .filter(
                    TenantOidcProvider.organization_id == g.tenant.id,
                    TenantOidcProvider.id != provider.id,
                    TenantOidcProvider.is_default.is_(True),
                )
                .update({'is_default': False}, synchronize_session=False)
        )
        db.session.add(provider)
        db.session.commit()
        if provider.discovery_endpoint and not provider.test_mode:
            _discover_oidc_provider_metadata(provider)
    except ValidationError as exc:
        db.session.rollback()
        details = exc.messages if isinstance(exc.messages, dict) else {'provider': [str(exc)]}
        log_audit_event('auth.oidc.provider.update', outcome='failure', reason='validation_failed', provider_id=provider_id, details=details)
        return jsonify({'error': 'Validation failed', 'details': details}), 400
    except requests.RequestException as exc:
        db.session.rollback()
        db.session.add(provider)
        db.session.commit()
        _record_oidc_discovery(provider, 'error', str(exc))
        details = {'provider': [f'OIDC discovery failed: {exc}']}
        log_audit_event('auth.oidc.provider.update', outcome='failure', reason='discovery_failed', provider_id=provider_id, details=details)
        return jsonify({'error': 'OIDC discovery failed', 'details': details, 'provider': provider.to_dict()}), 502
    except Exception:
        db.session.rollback()
        raise

    log_audit_event('auth.oidc.provider.update', outcome='success', provider_id=provider.id, provider_name=provider.name)
    return jsonify({'status': 'success', 'provider': provider.to_dict()}), 200


@api_bp.route('/auth/oidc/providers/<int:provider_id>/discover', methods=['POST'])
@limiter.limit("30 per hour")
@require_api_key_or_permission('tenant.manage')
def discover_oidc_provider_api(provider_id: int):
    """Fetch OpenID metadata for a configured provider."""
    provider = _get_oidc_provider_for_tenant(provider_id, g.tenant.id)
    if provider is None:
        return jsonify({'error': 'OIDC provider not found'}), 404
    try:
        _discover_oidc_provider_metadata(provider)
    except ValidationError as exc:
        db.session.rollback()
        details = exc.messages if isinstance(exc.messages, dict) else {'provider': [str(exc)]}
        _record_oidc_discovery(provider, 'error', json.dumps(details))
        log_audit_event('auth.oidc.provider.discover', outcome='failure', reason='validation_failed', provider_id=provider_id, details=details)
        return jsonify({'error': 'Validation failed', 'details': details, 'provider': provider.to_dict()}), 400
    except requests.RequestException as exc:
        db.session.rollback()
        _record_oidc_discovery(provider, 'error', str(exc))
        details = {'provider': [f'OIDC discovery failed: {exc}']}
        log_audit_event('auth.oidc.provider.discover', outcome='failure', reason='discovery_failed', provider_id=provider_id, details=details)
        return jsonify({'error': 'OIDC discovery failed', 'details': details, 'provider': provider.to_dict()}), 502

    log_audit_event('auth.oidc.provider.discover', outcome='success', provider_id=provider.id, provider_name=provider.name)
    return jsonify({'status': 'success', 'provider': provider.to_dict()}), 200


@api_bp.route('/auth/oidc/login', methods=['POST'])
@limiter.limit("60 per hour")
def start_oidc_login():
    """Start an OIDC login by returning an authorization URL and signed state."""
    payload = request.get_json(silent=True) or {}
    tenant_slug = str(payload.get('tenant_slug') or request.headers.get('X-Tenant-Slug') or '').strip().lower()
    provider_id = payload.get('provider_id')
    provider_name = str(payload.get('provider_name') or '').strip()
    web_session = bool(payload.get('web_session', False))
    requested_redirect = _validate_relative_redirect_uri(str(payload.get('redirect_uri') or '/app'))

    if not tenant_slug:
        return jsonify({'error': 'Validation failed', 'details': {'tenant_slug': ['Field required.']}}), 400
    tenant = Organization.query.filter_by(slug=tenant_slug, is_active=True).first()
    if tenant is None:
        return jsonify({'error': 'Unauthorized', 'message': 'Tenant not found or inactive'}), 401

    policy = get_effective_auth_policy(tenant.id)
    if not bool(policy.get('oidc_enabled')):
        return jsonify({'error': 'Forbidden', 'message': 'OIDC login is disabled for this tenant'}), 403

    provider_query = TenantOidcProvider.query.filter_by(organization_id=tenant.id, is_enabled=True)
    provider = None
    if provider_id is not None:
        provider = provider_query.filter_by(id=int(provider_id)).first()
    elif provider_name:
        provider = provider_query.filter_by(name=provider_name).first()
    else:
        provider = provider_query.filter_by(is_default=True).first() or provider_query.order_by(TenantOidcProvider.id.asc()).first()
    if provider is None:
        return jsonify({'error': 'OIDC provider not found'}), 404

    if not provider.test_mode and provider.discovery_endpoint and (
        not str(provider.authorization_endpoint or '').strip() or not str(provider.token_endpoint or '').strip()
    ):
        try:
            _discover_oidc_provider_metadata(provider)
        except Exception as exc:  # noqa: BLE001
            details = {'provider': [f'OIDC provider metadata unavailable: {exc}']}
            log_audit_event('auth.oidc.login.start', outcome='failure', reason='discovery_unavailable', tenant_id=tenant.id, provider_id=provider.id, details=details)
            return jsonify({'error': 'OIDC provider metadata unavailable', 'details': details, 'provider': provider.to_dict()}), 502

    state = issue_oidc_state_token(tenant.slug, provider.id, redirect_uri=requested_redirect, web_session=web_session)
    callback_url = url_for('api.oidc_callback', _external=False)
    auth_params = {
        'response_type': 'code',
        'client_id': provider.client_id,
        'redirect_uri': callback_url,
        'scope': ' '.join(provider.scopes or ['openid', 'profile', 'email']),
        'state': state['state_token'],
    }
    auth_url = f"{provider.authorization_endpoint}?{urlencode(auth_params)}"
    if provider.test_mode:
        test_claim_codes = sorted((provider.test_claims or {}).keys())
        selected_code = test_claim_codes[0] if test_claim_codes else 'default'
        auth_url = f"{callback_url}?{urlencode({'state': state['state_token'], 'code': selected_code})}"

    log_audit_event('auth.oidc.login.start', outcome='success', tenant_id=tenant.id, provider_id=provider.id, provider_name=provider.name)
    return jsonify({
        'status': 'success',
        'provider': provider.to_dict(),
        'authorization': {
            'authorization_url': auth_url,
            'callback_url': callback_url,
            'state_token': state['state_token'],
            'mode': 'test' if provider.test_mode else 'external',
            'web_session': web_session,
            'requires_userinfo': not provider.test_mode,
        },
    }), 200


@api_bp.route('/auth/oidc/callback', methods=['GET'])
def oidc_callback():
    """Complete OIDC login for deterministic test-mode and bounded external-provider flows."""
    state_token = str(request.args.get('state') or '').strip()
    code = str(request.args.get('code') or '').strip()
    if not state_token or not code:
        return jsonify({'error': 'Validation failed', 'details': {'required': ['state', 'code']}}), 400

    try:
        state = decode_jwt_token(state_token, expected_type='oidc_state')
    except Exception as exc:  # noqa: BLE001
        return jsonify({'error': 'Unauthorized', 'message': str(exc)}), 401

    tenant = Organization.query.filter_by(slug=str(state.get('tenant_slug') or '').strip().lower(), is_active=True).first()
    if tenant is None:
        return jsonify({'error': 'Unauthorized', 'message': 'Tenant not found or inactive'}), 401

    provider = _get_oidc_provider_for_tenant(int(state.get('provider_id') or 0), tenant.id)
    if provider is None or not provider.is_enabled:
        return jsonify({'error': 'OIDC provider not found'}), 404

    try:
        if provider.test_mode:
            test_claims = provider.test_claims or {}
            claims = test_claims.get(code) or test_claims.get('default')
            if not isinstance(claims, dict):
                return jsonify({'error': 'Unauthorized', 'message': 'Invalid or expired authorization code'}), 401
        else:
            callback_url = url_for('api.oidc_callback', _external=False)
            token_payload = _exchange_external_oidc_code(provider, code, callback_url)
            claims = _fetch_external_oidc_claims(provider, token_payload)
    except ValidationError as exc:
        details = exc.messages if isinstance(exc.messages, dict) else {'provider': [str(exc)]}
        _record_oidc_auth(provider, 'error', json.dumps(details))
        log_audit_event('auth.oidc.callback', outcome='failure', reason='provider_validation_failed', tenant_id=tenant.id, provider_id=provider.id, details=details)
        return jsonify({'error': 'Validation failed', 'details': details, 'provider': provider.to_dict()}), 400
    except requests.RequestException as exc:
        _record_oidc_auth(provider, 'error', str(exc))
        details = {'provider': [f'OIDC external exchange failed: {exc}']}
        log_audit_event('auth.oidc.callback', outcome='failure', reason='external_exchange_failed', tenant_id=tenant.id, provider_id=provider.id, details=details)
        return jsonify({'error': 'OIDC external exchange failed', 'details': details, 'provider': provider.to_dict()}), 502

    try:
        user, created = _upsert_oidc_user(tenant, provider, claims)
    except ValidationError as exc:
        details = exc.messages if isinstance(exc.messages, dict) else {'claims': [str(exc)]}
        _record_oidc_auth(provider, 'error', json.dumps(details))
        log_audit_event('auth.oidc.callback', outcome='failure', reason='claim_validation_failed', tenant_id=tenant.id, provider_id=provider.id, details=details)
        return jsonify({'error': 'Validation failed', 'details': details}), 400

    reset_login_state(user)
    redirect_uri = _validate_relative_redirect_uri(str(state.get('redirect_uri') or '')) or '/app'
    _record_oidc_auth(provider, 'success')
    log_audit_event('auth.oidc.callback', outcome='success', tenant_id=tenant.id, provider_id=provider.id, user_id=user.id, oidc_user_created=created)

    if bool(state.get('web_session')):
        start_web_session(user)
        return redirect(redirect_uri)

    tokens = issue_jwt_tokens(user)
    return jsonify({
        'status': 'success',
        'provider': provider.to_dict(),
        'tokens': tokens,
        'user': _serialize_user(user),
        'redirect_uri': redirect_uri,
        'created_user': created,
    }), 200


@api_bp.route('/tenant-controls', methods=['GET'])
@require_api_key_or_permission('tenant.manage')
def get_tenant_controls_api():
    """Return tenant entitlements and feature flags with effective defaults applied."""
    controls = _get_effective_tenant_controls(g.tenant.id)
    return jsonify({'status': 'success', 'tenant_controls': controls}), 200


@api_bp.route('/tenant-controls', methods=['PATCH'])
@limiter.limit("30 per hour")
@require_api_key_or_permission('tenant.manage')
def update_tenant_controls_api():
    """Patch tenant entitlements and feature flags via durable rows."""
    payload = request.get_json(silent=True) or {}
    entitlement_payload = payload.get('entitlements', {})
    feature_flag_payload = payload.get('feature_flags', {})
    errors = {}

    if entitlement_payload and not isinstance(entitlement_payload, dict):
        errors['entitlements'] = ['Must be an object keyed by entitlement name.']
    if feature_flag_payload and not isinstance(feature_flag_payload, dict):
        errors['feature_flags'] = ['Must be an object keyed by flag name.']

    if errors:
        log_audit_event('tenant.controls.update', outcome='failure', reason='validation_failed', details=errors)
        return jsonify({'error': 'Validation failed', 'details': errors}), 400

    for entitlement_key, config in entitlement_payload.items():
        if not isinstance(config, dict):
            errors[f'entitlements.{entitlement_key}'] = ['Must be an object.']
            continue
        row = TenantEntitlement.query.filter_by(organization_id=g.tenant.id, entitlement_key=entitlement_key).first()
        if row is None:
            row = TenantEntitlement(organization_id=g.tenant.id, entitlement_key=entitlement_key)
        row.is_enabled = bool(config.get('enabled', True))
        row.limit_value = int(config['limit_value']) if config.get('limit_value') not in (None, '') else None
        row.metadata_json = config.get('metadata') if isinstance(config.get('metadata'), dict) else {}
        db.session.add(row)

    for flag_key, config in feature_flag_payload.items():
        if isinstance(config, bool):
            config = {'enabled': config}
        if not isinstance(config, dict):
            errors[f'feature_flags.{flag_key}'] = ['Must be an object or boolean.']
            continue
        row = TenantFeatureFlag.query.filter_by(organization_id=g.tenant.id, flag_key=flag_key).first()
        if row is None:
            row = TenantFeatureFlag(organization_id=g.tenant.id, flag_key=flag_key)
        row.is_enabled = bool(config.get('enabled', True))
        row.description = str(config.get('description') or '').strip() or None
        db.session.add(row)

    if errors:
        db.session.rollback()
        log_audit_event('tenant.controls.update', outcome='failure', reason='validation_failed', details=errors)
        return jsonify({'error': 'Validation failed', 'details': errors}), 400

    db.session.commit()
    controls = _get_effective_tenant_controls(g.tenant.id)
    log_audit_event('tenant.controls.update', outcome='success', entitlement_count=len(controls['entitlement_rows']), feature_flag_count=len(controls['feature_flag_rows']))
    return jsonify({'status': 'success', 'tenant_controls': controls}), 200


@api_bp.route('/tenant-quotas', methods=['GET'])
@require_api_key_or_permission('tenant.manage')
def get_tenant_quotas_api():
    """Return effective tenant quota policies with persisted overrides."""
    quotas = _get_effective_tenant_quotas(g.tenant.id)
    return jsonify({'status': 'success', 'tenant_quotas': quotas}), 200


@api_bp.route('/tenant-quotas', methods=['PATCH'])
@limiter.limit("30 per hour")
@require_api_key_or_permission('tenant.manage')
def update_tenant_quotas_api():
    """Patch tenant quota policies for supported quota keys."""
    payload = request.get_json(silent=True) or {}
    quotas_payload = payload.get('quotas', {})
    if not isinstance(quotas_payload, dict):
        return jsonify({'error': 'Validation failed', 'details': {'quotas': ['Must be an object keyed by quota name.']}}), 400

    errors = {}
    known_keys = set(_tenant_quota_defaults().keys())
    for quota_key, config in quotas_payload.items():
        if quota_key not in known_keys:
            errors[f'quotas.{quota_key}'] = ['Unsupported quota key.']
            continue
        if not isinstance(config, dict):
            errors[f'quotas.{quota_key}'] = ['Must be an object.']
            continue
        if 'limit_value' in config and config.get('limit_value') not in (None, ''):
            if not isinstance(config.get('limit_value'), int) or int(config.get('limit_value')) < 0:
                errors[f'quotas.{quota_key}.limit_value'] = ['Must be a non-negative integer or null.']
        if 'is_enforced' in config and not isinstance(config.get('is_enforced'), bool):
            errors[f'quotas.{quota_key}.is_enforced'] = ['Must be a boolean.']
        if 'metadata' in config and not isinstance(config.get('metadata'), dict):
            errors[f'quotas.{quota_key}.metadata'] = ['Must be an object.']

    if errors:
        log_audit_event('tenant.quotas.update', outcome='failure', reason='validation_failed', details=errors)
        return jsonify({'error': 'Validation failed', 'details': errors}), 400

    for quota_key, config in quotas_payload.items():
        row = TenantQuotaPolicy.query.filter_by(organization_id=g.tenant.id, quota_key=quota_key).first()
        if row is None:
            row = TenantQuotaPolicy(organization_id=g.tenant.id, quota_key=quota_key)
        if 'limit_value' in config:
            row.limit_value = int(config['limit_value']) if config.get('limit_value') not in (None, '') else None
        if 'is_enforced' in config:
            row.is_enforced = bool(config.get('is_enforced'))
        if 'metadata' in config:
            row.metadata_json = config.get('metadata') if isinstance(config.get('metadata'), dict) else {}
        db.session.add(row)

    db.session.commit()
    quotas = _get_effective_tenant_quotas(g.tenant.id)
    log_audit_event('tenant.quotas.update', outcome='success', quota_count=len(quotas['quota_rows']))
    return jsonify({'status': 'success', 'tenant_quotas': quotas}), 200


@api_bp.route('/tenant-usage', methods=['GET'])
@require_api_key_or_permission('tenant.manage')
def get_tenant_usage_api():
    """Return current tenant usage snapshot for quota reporting."""
    usage = _sync_tenant_usage_metrics(g.tenant.id)
    return jsonify({'status': 'success', 'tenant_usage': usage}), 200


@api_bp.route('/tenant-usage/report', methods=['GET'])
@require_api_key_or_permission('tenant.manage')
def get_tenant_usage_report_api():
    """Return operator-facing quota health reporting and recent enforcement visibility."""
    limit = max(min(int(request.args.get('limit', 10) or 10), 25), 1)
    report = _build_tenant_quota_report(g.tenant.id, limit=limit)
    return jsonify({'status': 'success', 'tenant_usage_report': report}), 200


@api_bp.route('/tenant-commercial', methods=['GET'])
@require_api_key_or_permission('tenant.manage')
def get_tenant_commercial_api():
    """Return draft commercial boundaries for plan, billing profile, and license state."""
    commercial = _serialize_tenant_commercial_profile(g.tenant.id)
    return jsonify({'status': 'success', 'tenant_commercial': commercial}), 200


@api_bp.route('/tenant-commercial/provider-boundary', methods=['GET'])
@require_api_key_or_permission('tenant.manage')
def get_tenant_commercial_provider_boundary_api():
    """Return the current billing-provider boundary draft for the tenant commercial profile."""
    plan, billing, license_row = _get_or_create_tenant_commercial_profile(g.tenant.id)
    return jsonify({
        'status': 'success',
        'provider_boundary': _build_tenant_commercial_provider_boundary(plan, billing, license_row),
    }), 200


@api_bp.route('/tenant-commercial', methods=['PATCH'])
@limiter.limit("30 per hour")
@require_api_key_or_permission('tenant.manage')
def update_tenant_commercial_api():
    """Patch tenant commercial draft models without coupling entitlements to billing state."""
    payload = request.get_json(silent=True) or {}
    plan_payload = payload.get('plan', {})
    billing_payload = payload.get('billing_profile', {})
    license_payload = payload.get('license', {})
    errors = {}

    if plan_payload and not isinstance(plan_payload, dict):
        errors['plan'] = ['Must be an object.']
    if billing_payload and not isinstance(billing_payload, dict):
        errors['billing_profile'] = ['Must be an object.']
    if license_payload and not isinstance(license_payload, dict):
        errors['license'] = ['Must be an object.']

    if errors:
        return jsonify({'error': 'Validation failed', 'details': errors}), 400

    plan, billing, license_row = _get_or_create_tenant_commercial_profile(g.tenant.id)
    allowed_plan_statuses = {'draft', 'trial', 'active', 'past_due', 'suspended', 'canceled'}
    allowed_billing_cycles = {'monthly', 'annual', 'usage_based'}
    allowed_license_statuses = {'draft', 'trial', 'active', 'expired', 'suspended'}
    allowed_enforcement_modes = {'advisory', 'soft_block', 'hard_block'}
    allowed_providers = set(_commercial_provider_catalog().keys())

    if 'plan_key' in plan_payload:
        plan.plan_key = str(plan_payload.get('plan_key') or '').strip() or plan.plan_key
    if 'display_name' in plan_payload:
        plan.display_name = str(plan_payload.get('display_name') or '').strip() or plan.display_name
    if 'status' in plan_payload:
        next_status = str(plan_payload.get('status') or '').strip()
        if next_status and next_status not in allowed_plan_statuses:
            errors['plan.status'] = ['Unsupported plan status.']
        elif next_status:
            plan.status = next_status
    if 'billing_cycle' in plan_payload:
        next_cycle = str(plan_payload.get('billing_cycle') or '').strip()
        if next_cycle and next_cycle not in allowed_billing_cycles:
            errors['plan.billing_cycle'] = ['Unsupported billing cycle.']
        else:
            plan.billing_cycle = next_cycle or None
    if 'external_customer_ref' in plan_payload:
        plan.external_customer_ref = str(plan_payload.get('external_customer_ref') or '').strip() or None
    if 'external_subscription_ref' in plan_payload:
        plan.external_subscription_ref = str(plan_payload.get('external_subscription_ref') or '').strip() or None
    if 'effective_from' in plan_payload:
        raw_effective_from = str(plan_payload.get('effective_from') or '').strip()
        if raw_effective_from:
            try:
                plan.effective_from = datetime.fromisoformat(raw_effective_from.replace('Z', '+00:00')).replace(tzinfo=None)
            except ValueError:
                errors['plan.effective_from'] = ['Must be a valid ISO datetime.']
        else:
            plan.effective_from = None
    if 'metadata' in plan_payload and isinstance(plan_payload.get('metadata'), dict):
        plan.metadata_json = plan_payload.get('metadata')

    for field_name in ['billing_email', 'billing_name', 'contact_email', 'country_code', 'provider_name', 'provider_customer_ref', 'tax_id_hint']:
        if field_name in billing_payload:
            setattr(billing, field_name, str(billing_payload.get(field_name) or '').strip() or None)
    if 'metadata' in billing_payload and isinstance(billing_payload.get('metadata'), dict):
        billing.metadata_json = billing_payload.get('metadata')
    if billing.provider_name and billing.provider_name not in allowed_providers:
        errors['billing_profile.provider_name'] = ['Unsupported billing provider.']

    if 'license_status' in license_payload:
        next_license_status = str(license_payload.get('license_status') or '').strip()
        if next_license_status and next_license_status not in allowed_license_statuses:
            errors['license.license_status'] = ['Unsupported license status.']
        elif next_license_status:
            license_row.license_status = next_license_status
    if 'license_key_hint' in license_payload:
        license_row.license_key_hint = str(license_payload.get('license_key_hint') or '').strip() or None
    if 'seat_limit' in license_payload:
        seat_limit = license_payload.get('seat_limit')
        if seat_limit not in (None, ''):
            try:
                parsed_seat_limit = int(seat_limit)
                if parsed_seat_limit < 0:
                    raise ValueError
                license_row.seat_limit = parsed_seat_limit
            except (TypeError, ValueError):
                errors['license.seat_limit'] = ['Must be a non-negative integer or null.']
        else:
            license_row.seat_limit = None
    if 'enforcement_mode' in license_payload:
        next_enforcement_mode = str(license_payload.get('enforcement_mode') or '').strip()
        if next_enforcement_mode and next_enforcement_mode not in allowed_enforcement_modes:
            errors['license.enforcement_mode'] = ['Unsupported enforcement mode.']
        elif next_enforcement_mode:
            license_row.enforcement_mode = next_enforcement_mode
    if 'expires_at' in license_payload:
        raw_expires_at = str(license_payload.get('expires_at') or '').strip()
        if raw_expires_at:
            try:
                license_row.expires_at = datetime.fromisoformat(raw_expires_at.replace('Z', '+00:00')).replace(tzinfo=None)
            except ValueError:
                errors['license.expires_at'] = ['Must be a valid ISO datetime.']
        else:
            license_row.expires_at = None
    if 'metadata' in license_payload and isinstance(license_payload.get('metadata'), dict):
        license_row.metadata_json = license_payload.get('metadata')

    if errors:
        return jsonify({'error': 'Validation failed', 'details': errors}), 400

    db.session.add(plan)
    db.session.add(billing)
    db.session.add(license_row)
    db.session.commit()

    log_audit_event(
        'tenant.commercial.update',
        outcome='success',
        plan_key=plan.plan_key,
        provider_name=billing.provider_name,
        license_status=license_row.license_status,
    )
    commercial = _serialize_tenant_commercial_profile(g.tenant.id)
    return jsonify({'status': 'success', 'tenant_commercial': commercial}), 200


@api_bp.route('/agents', methods=['GET'])
@require_api_key_or_permission('tenant.manage')
def list_agents_api():
    """List tenant-scoped enrolled agents."""
    agents = AgentIdentityService.list_agents(g.tenant.id)
    return jsonify({'status': 'success', 'count': len(agents), 'agents': [agent.to_dict() for agent in agents]}), 200


@api_bp.route('/agents/enrollment-tokens', methods=['POST'])
@limiter.limit("20 per hour")
@require_api_key_or_permission('tenant.manage')
def create_agent_enrollment_token_api():
    """Create a short-lived agent enrollment token."""
    payload = request.get_json(silent=True) or {}
    ttl_hours = int(payload.get('ttl_hours') or current_app.config.get('AGENT_ENROLLMENT_TOKEN_TTL_HOURS', 24))
    token, raw_token = AgentIdentityService.create_enrollment_token(
        organization_id=g.tenant.id,
        created_by_user_id=getattr(getattr(g, 'current_user', None), 'id', None),
        intended_hostname_pattern=payload.get('intended_hostname_pattern'),
        ttl_hours=ttl_hours,
    )
    log_audit_event(
        'agent.enrollment_token.create',
        outcome='success',
        enrollment_token_id=token.id,
        intended_hostname_pattern=token.intended_hostname_pattern,
    )
    return jsonify({
        'status': 'success',
        'enrollment_token': raw_token,
        'token_metadata': token.to_dict(),
    }), 201


@api_bp.route('/agents/enroll', methods=['POST'])
@limiter.limit("60 per hour")
def enroll_agent_api():
    """Enroll an agent using a one-time enrollment token and issue per-agent credential."""
    payload = request.get_json(silent=True) or {}
    result, errors = AgentIdentityService.enroll_agent(
        payload,
        remote_addr=request.remote_addr,
        credential_ttl_days=int(current_app.config.get('AGENT_CREDENTIAL_TTL_DAYS', 365)),
    )
    if errors:
        log_audit_event('agent.enroll', outcome='failure', reason='validation_failed', details=errors)
        return jsonify({'error': 'Validation failed', 'details': errors}), 400

    log_audit_event(
        'agent.enroll',
        outcome='success',
        agent_id=result['agent']['id'],
        agent_serial_number=result['agent']['serial_number'],
    )
    return jsonify({'status': 'success', **result}), 201


@api_bp.route('/tenant-secrets', methods=['GET'])
@require_api_key_or_permission('tenant.manage')
def list_tenant_secrets_api():
    """List tenant secret metadata without exposing plaintext secret material."""
    secrets_payload = TenantSecretService.list_secrets(g.tenant.id)
    return jsonify({
        'status': 'success',
        'count': len(secrets_payload),
        'secrets': [item.to_dict() for item in secrets_payload],
    }), 200


@api_bp.route('/tenant-secrets', methods=['POST'])
@limiter.limit("30 per hour")
@require_api_key_or_permission('tenant.manage')
def create_tenant_secret_api():
    """Create an encrypted tenant-scoped secret."""
    allowed, quota_error = _enforce_tenant_quota(
        g.tenant.id,
        'tenant_secrets',
        prospective_value=TenantSecret.query.filter_by(organization_id=g.tenant.id, status='active').count() + 1,
    )
    if not allowed:
        log_audit_event('quota.enforce', outcome='failure', quota_key='tenant_secrets', details=quota_error)
        return jsonify({'error': 'Quota exceeded', 'details': {'quota': quota_error}}), 403

    payload = request.get_json(silent=True) or {}
    secret, errors = TenantSecretService.create_secret(
        organization_id=g.tenant.id,
        payload=payload,
        config=current_app.config,
        created_by_user_id=getattr(getattr(g, 'current_user', None), 'id', None),
    )
    if errors:
        log_audit_event('tenant.secret.create', outcome='failure', reason='validation_failed', details=errors)
        return jsonify({'error': 'Validation failed', 'details': errors}), 400
    log_audit_event('tenant.secret.create', outcome='success', secret_id=secret.id, secret_type=secret.secret_type, secret_name=secret.name)
    return jsonify({'status': 'success', 'secret': secret.to_dict()}), 201


@api_bp.route('/tenant-secrets/<int:secret_id>/rotate', methods=['POST'])
@limiter.limit("30 per hour")
@require_api_key_or_permission('tenant.manage')
def rotate_tenant_secret_api(secret_id):
    """Rotate an encrypted tenant secret without exposing plaintext on read."""
    payload = request.get_json(silent=True) or {}
    secret, errors, not_found_reason = TenantSecretService.rotate_secret(
        organization_id=g.tenant.id,
        secret_id=secret_id,
        payload=payload,
        config=current_app.config,
    )
    if not_found_reason == 'not_found':
        log_audit_event('tenant.secret.rotate', outcome='failure', reason='not_found', secret_id=secret_id)
        return jsonify({'error': 'Tenant secret not found'}), 404
    if errors:
        log_audit_event('tenant.secret.rotate', outcome='failure', reason='validation_failed', secret_id=secret_id, details=errors)
        return jsonify({'error': 'Validation failed', 'details': errors}), 400
    log_audit_event('tenant.secret.rotate', outcome='success', secret_id=secret.id, secret_type=secret.secret_type)
    return jsonify({'status': 'success', 'secret': secret.to_dict()}), 200


@api_bp.route('/tenant-secrets/<int:secret_id>/revoke', methods=['POST'])
@limiter.limit("30 per hour")
@require_api_key_or_permission('tenant.manage')
def revoke_tenant_secret_api(secret_id):
    """Revoke a tenant secret while keeping metadata for audit/history."""
    revoked = TenantSecretService.revoke_secret(g.tenant.id, secret_id)
    if not revoked:
        log_audit_event('tenant.secret.revoke', outcome='failure', reason='not_found', secret_id=secret_id)
        return jsonify({'error': 'Tenant secret not found'}), 404
    log_audit_event('tenant.secret.revoke', outcome='success', secret_id=secret_id)
    return jsonify({'status': 'success', 'revoked_id': secret_id}), 200


@api_bp.route('/tenants', methods=['POST'])
@limiter.limit("20 per hour")
@require_api_key_or_permission('tenant.manage')
def create_tenant():
    """Create a new tenant organization."""
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    slug = (data.get('slug') or '').strip().lower()

    if not name:
        log_audit_event('tenant.create', outcome='failure', reason='name_missing')
        return jsonify({'error': 'Validation failed', 'details': {'name': ['Missing data for required field.']}}), 400

    if not slug:
        slug = _slugify(name)

    if not slug:
        log_audit_event('tenant.create', outcome='failure', reason='slug_invalid')
        return jsonify({'error': 'Validation failed', 'details': {'slug': ['Could not generate valid slug.']}}), 400

    existing = Organization.query.filter_by(slug=slug).first()
    if existing:
        log_audit_event('tenant.create', outcome='failure', reason='slug_conflict', tenant_slug=slug)
        return jsonify({'error': 'Tenant already exists', 'details': {'slug': [f"Tenant slug '{slug}' already exists."]}}), 409

    org = Organization(name=name, slug=slug, is_active=bool(data.get('is_active', True)))
    db.session.add(org)
    db.session.commit()

    logger.info("Created tenant '%s' (%s)", org.name, org.slug)
    log_audit_event('tenant.create', outcome='success', tenant_id=org.id, tenant_slug=org.slug)
    return jsonify({'status': 'success', 'tenant': org.to_dict()}), 201


@api_bp.route('/tenants/<int:tenant_id>/status', methods=['PATCH'])
@limiter.limit("30 per hour")
@require_api_key_or_permission('tenant.manage')
def update_tenant_status(tenant_id):
    """Activate or deactivate a tenant organization."""
    data = request.get_json() or {}
    if 'is_active' not in data:
        log_audit_event('tenant.status_update', outcome='failure', reason='is_active_missing', tenant_id=tenant_id)
        return jsonify({'error': 'Validation failed', 'details': {'is_active': ['Field required.']}}), 400

    org = db.session.get(Organization, tenant_id)
    if not org:
        log_audit_event('tenant.status_update', outcome='failure', reason='tenant_not_found', tenant_id=tenant_id)
        return jsonify({'error': 'Tenant not found'}), 404

    if org.slug == 'default' and data.get('is_active') is False:
        log_audit_event('tenant.status_update', outcome='failure', reason='default_tenant_deactivate_blocked', tenant_id=tenant_id)
        return jsonify({'error': 'Operation not allowed', 'details': {'tenant': ['Default tenant cannot be deactivated.']}}), 400

    org.is_active = bool(data.get('is_active'))
    db.session.commit()

    logger.info("Updated tenant status '%s' -> %s", org.slug, org.is_active)
    log_audit_event('tenant.status_update', outcome='success', tenant_id=org.id, tenant_slug=org.slug, is_active=org.is_active)
    return jsonify({'status': 'success', 'tenant': org.to_dict()}), 200


@api_bp.route('/users', methods=['GET'])
@require_api_key_or_permission('tenant.manage')
def list_users_api():
    """List tenant-scoped users with role and permission context."""
    users = (
        User.query
        .filter_by(organization_id=g.tenant.id)
        .order_by(User.created_at.desc())
        .all()
    )
    return jsonify({
        'status': 'success',
        'count': len(users),
        'users': [_serialize_user(user) for user in users],
    }), 200


@api_bp.route('/users', methods=['POST'])
@limiter.limit("30 per hour")
@require_api_key_or_permission('tenant.manage')
def create_user_api():
    """Create tenant-scoped user with optional role assignment."""
    payload = request.get_json(silent=True) or {}
    email = (payload.get('email') or '').strip().lower()
    full_name = (payload.get('full_name') or '').strip()
    password = (payload.get('password') or '').strip()
    role_ids = payload.get('role_ids') if isinstance(payload.get('role_ids'), list) else []

    errors = {}
    if not email:
        errors['email'] = ['Field required.']
    if not full_name:
        errors['full_name'] = ['Field required.']
    if not password:
        errors['password'] = ['Field required.']
    elif len(password) < 8:
        errors['password'] = ['Minimum length is 8.']

    if errors:
        log_audit_event('users.create', outcome='failure', reason='validation_failed', details=errors)
        return jsonify({'error': 'Validation failed', 'details': errors}), 400

    existing = User.query.filter_by(organization_id=g.tenant.id, email=email).first()
    if existing:
        log_audit_event('users.create', outcome='failure', reason='email_exists', user_email=email)
        return jsonify({'error': 'User already exists'}), 409

    roles = []
    if role_ids:
        roles = (
            Role.query
            .filter(Role.organization_id == g.tenant.id, Role.id.in_(role_ids))
            .all()
        )
        if len(roles) != len(set(int(rid) for rid in role_ids if isinstance(rid, int) or str(rid).isdigit())):
            return jsonify({'error': 'Validation failed', 'details': {'role_ids': ['One or more role_ids are invalid.']}}), 400

    user = User(
        organization_id=g.tenant.id,
        email=email,
        full_name=full_name,
        password_hash=hash_password(password),
        is_active=bool(payload.get('is_active', True)),
    )
    for role in roles:
        user.roles.append(role)

    db.session.add(user)
    db.session.commit()

    log_audit_event('users.create', outcome='success', user_id=user.id, user_email=user.email)
    return jsonify({'status': 'success', 'user': _serialize_user(user)}), 201


@api_bp.route('/users/<int:user_id>', methods=['PATCH'])
@limiter.limit("60 per hour")
@require_api_key_or_permission('tenant.manage')
def update_user_api(user_id):
    """Patch tenant-scoped user details and role assignments."""
    user = User.query.filter_by(id=user_id, organization_id=g.tenant.id).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    payload = request.get_json(silent=True) or {}

    if 'email' in payload:
        email = str(payload.get('email') or '').strip().lower()
        if not email:
            return jsonify({'error': 'Validation failed', 'details': {'email': ['Field cannot be blank.']}}), 400
        existing = User.query.filter_by(organization_id=g.tenant.id, email=email).first()
        if existing and existing.id != user.id:
            return jsonify({'error': 'User already exists'}), 409
        user.email = email

    if 'full_name' in payload:
        full_name = str(payload.get('full_name') or '').strip()
        if not full_name:
            return jsonify({'error': 'Validation failed', 'details': {'full_name': ['Field cannot be blank.']}}), 400
        user.full_name = full_name

    if 'password' in payload:
        password = str(payload.get('password') or '').strip()
        if len(password) < 8:
            return jsonify({'error': 'Validation failed', 'details': {'password': ['Minimum length is 8.']}}), 400
        user.password_hash = hash_password(password)

    if 'is_active' in payload:
        user.is_active = bool(payload.get('is_active'))

    if 'role_ids' in payload:
        role_ids = payload.get('role_ids')
        if not isinstance(role_ids, list):
            return jsonify({'error': 'Validation failed', 'details': {'role_ids': ['Must be a list.']}}), 400
        roles = (
            Role.query
            .filter(Role.organization_id == g.tenant.id, Role.id.in_(role_ids))
            .all()
        ) if role_ids else []
        if len(roles) != len(set(int(rid) for rid in role_ids if isinstance(rid, int) or str(rid).isdigit())):
            return jsonify({'error': 'Validation failed', 'details': {'role_ids': ['One or more role_ids are invalid.']}}), 400
        user.roles = roles

    db.session.commit()

    log_audit_event('users.update', outcome='success', user_id=user.id, user_email=user.email)
    return jsonify({'status': 'success', 'user': _serialize_user(user)}), 200


@api_bp.route('/roles', methods=['GET'])
@require_api_key_or_permission('tenant.manage')
def list_roles_api():
    """List tenant-scoped roles and associated permissions."""
    roles = Role.query.filter_by(organization_id=g.tenant.id).order_by(Role.name.asc()).all()
    payload = [
        {
            'id': role.id,
            'name': role.name,
            'description': role.description,
            'is_system': role.is_system,
            'permissions': [permission.code for permission in role.permissions],
        }
        for role in roles
    ]
    return jsonify({'status': 'success', 'count': len(payload), 'roles': payload}), 200


@api_bp.route('/permissions', methods=['GET'])
@require_api_key_or_permission('tenant.manage')
def list_permissions_api():
    """List known permission codes."""
    permissions = Permission.query.order_by(Permission.code.asc()).all()
    payload = [
        {
            'id': permission.id,
            'code': permission.code,
            'description': permission.description,
        }
        for permission in permissions
    ]
    return jsonify({'status': 'success', 'count': len(payload), 'permissions': payload}), 200


@api_bp.route('/backups', methods=['GET'])
@require_api_key_or_permission('backup.manage')
def list_backups_api():
    """List available database backups."""
    backups = BackupService.list_backups()
    return jsonify({'status': 'success', 'count': len(backups), 'backups': backups}), 200


@api_bp.route('/backups', methods=['POST'])
@limiter.limit("20 per hour")
@require_api_key_or_permission('backup.manage')
def create_backup_api():
    """Create a database backup."""
    db_path = os.path.join(os.path.dirname(__file__), '..', 'toolboxgalaxy.db')
    result = BackupService.create_backup(db_path)
    if not result.get('success'):
        log_audit_event('backup.create.api', outcome='failure', reason='service_failed', error=result.get('error'))
        return jsonify({'error': 'Backup creation failed', 'details': result.get('error')}), 500

    log_audit_event('backup.create.api', outcome='success', backup_filename=result.get('backup_filename'))
    return jsonify({'status': 'success', 'backup': result}), 201


@api_bp.route('/backups/<path:filename>/restore', methods=['POST'])
@limiter.limit("20 per hour")
@require_api_key_or_permission('backup.manage')
def restore_backup_api(filename):
    """Restore database from a named backup file."""
    safe_filename = secure_filename(filename)
    if not safe_filename:
        return jsonify({'error': 'Validation failed', 'details': {'filename': ['Invalid filename.']}}), 400

    backup_path = os.path.join(BackupService.BACKUP_DIR, safe_filename)
    db_path = os.path.join(os.path.dirname(__file__), '..', 'toolboxgalaxy.db')

    result = BackupService.restore_backup(backup_path, db_path)
    if not result.get('success'):
        status = 404 if 'not found' in str(result.get('error', '')).lower() else 500
        log_audit_event('backup.restore.api', outcome='failure', reason='service_failed', backup_filename=safe_filename, error=result.get('error'))
        return jsonify({'error': 'Backup restore failed', 'details': result.get('error')}), status

    log_audit_event('backup.restore.api', outcome='success', backup_filename=safe_filename)
    return jsonify({'status': 'success', 'restore': result}), 200


@api_bp.route('/backups/<path:filename>/verify', methods=['POST'])
@limiter.limit("20 per hour")
@require_api_key_or_permission('backup.manage')
def verify_backup_api(filename):
    """Verify that a named backup is readable and restorable."""
    safe_filename = secure_filename(filename)
    if not safe_filename:
        return jsonify({'error': 'Validation failed', 'details': {'filename': ['Invalid filename.']}}), 400

    backup_path = os.path.join(BackupService.BACKUP_DIR, safe_filename)
    result = BackupService.verify_backup(backup_path)
    if not result.get('success'):
        status = 404 if 'not found' in str(result.get('error', '')).lower() else 500
        log_audit_event('backup.verify.api', outcome='failure', reason='service_failed', backup_filename=safe_filename, error=result.get('error'))
        return jsonify({'error': 'Backup verification failed', 'details': result.get('error')}), status

    log_audit_event('backup.verify.api', outcome='success', backup_filename=safe_filename)
    return jsonify({'status': 'success', 'verification': result}), 200


@api_bp.route('/backups/<path:filename>/restore-drill', methods=['POST'])
@limiter.limit("20 per hour")
@require_api_key_or_permission('backup.manage')
def run_backup_restore_drill_api(filename):
    """Run a lightweight non-destructive restore drill report for a named backup."""
    safe_filename = secure_filename(filename)
    if not safe_filename:
        return jsonify({'error': 'Validation failed', 'details': {'filename': ['Invalid filename.']}}), 400

    backup_path = os.path.join(BackupService.BACKUP_DIR, safe_filename)
    result = BackupService.run_restore_drill(backup_path)
    if not result.get('success'):
        status = 404 if 'not found' in str((result.get('verification') or {}).get('error', '')).lower() else 500
        log_audit_event('backup.restore_drill.api', outcome='failure', reason='service_failed', backup_filename=safe_filename)
        return jsonify({'error': 'Restore drill failed', 'details': result}), status

    log_audit_event('backup.restore_drill.api', outcome='success', backup_filename=safe_filename)
    return jsonify({'status': 'success', 'restore_drill': result}), 200


@api_bp.route('/supportability/policy', methods=['GET'])
@require_api_key_or_permission('tenant.manage')
def get_supportability_policy_api():
    """Return current supportability retention defaults for operator visibility."""
    retention = _default_retention_settings()
    return jsonify({'status': 'success', 'retention_defaults': retention}), 200


@api_bp.route('/supportability/metrics', methods=['GET'])
@require_api_key_or_permission('tenant.manage')
def get_supportability_metrics_api():
    """Return lightweight platform-supportability metrics for the current tenant."""
    queue_status = get_queue_status(current_app)
    backup_stats = BackupService.get_backup_stats()
    tenant_id = g.tenant.id
    metrics = {
        'tenant_id': tenant_id,
        'queue': queue_status,
        'retention_defaults': _default_retention_settings(),
        'backups': backup_stats,
        'counts': {
            'workflow_runs': WorkflowRun.query.filter_by(organization_id=tenant_id).count(),
            'notification_deliveries': NotificationDelivery.query.filter_by(organization_id=tenant_id).count(),
            'incidents_total': IncidentRecord.query.filter_by(organization_id=tenant_id).count(),
            'incidents_open': IncidentRecord.query.filter(
                IncidentRecord.organization_id == tenant_id,
                IncidentRecord.status.in_(['open', 'acknowledged']),
            ).count(),
            'incidents_resolved': IncidentRecord.query.filter_by(organization_id=tenant_id, status='resolved').count(),
            'log_entries': LogEntry.query.filter_by(organization_id=tenant_id).count(),
        },
    }
    return jsonify({'status': 'success', 'metrics': metrics}), 200


@api_bp.route('/audit-events', methods=['GET'])
@require_api_key_or_permission('tenant.manage')
def list_audit_events_api():
    """List audit events for current tenant with lightweight pagination."""
    page = max(int(request.args.get('page', 1) or 1), 1)
    per_page = max(min(int(request.args.get('per_page', 25) or 25), 100), 1)

    query = AuditEvent.query
    tenant_id = getattr(g.tenant, 'id', None)
    if tenant_id is not None:
        query = query.filter((AuditEvent.tenant_id == tenant_id) | (AuditEvent.tenant_id.is_(None)))

    pagination = query.order_by(AuditEvent.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    items = [
        {
            'id': event.id,
            'created_at': event.created_at.isoformat() if event.created_at else None,
            'action': event.action,
            'outcome': event.outcome,
            'tenant_id': event.tenant_id,
            'user_id': event.user_id,
            'method': event.method,
            'path': event.path,
            'remote_addr': event.remote_addr,
            'metadata': event.event_metadata,
        }
        for event in pagination.items
    ]

    return jsonify({
        'status': 'success',
        'page': page,
        'per_page': per_page,
        'total': pagination.total,
        'pages': pagination.pages,
        'events': items,
    }), 200


@api_bp.route('/operations/timeline', methods=['GET'])
@require_api_key_or_permission('tenant.manage')
def get_operations_timeline_api():
    """Return a merged operator timeline across audit, automation, delivery, and incidents."""
    limit = max(min(int(request.args.get('limit', 50) or 50), 100), 1)
    items = _build_operations_timeline(g.tenant.id, limit)
    return jsonify({'status': 'success', 'count': len(items), 'timeline': items}), 200


@api_bp.route('/operations/timeline/stream', methods=['GET'])
@require_api_key_or_permission('tenant.manage')
def stream_operations_timeline_api():
    """Stream a live-ish tenant-scoped operations timeline snapshot over SSE."""
    limit = max(min(int(request.args.get('limit', 25) or 25), 100), 1)
    return _stream_snapshot_response(
        'operations.timeline.snapshot',
        lambda: (
            lambda items: {
                'generated_at': datetime.now(UTC).isoformat(),
                'timeline': items,
                'count': len(items),
            }
        )(_build_operations_timeline(g.tenant.id, limit)),
    )


@api_bp.route('/automation/workflow-runs', methods=['GET'])
@require_api_key_or_permission('automation.manage')
def list_workflow_runs_api():
    """List tenant-scoped workflow execution history."""
    page = max(int(request.args.get('page', 1) or 1), 1)
    per_page = max(min(int(request.args.get('per_page', 25) or 25), 100), 1)
    query = WorkflowRun.query.filter_by(organization_id=g.tenant.id)

    workflow_id = request.args.get('workflow_id')
    if workflow_id and str(workflow_id).isdigit():
        query = query.filter_by(workflow_id=int(workflow_id))

    status = str(request.args.get('status') or '').strip()
    if status:
        query = query.filter_by(status=status)

    pagination = query.order_by(WorkflowRun.executed_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        'status': 'success',
        'page': page,
        'per_page': per_page,
        'total': pagination.total,
        'pages': pagination.pages,
        'workflow_runs': [item.to_dict() for item in pagination.items],
    }), 200


@api_bp.route('/automation/workflow-runs/<int:run_id>', methods=['GET'])
@require_api_key_or_permission('automation.manage')
def get_workflow_run_api(run_id):
    """Return one workflow execution history record."""
    item = WorkflowRun.query.filter_by(id=run_id, organization_id=g.tenant.id).first()
    if not item:
        return jsonify({'error': 'Workflow run not found'}), 404
    return jsonify({'status': 'success', 'workflow_run': item.to_dict()}), 200


@api_bp.route('/alerts/delivery-history', methods=['GET'])
@require_api_key_or_permission('tenant.manage')
def list_notification_delivery_history_api():
    """List tenant-scoped notification delivery history."""
    page = max(int(request.args.get('page', 1) or 1), 1)
    per_page = max(min(int(request.args.get('per_page', 25) or 25), 100), 1)
    query = NotificationDelivery.query.filter_by(organization_id=g.tenant.id)

    status = str(request.args.get('status') or '').strip()
    if status:
        query = query.filter_by(status=status)

    pagination = query.order_by(NotificationDelivery.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        'status': 'success',
        'page': page,
        'per_page': per_page,
        'total': pagination.total,
        'pages': pagination.pages,
        'deliveries': [item.to_dict() for item in pagination.items],
    }), 200


@api_bp.route('/alerts/stream', methods=['GET'])
@require_api_key_or_permission('tenant.manage')
def stream_alerts_feed_api():
    """Stream tenant-scoped alert delivery + incident snapshots over SSE."""
    limit = max(min(int(request.args.get('limit', 10) or 10), 50), 1)
    return _stream_snapshot_response(
        'alerts.snapshot',
        lambda: _build_alerts_stream_snapshot(g.tenant.id, limit),
    )


@api_bp.route('/alerts/delivery-history/<int:delivery_id>', methods=['GET'])
@require_api_key_or_permission('tenant.manage')
def get_notification_delivery_history_api(delivery_id):
    """Return one notification-delivery history record."""
    item = NotificationDelivery.query.filter_by(id=delivery_id, organization_id=g.tenant.id).first()
    if not item:
        return jsonify({'error': 'Delivery history not found'}), 404
    return jsonify({'status': 'success', 'delivery': item.to_dict()}), 200


@api_bp.route('/alerts/delivery-history/<int:delivery_id>/redeliver', methods=['POST'])
@limiter.limit("20 per hour")
@require_api_key_or_permission('tenant.manage')
def redeliver_notification_history_api(delivery_id):
    """Re-dispatch a historical alert delivery snapshot using the stored channels."""
    item = NotificationDelivery.query.filter_by(id=delivery_id, organization_id=g.tenant.id).first()
    if not item:
        log_audit_event('alerts.delivery.redeliver', outcome='failure', reason='not_found', delivery_id=delivery_id)
        return jsonify({'error': 'Delivery history not found'}), 404

    try:
        result = enqueue_alert_notification_job(
            current_app,
            organization_id=g.tenant.id,
            alerts=list(item.alert_snapshot or []),
            channels=list(item.channels_requested or []),
            deduplicate=False,
        )
    except Exception as exc:
        logger.error("Failed to re-dispatch delivery %s: %s", delivery_id, exc, exc_info=True)
        log_audit_event('alerts.delivery.redeliver', outcome='failure', reason='enqueue_error', delivery_id=delivery_id)
        return jsonify({'error': 'Queue unavailable', 'details': str(exc)}), 503

    if not result.get('accepted'):
        log_audit_event('alerts.delivery.redeliver', outcome='failure', reason=result.get('reason', 'queue_disabled'), delivery_id=delivery_id)
        return jsonify({'error': 'Queue disabled', 'details': result}), 503

    log_audit_event('alerts.delivery.redeliver', outcome='success', delivery_id=delivery_id, task_id=result.get('task_id'))
    return jsonify({'status': 'accepted', 'job': result, 'source_delivery_id': delivery_id}), 202


@api_bp.route('/incidents', methods=['GET'])
@require_api_key_or_permission('dashboard.view')
def list_incidents_api():
    """List tenant-scoped durable incidents."""
    page = max(int(request.args.get('page', 1) or 1), 1)
    per_page = max(min(int(request.args.get('per_page', 25) or 25), 100), 1)
    query = IncidentRecord.query.filter_by(organization_id=g.tenant.id)

    status = str(request.args.get('status') or '').strip()
    if status:
        query = query.filter_by(status=status)

    pagination = query.order_by(IncidentRecord.last_seen_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        'status': 'success',
        'page': page,
        'per_page': per_page,
        'total': pagination.total,
        'pages': pagination.pages,
        'incidents': [item.to_dict() for item in pagination.items],
    }), 200


@api_bp.route('/incidents/<int:incident_id>', methods=['GET'])
@require_api_key_or_permission('dashboard.view')
def get_incident_api(incident_id):
    """Return one durable incident record."""
    item = IncidentRecord.query.filter_by(id=incident_id, organization_id=g.tenant.id).first()
    if not item:
        return jsonify({'error': 'Incident not found'}), 404
    return jsonify({'status': 'success', 'incident': item.to_dict()}), 200


@api_bp.route('/incidents/<int:incident_id>', methods=['PATCH'])
@limiter.limit("40 per hour")
@require_api_key_or_permission('tenant.manage')
def update_incident_api(incident_id):
    """Update operator-facing incident status and ownership fields."""
    item = IncidentRecord.query.filter_by(id=incident_id, organization_id=g.tenant.id).first()
    if not item:
        log_audit_event('incident.update', outcome='failure', reason='not_found', incident_id=incident_id)
        return jsonify({'error': 'Incident not found'}), 404

    payload = request.get_json(silent=True) or {}
    errors = {}

    if 'status' in payload:
        status = str(payload.get('status') or '').strip().lower()
        if status not in {'open', 'acknowledged', 'resolved'}:
            errors['status'] = ['Must be one of open, acknowledged, resolved.']
        else:
            item.status = status
            if status == 'acknowledged':
                item.acknowledged_at = _utcnow_naive()
                item.resolved_at = None
            elif status == 'resolved':
                item.acknowledged_at = item.acknowledged_at or _utcnow_naive()
                item.resolved_at = _utcnow_naive()
            elif status == 'open':
                item.acknowledged_at = None
                item.resolved_at = None

    if 'assigned_to_user_id' in payload:
        assignee = payload.get('assigned_to_user_id')
        if assignee in (None, ''):
            item.assigned_to_user_id = None
        elif str(assignee).isdigit():
            user = User.query.filter_by(id=int(assignee), organization_id=g.tenant.id).first()
            if not user:
                errors['assigned_to_user_id'] = ['User not found for this tenant.']
            else:
                item.assigned_to_user_id = user.id
        else:
            errors['assigned_to_user_id'] = ['Must be an integer or null.']

    if 'resolution_summary' in payload:
        summary = str(payload.get('resolution_summary') or '').strip()
        if summary and len(summary) > 1000:
            errors['resolution_summary'] = ['Must be 1000 characters or fewer.']
        else:
            item.resolution_summary = summary or None

    if errors:
        log_audit_event('incident.update', outcome='failure', reason='validation_failed', incident_id=incident_id, details=errors)
        return jsonify({'error': 'Validation failed', 'details': errors}), 400

    db.session.commit()
    log_audit_event('incident.update', outcome='success', incident_id=item.id, status=item.status, assigned_to_user_id=item.assigned_to_user_id)
    return jsonify({'status': 'success', 'incident': item.to_dict()}), 200


@api_bp.route('/incidents/<int:incident_id>/comments', methods=['GET'])
@require_api_key_or_permission('dashboard.view')
def list_incident_comments_api(incident_id):
    """List case-management comments for one incident."""
    if not tenant_entitlement_enabled(g.tenant.id, 'case_management_v1', default=True):
        return jsonify({'error': 'Entitlement disabled', 'details': {'entitlement': 'case_management_v1'}}), 403
    if not tenant_feature_flag_enabled(g.tenant.id, 'incident_case_management_v1', default=True):
        return jsonify({'error': 'Feature disabled', 'details': {'feature_flag': 'incident_case_management_v1'}}), 403

    incident = IncidentRecord.query.filter_by(id=incident_id, organization_id=g.tenant.id).first()
    if not incident:
        return jsonify({'error': 'Incident not found'}), 404

    comments = (
        IncidentCaseComment.query
        .filter_by(incident_id=incident_id, organization_id=g.tenant.id)
        .order_by(IncidentCaseComment.created_at.desc())
        .all()
    )
    return jsonify({'status': 'success', 'count': len(comments), 'comments': [item.to_dict() for item in comments]}), 200


@api_bp.route('/incidents/<int:incident_id>/comments', methods=['POST'])
@limiter.limit("60 per hour")
@require_api_key_or_permission('tenant.manage')
def create_incident_comment_api(incident_id):
    """Add a lightweight investigation note/comment to an incident."""
    if not tenant_entitlement_enabled(g.tenant.id, 'case_management_v1', default=True):
        log_audit_event('incident.comment.create', outcome='failure', reason='entitlement_disabled', incident_id=incident_id)
        return jsonify({'error': 'Entitlement disabled', 'details': {'entitlement': 'case_management_v1'}}), 403
    if not tenant_feature_flag_enabled(g.tenant.id, 'incident_case_management_v1', default=True):
        log_audit_event('incident.comment.create', outcome='failure', reason='feature_flag_disabled', incident_id=incident_id)
        return jsonify({'error': 'Feature disabled', 'details': {'feature_flag': 'incident_case_management_v1'}}), 403

    incident = IncidentRecord.query.filter_by(id=incident_id, organization_id=g.tenant.id).first()
    if not incident:
        log_audit_event('incident.comment.create', outcome='failure', reason='incident_not_found', incident_id=incident_id)
        return jsonify({'error': 'Incident not found'}), 404

    payload = request.get_json(silent=True) or {}
    body = str(payload.get('body') or '').strip()
    comment_type = str(payload.get('comment_type') or 'note').strip().lower()
    errors = {}

    if not body:
        errors['body'] = ['Field required.']
    elif len(body) > 5000:
        errors['body'] = ['Must be 5000 characters or fewer.']

    if comment_type not in {'note', 'update', 'resolution', 'handoff'}:
        errors['comment_type'] = ['Must be one of note, update, resolution, handoff.']

    if errors:
        log_audit_event('incident.comment.create', outcome='failure', reason='validation_failed', incident_id=incident_id, details=errors)
        return jsonify({'error': 'Validation failed', 'details': errors}), 400

    comment = IncidentCaseComment(
        organization_id=g.tenant.id,
        incident_id=incident_id,
        author_user_id=getattr(getattr(g, 'current_user', None), 'id', None),
        comment_type=comment_type,
        body=body,
    )
    db.session.add(comment)
    db.session.commit()

    log_audit_event('incident.comment.create', outcome='success', incident_id=incident_id, comment_id=comment.id, comment_type=comment.comment_type)
    return jsonify({'status': 'success', 'comment': comment.to_dict()}), 201


@api_bp.route('/auth/register', methods=['POST'])
@limiter.limit("30 per hour")
@require_api_key_or_permission('tenant.manage')
def register_user():
    """Register tenant-scoped user and assign default admin role."""
    data = request.get_json() or {}
    email = (data.get('email') or '').strip().lower()
    full_name = (data.get('full_name') or '').strip()
    password = (data.get('password') or '').strip()

    if not email or not full_name or not password:
        log_audit_event('auth.register', outcome='failure', reason='required_fields_missing')
        return jsonify({
            'error': 'Validation failed',
            'details': {'required': ['email', 'full_name', 'password']}
        }), 400

    policy = get_effective_auth_policy(g.tenant.id)
    password_errors = validate_password_against_policy(password, policy)
    if password_errors:
        log_audit_event('auth.register', outcome='failure', reason='password_policy_failed', email=email)
        return jsonify({'error': 'Validation failed', 'details': {'password': password_errors}}), 400

    existing = User.query.filter_by(organization_id=g.tenant.id, email=email).first()
    if existing:
        log_audit_event('auth.register', outcome='failure', reason='user_exists', email=email)
        return jsonify({'error': 'User already exists'}), 409

    user = User(
        organization_id=g.tenant.id,
        email=email,
        full_name=full_name,
        password_hash=hash_password(password),
        is_active=True,
    )
    admin_role = _get_or_create_default_admin_role(g.tenant.id)
    user.roles.append(admin_role)

    db.session.add(user)
    db.session.commit()

    log_audit_event('auth.register', outcome='success', created_user_id=user.id, created_user_email=user.email)

    return jsonify({
        'status': 'success',
        'user': {
            'id': user.id,
            'organization_id': user.organization_id,
            'email': user.email,
            'full_name': user.full_name,
            'roles': [role.name for role in user.roles],
        }
    }), 201


@api_bp.route('/auth/login', methods=['POST'])
@limiter.limit("60 per hour")
def login_user():
    """Login user and return JWT access/refresh tokens."""
    data = request.get_json() or {}
    email = (data.get('email') or '').strip().lower()
    password = (data.get('password') or '').strip()

    if not email or not password:
        log_audit_event('auth.login', outcome='failure', reason='required_fields_missing')
        return jsonify({'error': 'Validation failed', 'details': {'required': ['email', 'password']}}), 400

    user = User.query.filter_by(organization_id=g.tenant.id, email=email).first()
    if not user or not user.is_active:
        log_audit_event('auth.login', outcome='failure', reason='invalid_credentials', email=email)
        return jsonify({'error': 'Unauthorized', 'message': 'Invalid credentials'}), 401

    if is_user_locked_out(user):
        log_audit_event('auth.login', outcome='failure', reason='lockout_active', email=email, user_id=user.id)
        return jsonify({'error': 'Unauthorized', 'message': 'Account temporarily locked'}), 401

    if not verify_password(password, user.password_hash):
        record_failed_login(user)
        log_audit_event('auth.login', outcome='failure', reason='invalid_credentials', email=email)
        return jsonify({'error': 'Unauthorized', 'message': 'Invalid credentials'}), 401

    reset_login_state(user)
    policy = get_effective_auth_policy(g.tenant.id)
    factor = MfaService.get_factor(user.id, user.organization_id)
    if bool(policy.get('totp_mfa_enabled')) and factor is not None and factor.status == 'active':
        challenge = issue_mfa_challenge_token(user)
        log_audit_event('auth.login', outcome='mfa_required', user_id=user.id, user_email=user.email)
        return jsonify({
            'status': 'mfa_required',
            'challenge_type': 'totp',
            'challenge': challenge,
            'user': {
                'id': user.id,
                'organization_id': user.organization_id,
                'email': user.email,
                'full_name': user.full_name,
                'roles': [role.name for role in user.roles],
            },
        }), 202

    tokens = issue_jwt_tokens(user)
    log_audit_event('auth.login', outcome='success', user_id=user.id, user_email=user.email)
    return jsonify({
        'status': 'success',
        'tokens': tokens,
        'user': {
            'id': user.id,
            'organization_id': user.organization_id,
            'email': user.email,
            'full_name': user.full_name,
            'roles': [role.name for role in user.roles],
        }
    }), 200


@api_bp.route('/auth/change-password', methods=['POST'])
@limiter.limit("10 per hour")
@require_jwt_auth
def change_my_password_api():
    """Authenticated user changes own password (current_password + new_password)."""
    payload = request.get_json(silent=True) or {}
    current_password = (payload.get('current_password') or '').strip()
    new_password = (payload.get('new_password') or '').strip()

    user = g.current_user
    if not current_password or not new_password:
        return jsonify({
            'error': 'Validation failed',
            'details': {'required': ['current_password', 'new_password']},
        }), 400

    if not verify_password(current_password, user.password_hash):
        log_audit_event('auth.change_password', outcome='failure', reason='invalid_current_password',
                        user_id=user.id, user_email=user.email)
        return jsonify({'error': 'Unauthorized', 'message': 'Current password is incorrect.'}), 401

    if new_password == current_password:
        return jsonify({
            'error': 'Validation failed',
            'details': {'new_password': ['Must differ from the current password.']},
        }), 400

    policy = get_effective_auth_policy(user.organization_id)
    password_errors = validate_password_against_policy(new_password, policy)
    if password_errors:
        log_audit_event('auth.change_password', outcome='failure', reason='password_policy_failed',
                        user_id=user.id, user_email=user.email)
        return jsonify({'error': 'Validation failed', 'details': {'new_password': password_errors}}), 400

    user.password_hash = hash_password(new_password)
    user.failed_login_attempts = 0
    user.locked_until = None
    user.auth_token_version = int(user.auth_token_version or 1) + 1
    db.session.commit()

    revoke_token(g.jwt_payload)
    tokens = issue_jwt_tokens(user)
    log_audit_event('auth.change_password', outcome='success',
                    user_id=user.id, user_email=user.email)
    return jsonify({
        'status': 'success',
        'message': 'Password changed; existing sessions revoked.',
        'tokens': tokens,
    }), 200


@api_bp.route('/auth/refresh', methods=['POST'])
@require_refresh_token
def refresh_tokens():
    """Refresh JWT access + refresh tokens using refresh token."""
    revoke_token(g.jwt_payload)
    tokens = issue_jwt_tokens(g.current_user)
    log_audit_event('auth.refresh', outcome='success', user_id=g.current_user.id, user_email=g.current_user.email)
    return jsonify({'status': 'success', 'tokens': tokens}), 200


@api_bp.route('/auth/logout', methods=['POST'])
@require_jwt_auth
def logout_user():
    """Logout by revoking current access token."""
    revoke_token(g.jwt_payload)
    log_audit_event('auth.logout', outcome='success', user_id=g.current_user.id, user_email=g.current_user.email)
    return jsonify({'status': 'success', 'message': 'Logged out successfully'}), 200


@api_bp.route('/users/<int:user_id>/revoke-sessions', methods=['POST'])
@limiter.limit("30 per hour")
@require_api_key_or_permission('tenant.manage')
def revoke_user_sessions_api(user_id):
    """Invalidate all JWT and browser sessions for a tenant-scoped user."""
    user = User.query.filter_by(id=user_id, organization_id=g.tenant.id).first()
    if not user:
        log_audit_event('auth.sessions.revoke', outcome='failure', reason='user_not_found', revoked_user_id=user_id)
        return jsonify({'error': 'User not found'}), 404

    new_version = revoke_user_sessions(user)
    log_audit_event('auth.sessions.revoke', outcome='success', revoked_user_id=user.id, token_version=new_version)
    return jsonify({'status': 'success', 'revoked_user_id': user.id, 'auth_token_version': new_version}), 200


@api_bp.route('/auth/me', methods=['GET'])
@require_jwt_auth
def auth_me():
    """Return authenticated user profile and permissions."""
    user = g.current_user
    permissions = sorted({p.code for role in user.roles for p in role.permissions})
    return jsonify({
        'status': 'success',
        'user': {
            'id': user.id,
            'organization_id': user.organization_id,
            'email': user.email,
            'full_name': user.full_name,
            'is_active': user.is_active,
            'roles': [role.name for role in user.roles],
            'permissions': permissions,
            'mfa': {
                'totp_enabled': bool(user.totp_factor and user.totp_factor.status == 'active'),
            },
        }
    }), 200


@api_bp.route('/auth/mfa/totp', methods=['GET'])
@require_jwt_auth
def get_totp_factor_status():
    """Return current-user TOTP MFA factor status."""
    factor = MfaService.get_factor(g.current_user.id, g.current_user.organization_id)
    return jsonify({
        'status': 'success',
        'totp': {
            'enabled': bool(factor and factor.status == 'active'),
            'status': factor.status if factor else 'not_configured',
            'factor': factor.to_dict() if factor else None,
        },
    }), 200


@api_bp.route('/auth/mfa/totp/enroll', methods=['POST'])
@limiter.limit("20 per hour")
@require_jwt_auth
def enroll_totp_factor():
    """Start or rotate TOTP enrollment for the current user."""
    secret = generate_totp_secret()
    factor = MfaService.create_or_rotate_pending_factor(
        g.current_user.id,
        g.current_user.organization_id,
        secret,
        current_app.config,
    )
    provisioning_uri = build_totp_provisioning_uri(secret, g.current_user.email)
    log_audit_event('auth.mfa.totp.enroll', outcome='success', user_id=g.current_user.id, factor_status=factor.status)
    return jsonify({
        'status': 'success',
        'totp': {
            'enabled': False,
            'status': factor.status,
            'factor': factor.to_dict(),
            'secret': secret,
            'provisioning_uri': provisioning_uri,
        },
    }), 200


@api_bp.route('/auth/mfa/totp/activate', methods=['POST'])
@limiter.limit("30 per hour")
@require_jwt_auth
def activate_totp_factor():
    """Verify a TOTP code and activate the current user's factor."""
    factor = MfaService.get_factor(g.current_user.id, g.current_user.organization_id)
    if factor is None:
        return jsonify({'error': 'MFA enrollment not started'}), 404

    payload = request.get_json(silent=True) or {}
    code = str(payload.get('code') or '').strip()
    if not verify_totp_code(MfaService.decrypt_secret(factor, current_app.config), code):
        log_audit_event('auth.mfa.totp.activate', outcome='failure', reason='invalid_code', user_id=g.current_user.id)
        return jsonify({'error': 'Unauthorized', 'message': 'Invalid TOTP code'}), 401

    factor = MfaService.activate_factor(factor)
    log_audit_event('auth.mfa.totp.activate', outcome='success', user_id=g.current_user.id, factor_status=factor.status)
    return jsonify({'status': 'success', 'totp': {'enabled': True, 'status': factor.status, 'factor': factor.to_dict()}}), 200


@api_bp.route('/auth/mfa/totp/disable', methods=['POST'])
@limiter.limit("20 per hour")
@require_jwt_auth
def disable_totp_factor():
    """Disable current-user TOTP MFA after password confirmation."""
    factor = MfaService.get_factor(g.current_user.id, g.current_user.organization_id)
    if factor is None or factor.status != 'active':
        return jsonify({'error': 'Active MFA factor not found'}), 404

    payload = request.get_json(silent=True) or {}
    current_password = str(payload.get('current_password') or '').strip()
    if not current_password or not verify_password(current_password, g.current_user.password_hash):
        log_audit_event('auth.mfa.totp.disable', outcome='failure', reason='invalid_password', user_id=g.current_user.id)
        return jsonify({'error': 'Unauthorized', 'message': 'Invalid password'}), 401

    factor = MfaService.disable_factor(factor)
    log_audit_event('auth.mfa.totp.disable', outcome='success', user_id=g.current_user.id, factor_status=factor.status)
    return jsonify({'status': 'success', 'totp': {'enabled': False, 'status': factor.status, 'factor': factor.to_dict()}}), 200


@api_bp.route('/auth/mfa/totp/verify-login', methods=['POST'])
@limiter.limit("40 per hour")
def verify_totp_login():
    """Complete MFA-gated login and issue JWT tokens."""
    payload = request.get_json(silent=True) or {}
    challenge_token = str(payload.get('challenge_token') or '').strip()
    code = str(payload.get('code') or '').strip()
    if not challenge_token or not code:
        return jsonify({'error': 'Validation failed', 'details': {'required': ['challenge_token', 'code']}}), 400

    from ..auth import decode_jwt_token

    try:
        challenge_payload = decode_jwt_token(challenge_token, expected_type='mfa_pending')
    except Exception as exc:  # noqa: BLE001
        return jsonify({'error': 'Unauthorized', 'message': str(exc)}), 401

    user = User.query.filter_by(id=int(challenge_payload['sub']), organization_id=int(challenge_payload['organization_id'])).first()
    if not user or not user.is_active:
        return jsonify({'error': 'Unauthorized', 'message': 'User not found or inactive'}), 401
    if int(challenge_payload.get('token_version', 1)) != int(user.auth_token_version or 1):
        return jsonify({'error': 'Token revoked'}), 401

    factor = MfaService.get_factor(user.id, user.organization_id)
    if factor is None or factor.status != 'active':
        return jsonify({'error': 'Unauthorized', 'message': 'Active MFA factor not found'}), 401
    if not verify_totp_code(MfaService.decrypt_secret(factor, current_app.config), code):
        log_audit_event('auth.mfa.totp.verify_login', outcome='failure', reason='invalid_code', user_id=user.id, user_email=user.email)
        return jsonify({'error': 'Unauthorized', 'message': 'Invalid TOTP code'}), 401

    MfaService.mark_used(factor)
    tokens = issue_jwt_tokens(user)
    log_audit_event('auth.mfa.totp.verify_login', outcome='success', user_id=user.id, user_email=user.email)
    return jsonify({
        'status': 'success',
        'tokens': tokens,
        'user': {
            'id': user.id,
            'organization_id': user.organization_id,
            'email': user.email,
            'full_name': user.full_name,
            'roles': [role.name for role in user.roles],
        },
    }), 200


@api_bp.route('/auth/rbac-check', methods=['GET'])
@require_permission('tenant.manage')
def auth_rbac_check():
    """Protected endpoint to validate RBAC permission enforcement."""
    return jsonify({'status': 'success', 'message': 'RBAC permission granted'}), 200


@api_bp.route('/alerts/rules', methods=['GET'])
@require_api_key_or_permission('tenant.manage')
def list_alert_rules():
    """List tenant-scoped alert threshold rules."""
    rules = AlertService.list_rules(g.tenant.id)
    return jsonify({
        'status': 'success',
        'count': len(rules),
        'rules': [rule.to_dict() for rule in rules],
    }), 200


@api_bp.route('/alerts/rules', methods=['POST'])
@limiter.limit("60 per hour")
@require_api_key_or_permission('tenant.manage')
def create_alert_rule():
    """Create new threshold alert rule for current tenant."""
    allowed, quota_error = _enforce_tenant_quota(
        g.tenant.id,
        'alert_rules',
        prospective_value=AlertRule.query.filter_by(organization_id=g.tenant.id).count() + 1,
    )
    if not allowed:
        log_audit_event('quota.enforce', outcome='failure', quota_key='alert_rules', details=quota_error)
        return jsonify({'error': 'Quota exceeded', 'details': {'quota': quota_error}}), 403

    payload = request.get_json(silent=True) or {}
    rule, errors = AlertService.create_rule(g.tenant.id, payload)
    if errors:
        log_audit_event('alerts.rule.create', outcome='failure', reason='validation_failed', details=errors)
        return jsonify({'error': 'Validation failed', 'details': errors}), 400

    log_audit_event('alerts.rule.create', outcome='success', alert_rule_id=rule.id, metric=rule.metric)
    return jsonify({'status': 'success', 'rule': rule.to_dict()}), 201


@api_bp.route('/alerts/rules/<int:rule_id>', methods=['PATCH'])
@limiter.limit("120 per hour")
@require_api_key_or_permission('tenant.manage')
def update_alert_rule(rule_id):
    """Patch tenant alert rule fields."""
    payload = request.get_json(silent=True) or {}
    rule, errors, not_found_reason = AlertService.update_rule(g.tenant.id, rule_id, payload)

    if not_found_reason == 'not_found':
        log_audit_event('alerts.rule.update', outcome='failure', reason='not_found', alert_rule_id=rule_id)
        return jsonify({'error': 'Alert rule not found'}), 404

    if errors:
        log_audit_event('alerts.rule.update', outcome='failure', reason='validation_failed', alert_rule_id=rule_id)
        return jsonify({'error': 'Validation failed', 'details': errors}), 400

    log_audit_event('alerts.rule.update', outcome='success', alert_rule_id=rule.id)
    return jsonify({'status': 'success', 'rule': rule.to_dict()}), 200


@api_bp.route('/alerts/evaluate', methods=['POST'])
@limiter.limit("120 per hour")
@require_api_key_or_permission('dashboard.view')
def evaluate_alert_rules():
    """Evaluate threshold, anomaly, pattern, and correlated alerts for current tenant."""
    payload = request.get_json(silent=True) or {}

    include_threshold_alerts = bool(payload.get('include_threshold_alerts', True))
    include_anomaly_alerts = bool(payload.get('include_anomaly_alerts', True))
    include_pattern_alerts = bool(payload.get('include_pattern_alerts', True))
    include_correlation = bool(payload.get('include_correlation', True))
    apply_silences = bool(payload.get('apply_silences', True))

    threshold_alerts = AlertService.evaluate_rules_for_tenant(g.tenant.id) if include_threshold_alerts else []
    anomaly_alerts = (
        AlertService.evaluate_anomalies_for_tenant(
            g.tenant.id,
            z_score_threshold=float(payload.get('anomaly_z_score_threshold', 2.5)),
            min_samples=int(payload.get('anomaly_min_samples', 8)),
            window_size=int(payload.get('anomaly_window_size', 50)),
        )
        if include_anomaly_alerts
        else []
    )
    pattern_alerts = (
        AlertService.evaluate_patterns_for_tenant(
            g.tenant.id,
            min_occurrences=int(payload.get('pattern_min_occurrences', 3)),
            window_size=int(payload.get('pattern_window_size', 10)),
        )
        if include_pattern_alerts
        else []
    )

    all_alerts = threshold_alerts + anomaly_alerts + pattern_alerts
    silenced_alerts: list = []
    if apply_silences and all_alerts:
        all_alerts, silenced_alerts = AlertService.filter_silenced_alerts(g.tenant.id, all_alerts)

    correlated_alerts = (
        AlertService.correlate_alerts(
            all_alerts,
            min_group_size=int(payload.get('correlation_min_group_size', 2)),
        )
        if include_correlation
        else []
    )
    incident_persistence = _persist_correlated_incidents(g.tenant.id, correlated_alerts)

    log_audit_event(
        'alerts.evaluate',
        outcome='success',
        threshold_count=len(threshold_alerts),
        anomaly_count=len(anomaly_alerts),
        pattern_count=len(pattern_alerts),
        silenced_count=len(silenced_alerts),
        correlated_count=len(correlated_alerts),
        incident_count=incident_persistence.get('persisted_count', 0),
    )

    return jsonify({
        'status': 'success',
        'triggered_count': len(all_alerts),
        'threshold_count': len(threshold_alerts),
        'anomaly_count': len(anomaly_alerts),
        'pattern_count': len(pattern_alerts),
        'silenced_count': len(silenced_alerts),
        'correlated_count': len(correlated_alerts),
        'incident_count': incident_persistence.get('persisted_count', 0),
        'incident_ids': incident_persistence.get('incident_ids', []),
        'alerts': all_alerts,
        'silenced_alerts': silenced_alerts,
        'correlated_alerts': correlated_alerts,
    }), 200


@api_bp.route('/alerts/silences', methods=['GET'])
@require_api_key_or_permission('dashboard.view')
def list_alert_silences():
    """List active alert silence windows for current tenant."""
    silences = AlertService.list_silences(g.tenant.id)
    return jsonify({
        'status': 'success',
        'count': len(silences),
        'silences': [s.to_dict() for s in silences],
    }), 200


@api_bp.route('/alerts/silences', methods=['POST'])
@limiter.limit("60 per hour")
@require_api_key_or_permission('tenant.manage')
def create_alert_silence():
    """Create an alert silence window to suppress alerts during maintenance."""
    payload = request.get_json(silent=True) or {}
    silence, errors = AlertService.create_silence(g.tenant.id, payload)
    if errors:
        log_audit_event('alerts.silence.create', outcome='failure', reason='validation_failed', details=errors)
        return jsonify({'error': 'Validation failed', 'details': errors}), 400
    log_audit_event('alerts.silence.create', outcome='success', silence_id=silence.id, metric=silence.metric, rule_id=silence.rule_id)
    return jsonify({'status': 'success', 'silence': silence.to_dict()}), 201


@api_bp.route('/alerts/silences/<int:silence_id>', methods=['DELETE'])
@limiter.limit("60 per hour")
@require_api_key_or_permission('tenant.manage')
def delete_alert_silence(silence_id):
    """Delete an alert silence window for current tenant."""
    deleted = AlertService.delete_silence(g.tenant.id, silence_id)
    if not deleted:
        log_audit_event('alerts.silence.delete', outcome='failure', reason='not_found', silence_id=silence_id)
        return jsonify({'error': 'Alert silence not found'}), 404
    log_audit_event('alerts.silence.delete', outcome='success', silence_id=silence_id)
    return jsonify({'status': 'success', 'deleted_id': silence_id}), 200


@api_bp.route('/alerts/dispatch', methods=['POST'])
@limiter.limit("60 per hour")
@require_api_key_or_permission('tenant.manage')
def dispatch_alert_notifications():
    """Queue alert notification dispatch (email/webhook) with retry-aware delivery."""
    payload = request.get_json(silent=True) or {}

    channels = payload.get('channels')
    if channels is not None and not isinstance(channels, list):
        log_audit_event('alerts.dispatch.enqueue', outcome='failure', reason='channels_invalid')
        return jsonify({'error': 'Validation failed', 'details': {'channels': ['Must be a list.']}}), 400

    alerts = payload.get('alerts')
    if alerts is not None and not isinstance(alerts, list):
        log_audit_event('alerts.dispatch.enqueue', outcome='failure', reason='alerts_invalid')
        return jsonify({'error': 'Validation failed', 'details': {'alerts': ['Must be a list.']}}), 400

    enqueue_kwargs = {
        'organization_id': g.tenant.id,
        'alerts': alerts,
        'channels': channels,
        'email_retries': payload.get('email_retries'),
        'webhook_retries': payload.get('webhook_retries'),
        'deduplicate': payload.get('deduplicate'),
        'escalation_threshold': payload.get('escalation_threshold'),
    }

    try:
        result = enqueue_alert_notification_job(current_app, **enqueue_kwargs)
    except Exception as exc:
        logger.error("Failed to enqueue alert dispatch: %s", exc, exc_info=True)
        log_audit_event('alerts.dispatch.enqueue', outcome='failure', reason='enqueue_error')
        return jsonify({'error': 'Queue unavailable', 'details': str(exc)}), 503

    if not result.get('accepted'):
        log_audit_event('alerts.dispatch.enqueue', outcome='failure', reason=result.get('reason', 'queue_disabled'))
        return jsonify({'error': 'Queue disabled', 'details': result}), 503

    log_audit_event(
        'alerts.dispatch.enqueue',
        outcome='success',
        task_name=result.get('task_name'),
        task_id=result.get('task_id'),
    )

    return jsonify({'status': 'accepted', 'job': result}), 202


@api_bp.route('/automation/workflows', methods=['GET'])
@require_api_key_or_permission('automation.manage')
def list_automation_workflows():
    """List tenant-scoped automation workflows."""
    workflows = AutomationService.list_workflows(g.tenant.id)
    return jsonify({
        'status': 'success',
        'count': len(workflows),
        'workflows': [workflow.to_dict() for workflow in workflows],
    }), 200


@api_bp.route('/automation/workflows', methods=['POST'])
@limiter.limit("60 per hour")
@require_api_key_or_permission('automation.manage')
def create_automation_workflow():
    """Create a tenant automation workflow."""
    allowed, quota_error = _enforce_tenant_quota(
        g.tenant.id,
        'automation_workflows',
        prospective_value=AutomationWorkflow.query.filter_by(organization_id=g.tenant.id).count() + 1,
    )
    if not allowed:
        log_audit_event('quota.enforce', outcome='failure', quota_key='automation_workflows', details=quota_error)
        return jsonify({'error': 'Quota exceeded', 'details': {'quota': quota_error}}), 403

    payload = request.get_json(silent=True) or {}
    workflow, errors = AutomationService.create_workflow(g.tenant.id, payload)

    if errors:
        log_audit_event('automation.workflow.create', outcome='failure', reason='validation_failed', details=errors)
        return jsonify({'error': 'Validation failed', 'details': errors}), 400

    log_audit_event('automation.workflow.create', outcome='success', workflow_id=workflow.id)
    return jsonify({'status': 'success', 'workflow': workflow.to_dict()}), 201


@api_bp.route('/automation/evaluate', methods=['POST'])
@limiter.limit("120 per hour")
@require_api_key_or_permission('automation.manage')
def evaluate_automation_triggers():
    """Evaluate alert-triggered automation workflows against provided alerts."""
    payload = request.get_json(silent=True) or {}
    alerts = payload.get('alerts')
    if not isinstance(alerts, list):
        log_audit_event('automation.evaluate', outcome='failure', reason='alerts_invalid')
        return jsonify({'error': 'Validation failed', 'details': {'alerts': ['Must be a list.']}}), 400

    matches = AutomationService.evaluate_alert_triggers(g.tenant.id, alerts)
    log_audit_event('automation.evaluate', outcome='success', matched_workflows=len(matches), alerts_count=len(alerts))

    return jsonify({
        'status': 'success',
        'matched_workflow_count': len(matches),
        'matches': matches,
    }), 200


@api_bp.route('/automation/workflows/<int:workflow_id>/execute', methods=['POST'])
@limiter.limit("120 per hour")
@require_api_key_or_permission('automation.manage')
def execute_automation_workflow(workflow_id):
    """Queue execution for a tenant automation workflow."""
    payload = request.get_json(silent=True) or {}
    execution_payload = payload.get('payload') if isinstance(payload.get('payload'), dict) else {}
    dry_run = payload.get('dry_run')
    if dry_run is not None:
        dry_run = bool(dry_run)

    workflow = AutomationService.get_workflow(g.tenant.id, workflow_id)
    if workflow is None:
        log_audit_event('automation.execute.enqueue', outcome='failure', reason='not_found', workflow_id=workflow_id)
        return jsonify({'error': 'Workflow not found'}), 404

    if not workflow.is_active:
        log_audit_event('automation.execute.enqueue', outcome='failure', reason='inactive', workflow_id=workflow_id)
        return jsonify({'error': 'Workflow is inactive'}), 400

    enqueue_kwargs = {
        'organization_id': g.tenant.id,
        'workflow_id': workflow_id,
        'payload': execution_payload,
        'dry_run': dry_run,
    }

    try:
        result = enqueue_automation_workflow_job(current_app, **enqueue_kwargs)
    except Exception as exc:
        logger.error("Failed to enqueue automation workflow: %s", exc, exc_info=True)
        log_audit_event('automation.execute.enqueue', outcome='failure', reason='enqueue_error', workflow_id=workflow_id)
        return jsonify({'error': 'Queue unavailable', 'details': str(exc)}), 503

    if not result.get('accepted'):
        log_audit_event('automation.execute.enqueue', outcome='failure', reason=result.get('reason', 'queue_disabled'), workflow_id=workflow_id)
        return jsonify({'error': 'Queue disabled', 'details': result}), 503

    log_audit_event(
        'automation.execute.enqueue',
        outcome='success',
        workflow_id=workflow_id,
        task_name=result.get('task_name'),
        task_id=result.get('task_id'),
    )

    inline_result = result.get('result') if result.get('inline') else None
    if inline_result is not None:
        log_audit_event(
            'automation.execute.delivery',
            outcome='success' if inline_result.get('status') == 'success' else 'failure',
            workflow_id=workflow_id,
            execution_status=inline_result.get('status'),
        )

    return jsonify({'status': 'accepted', 'job': result}), 202


@api_bp.route('/automation/services/status', methods=['POST'])
@limiter.limit("240 per hour")
@require_api_key_or_permission('automation.manage')
def get_automation_service_status():
    """Get service status using configured adapter boundary."""
    payload = request.get_json(silent=True) or {}
    service_name = str(payload.get('service_name') or '').strip()
    if not service_name:
        log_audit_event('automation.service_status', outcome='failure', reason='service_name_missing')
        return jsonify({'error': 'Validation failed', 'details': {'service_name': ['Field required.']}}), 400

    allowed_services_raw = current_app.config.get('AUTOMATION_ALLOWED_SERVICES', '')
    allowed_services = [
        item.strip()
        for item in str(allowed_services_raw).split(',')
        if item.strip()
    ]

    test_double_raw = current_app.config.get('AUTOMATION_LINUX_SERVICE_STATUS_TEST_DOUBLE', '')
    linux_test_double_statuses: dict[str, str] = {}
    for pair in str(test_double_raw).split(','):
        pair = pair.strip()
        if '=' not in pair:
            continue
        key, value = pair.split('=', 1)
        key = key.strip()
        value = value.strip()
        if key:
            linux_test_double_statuses[key] = value

    runtime_config = {
        'allowed_services': allowed_services,
        'service_status_adapter': current_app.config.get('AUTOMATION_SERVICE_STATUS_ADAPTER', 'linux_test_double'),
        'linux_test_double_statuses': linux_test_double_statuses,
        'command_timeout_seconds': int(current_app.config.get('AUTOMATION_COMMAND_TIMEOUT_SECONDS', 8)),
    }

    result, error = AutomationService.get_service_status(service_name, runtime_config=runtime_config)
    if error:
        log_audit_event('automation.service_status', outcome='failure', reason=error, service_name=service_name)
        if error == 'command_failed':
            return jsonify({'error': 'Service status query failed', 'details': result}), 503
        return jsonify({'error': 'Validation failed', 'details': result}), 400

    log_audit_event(
        'automation.service_status',
        outcome='success',
        service_name=service_name,
        adapter=result.get('adapter'),
        service_state=result.get('service_state'),
    )
    return jsonify({'status': 'success', 'service': result}), 200


@api_bp.route('/automation/services/dependencies', methods=['POST'])
@limiter.limit("240 per hour")
@require_api_key_or_permission('automation.manage')
def get_automation_service_dependencies():
    """Get service dependency graph for a service via adapter boundary."""
    payload = request.get_json(silent=True) or {}
    service_name = str(payload.get('service_name') or '').strip()
    if not service_name:
        log_audit_event('automation.service_dependencies', outcome='failure', reason='service_name_missing')
        return jsonify({'error': 'Validation failed', 'details': {'service_name': ['Field required.']}}), 400

    allowed_services_raw = current_app.config.get('AUTOMATION_ALLOWED_SERVICES', '')
    allowed_services = [
        item.strip()
        for item in str(allowed_services_raw).split(',')
        if item.strip()
    ]

    dependencies_raw = current_app.config.get('AUTOMATION_LINUX_SERVICE_DEPENDENCY_TEST_DOUBLE', '')
    linux_test_double_dependencies: dict[str, list[str]] = {}
    for pair in str(dependencies_raw).split(';'):
        pair = pair.strip()
        if '=' not in pair:
            continue
        key, value = pair.split('=', 1)
        key = key.strip()
        if not key:
            continue
        deps = [item.strip() for item in value.split('|') if item.strip()]
        linux_test_double_dependencies[key] = deps

    runtime_config = {
        'allowed_services': allowed_services,
        'service_dependency_adapter': current_app.config.get('AUTOMATION_SERVICE_DEPENDENCY_ADAPTER', 'linux_test_double'),
        'linux_test_double_dependencies': linux_test_double_dependencies,
        'command_timeout_seconds': int(current_app.config.get('AUTOMATION_COMMAND_TIMEOUT_SECONDS', 8)),
    }

    result, error = AutomationService.get_service_dependencies(service_name, runtime_config=runtime_config)
    if error:
        log_audit_event('automation.service_dependencies', outcome='failure', reason=error, service_name=service_name)
        if error == 'command_failed':
            return jsonify({'error': 'Service dependency query failed', 'details': result}), 503
        return jsonify({'error': 'Validation failed', 'details': result}), 400

    log_audit_event(
        'automation.service_dependencies',
        outcome='success',
        service_name=service_name,
        adapter=result.get('adapter'),
        dependency_count=result.get('dependency_count', 0),
    )
    return jsonify({'status': 'success', 'service': result}), 200


@api_bp.route('/automation/services/failures', methods=['POST'])
@limiter.limit("240 per hour")
@require_api_key_or_permission('automation.manage')
def detect_automation_service_failures():
    """Detect service failures via safe adapter boundary."""
    payload = request.get_json(silent=True) or {}
    service_name = str(payload.get('service_name') or '').strip()
    if not service_name:
        log_audit_event('automation.service_failures', outcome='failure', reason='service_name_missing')
        return jsonify({'error': 'Validation failed', 'details': {'service_name': ['Field required.']}}), 400

    allowed_services_raw = current_app.config.get('AUTOMATION_ALLOWED_SERVICES', '')
    allowed_services = [
        item.strip()
        for item in str(allowed_services_raw).split(',')
        if item.strip()
    ]

    failures_raw = current_app.config.get('AUTOMATION_LINUX_SERVICE_FAILURE_TEST_DOUBLE', '')
    linux_test_double_failures: dict[str, str] = {}
    for pair in str(failures_raw).split(';'):
        pair = pair.strip()
        if '=' not in pair:
            continue
        key, value = pair.split('=', 1)
        key = key.strip()
        value = value.strip()
        if key:
            linux_test_double_failures[key] = value

    runtime_config = {
        'allowed_services': allowed_services,
        'service_failure_adapter': current_app.config.get('AUTOMATION_SERVICE_FAILURE_ADAPTER', 'linux_test_double'),
        'linux_test_double_failures': linux_test_double_failures,
        'command_timeout_seconds': int(current_app.config.get('AUTOMATION_COMMAND_TIMEOUT_SECONDS', 8)),
    }

    result, error = AutomationService.get_service_failures(service_name, runtime_config=runtime_config)
    if error:
        log_audit_event('automation.service_failures', outcome='failure', reason=error, service_name=service_name)
        if error == 'command_failed':
            return jsonify({'error': 'Service failure query failed', 'details': result}), 503
        return jsonify({'error': 'Validation failed', 'details': result}), 400

    log_audit_event(
        'automation.service_failures',
        outcome='success',
        service_name=service_name,
        adapter=result.get('adapter'),
        failure_detected=result.get('failure_detected', False),
    )
    return jsonify({'status': 'success', 'service': result}), 200


@api_bp.route('/automation/services/execute', methods=['POST'])
@limiter.limit("240 per hour")
@require_api_key_or_permission('automation.manage')
def execute_automation_service_command():
    """Execute remote command via safe adapter boundary."""
    payload = request.get_json(silent=True) or {}
    service_name = str(payload.get('service_name') or '').strip()
    command_text = str(payload.get('command_text') or '').strip()
    
    if not service_name:
        log_audit_event('automation.service_execute', outcome='failure', reason='service_name_missing')
        return jsonify({'error': 'Validation failed', 'details': {'service_name': ['Field required.']}}), 400
    
    if not command_text:
        log_audit_event('automation.service_execute', outcome='failure', reason='command_text_missing')
        return jsonify({'error': 'Validation failed', 'details': {'command_text': ['Field required.']}}), 400

    allowed_services_raw = current_app.config.get('AUTOMATION_ALLOWED_SERVICES', '')
    allowed_services = [
        item.strip()
        for item in str(allowed_services_raw).split(',')
        if item.strip()
    ]

    commands_raw = current_app.config.get('AUTOMATION_LINUX_COMMAND_EXECUTOR_TEST_DOUBLE', '')
    linux_test_double_commands: dict[str, dict[str, str]] = {}
    for pair in str(commands_raw).split(';'):
        pair = pair.strip()
        if '=' not in pair:
            continue
        key, value = pair.split('=', 1)
        key = key.strip()
        value = value.strip()
        if key:
            output_spec = {}
            if '|' in value:
                parts = value.split('|')
                output_spec['returncode'] = int(parts[0]) if parts[0].isdigit() else 0
                output_spec['stdout'] = parts[1] if len(parts) > 1 else ''
                output_spec['stderr'] = parts[2] if len(parts) > 2 else ''
            else:
                output_spec['returncode'] = 0
                output_spec['stdout'] = value
                output_spec['stderr'] = ''
            linux_test_double_commands[key] = output_spec

    runtime_config = {
        'allowed_services': allowed_services,
        'command_executor_adapter': current_app.config.get('AUTOMATION_COMMAND_EXECUTOR_ADAPTER', 'linux_test_double'),
        'linux_test_double_commands': linux_test_double_commands,
        'command_timeout_seconds': int(current_app.config.get('AUTOMATION_COMMAND_TIMEOUT_SECONDS', 8)),
    }

    result, error = AutomationService.execute_service_command(service_name, command_text, runtime_config=runtime_config)
    if error:
        log_audit_event('automation.service_execute', outcome='failure', reason=error, service_name=service_name, command_text=command_text[:100])
        if error == 'command_failed':
            return jsonify({'error': 'Command execution failed', 'details': result}), 503
        return jsonify({'error': 'Validation failed', 'details': result}), 400

    log_audit_event(
        'automation.service_execute',
        outcome='success',
        service_name=service_name,
        adapter=result.get('adapter'),
        returncode=result.get('returncode'),
    )
    return jsonify({'status': 'success', 'service': result}), 200


@api_bp.route('/logs/sources', methods=['GET'])
@require_api_key_or_permission('automation.manage')
def list_log_sources_api():
    """List tenant log sources with lightweight investigation summaries."""
    query = LogSource.query.filter_by(organization_id=g.tenant.id)

    is_active = request.args.get('is_active')
    if is_active is not None and str(is_active).strip() != '':
        query = query.filter_by(is_active=str(is_active).strip().lower() in {'1', 'true', 'yes'})

    search_text = str(request.args.get('search_text') or '').strip()
    if search_text:
        query = query.filter(
            or_(
                LogSource.name.ilike(f'%{search_text}%'),
                LogSource.description.ilike(f'%{search_text}%'),
                LogSource.host_name.ilike(f'%{search_text}%'),
            )
        )

    sources = query.order_by(LogSource.updated_at.desc(), LogSource.id.desc()).all()
    items = [_serialize_log_source_with_summary(source) for source in sources]
    return jsonify({'status': 'success', 'count': len(items), 'sources': items}), 200


@api_bp.route('/logs/sources/<int:source_id>', methods=['GET'])
@require_api_key_or_permission('automation.manage')
def get_log_source_api(source_id):
    """Return one tenant log source plus recent persisted entries."""
    source = LogSource.query.filter_by(id=source_id, organization_id=g.tenant.id).first()
    if not source:
        return jsonify({'error': 'Log source not found'}), 404

    recent_limit = max(min(int(request.args.get('recent_limit', 10) or 10), 25), 1)
    recent_entries = (
        LogEntry.query
        .filter_by(organization_id=g.tenant.id, log_source_id=source.id)
        .order_by(LogEntry.observed_at.desc(), LogEntry.created_at.desc(), LogEntry.id.desc())
        .limit(recent_limit)
        .all()
    )

    return jsonify({
        'status': 'success',
        'log_source': _serialize_log_source_with_summary(source),
        'recent_entries': [entry.to_dict() for entry in recent_entries],
    }), 200


@api_bp.route('/logs/sources/<int:source_id>', methods=['PATCH'])
@limiter.limit("120 per hour")
@require_api_key_or_permission('automation.manage')
def update_log_source_api(source_id):
    """Update operator-maintained metadata for a tenant log source."""
    source = LogSource.query.filter_by(id=source_id, organization_id=g.tenant.id).first()
    if not source:
        log_audit_event('logs.source.update', outcome='failure', reason='not_found', source_id=source_id)
        return jsonify({'error': 'Log source not found'}), 404

    payload = request.get_json(silent=True) or {}
    if 'description' in payload:
        source.description = str(payload.get('description') or '').strip() or None
    if 'host_name' in payload:
        source.host_name = str(payload.get('host_name') or '').strip() or None
    if 'is_active' in payload:
        raw_is_active = payload.get('is_active')
        if isinstance(raw_is_active, bool):
            source.is_active = raw_is_active
        else:
            source.is_active = str(raw_is_active).strip().lower() in {'1', 'true', 'yes'}
    if 'source_metadata' in payload:
        metadata = payload.get('source_metadata')
        if metadata is not None and not isinstance(metadata, dict):
            log_audit_event('logs.source.update', outcome='failure', reason='metadata_invalid', source_id=source_id)
            return jsonify({'error': 'Validation failed', 'details': {'source_metadata': ['Must be an object.']}}), 400
        source.source_metadata = metadata or {}

    db.session.commit()
    log_audit_event('logs.source.update', outcome='success', source_id=source_id)
    return jsonify({'status': 'success', 'log_source': _serialize_log_source_with_summary(source)}), 200


@api_bp.route('/logs/entries', methods=['GET'])
@require_api_key_or_permission('automation.manage')
def list_log_entries_api():
    """List tenant log entries with filters for investigation workflows."""
    page = max(int(request.args.get('page', 1) or 1), 1)
    per_page = max(min(int(request.args.get('per_page', 25) or 25), 100), 1)
    query = _apply_log_entry_filters(LogEntry.query, g.tenant.id)
    pagination = query.order_by(LogEntry.observed_at.desc(), LogEntry.created_at.desc(), LogEntry.id.desc()).paginate(
        page=page,
        per_page=per_page,
        error_out=False,
    )

    return jsonify({
        'status': 'success',
        'page': page,
        'per_page': per_page,
        'total': pagination.total,
        'pages': pagination.pages,
        'entries': [item.to_dict() for item in pagination.items],
    }), 200


@api_bp.route('/logs/entries/<int:entry_id>', methods=['GET'])
@require_api_key_or_permission('automation.manage')
def get_log_entry_api(entry_id):
    """Return one persisted tenant log entry for drill-down views."""
    entry = LogEntry.query.filter_by(id=entry_id, organization_id=g.tenant.id).first()
    if not entry:
        return jsonify({'error': 'Log entry not found'}), 404
    return jsonify({'status': 'success', 'entry': entry.to_dict()}), 200


@api_bp.route('/logs/investigations', methods=['GET'])
@require_api_key_or_permission('automation.manage')
def list_log_investigations_api():
    """List tenant-scoped saved log investigations."""
    status = str(request.args.get('status') or '').strip()
    query = LogInvestigation.query.filter_by(organization_id=g.tenant.id)
    if status:
        query = query.filter_by(status=status)
    items = query.order_by(LogInvestigation.updated_at.desc(), LogInvestigation.id.desc()).all()
    return jsonify({'status': 'success', 'count': len(items), 'investigations': [item.to_dict() for item in items]}), 200


@api_bp.route('/logs/investigations', methods=['POST'])
@limiter.limit("120 per hour")
@require_api_key_or_permission('automation.manage')
def create_log_investigation_api():
    """Create a saved log investigation from current filter context."""
    payload = request.get_json(silent=True) or {}
    name = str(payload.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Validation failed', 'details': {'name': ['Field required.']}}), 400

    filter_snapshot = payload.get('filter_snapshot') if isinstance(payload.get('filter_snapshot'), dict) else {}
    notes = str(payload.get('notes') or '').strip() or None
    pinned_source_id = payload.get('pinned_source_id')
    pinned_entry_id = payload.get('pinned_entry_id')
    source_name = str(payload.get('source_name') or filter_snapshot.get('source_name') or '').strip() or None

    result_count = _apply_log_entry_filters(LogEntry.query, g.tenant.id, filter_snapshot).count()
    investigation = LogInvestigation(
        organization_id=g.tenant.id,
        created_by_user_id=getattr(getattr(g, 'current_user', None), 'id', None),
        name=name,
        status=str(payload.get('status') or 'open').strip() or 'open',
        source_name=source_name,
        pinned_source_id=int(pinned_source_id) if pinned_source_id not in (None, '') else None,
        pinned_entry_id=int(pinned_entry_id) if pinned_entry_id not in (None, '') else None,
        filter_snapshot=filter_snapshot,
        notes=notes,
        last_result_count=result_count,
        last_matched_at=datetime.now(UTC).replace(tzinfo=None),
    )
    db.session.add(investigation)
    db.session.commit()
    log_audit_event('logs.investigation.create', outcome='success', investigation_id=investigation.id)
    return jsonify({'status': 'success', 'investigation': investigation.to_dict()}), 201


@api_bp.route('/logs/investigations/<int:investigation_id>', methods=['PATCH'])
@limiter.limit("120 per hour")
@require_api_key_or_permission('automation.manage')
def update_log_investigation_api(investigation_id):
    """Update a saved log investigation and refresh its last match count."""
    investigation = LogInvestigation.query.filter_by(id=investigation_id, organization_id=g.tenant.id).first()
    if not investigation:
        return jsonify({'error': 'Log investigation not found'}), 404

    payload = request.get_json(silent=True) or {}
    if 'name' in payload:
        name = str(payload.get('name') or '').strip()
        if not name:
            return jsonify({'error': 'Validation failed', 'details': {'name': ['Field cannot be blank.']}}), 400
        investigation.name = name
    if 'status' in payload:
        investigation.status = str(payload.get('status') or '').strip() or investigation.status
    if 'notes' in payload:
        investigation.notes = str(payload.get('notes') or '').strip() or None
    if 'source_name' in payload:
        investigation.source_name = str(payload.get('source_name') or '').strip() or None
    if 'pinned_source_id' in payload:
        raw = payload.get('pinned_source_id')
        investigation.pinned_source_id = int(raw) if raw not in (None, '') else None
    if 'pinned_entry_id' in payload:
        raw = payload.get('pinned_entry_id')
        investigation.pinned_entry_id = int(raw) if raw not in (None, '') else None
    if 'filter_snapshot' in payload:
        if not isinstance(payload.get('filter_snapshot'), dict):
            return jsonify({'error': 'Validation failed', 'details': {'filter_snapshot': ['Must be an object.']}}), 400
        investigation.filter_snapshot = payload.get('filter_snapshot') or {}

    result_count = _apply_log_entry_filters(LogEntry.query, g.tenant.id, investigation.filter_snapshot or {}).count()
    investigation.last_result_count = result_count
    investigation.last_matched_at = datetime.now(UTC).replace(tzinfo=None)
    db.session.commit()
    log_audit_event('logs.investigation.update', outcome='success', investigation_id=investigation.id)
    return jsonify({'status': 'success', 'investigation': investigation.to_dict()}), 200


@api_bp.route('/logs/ingest', methods=['POST'])
@limiter.limit("240 per hour")
@require_api_key_or_permission('automation.manage')
def ingest_logs_pipeline():
    """Ingest logs using safe adapter boundary and persist captured entries."""
    payload = request.get_json(silent=True) or {}
    source_name = str(payload.get('source_name') or '').strip()
    if not source_name:
        log_audit_event('logs.ingest', outcome='failure', reason='source_name_missing')
        return jsonify({'error': 'Validation failed', 'details': {'source_name': ['Field required.']}}), 400

    allowed_sources_raw = current_app.config.get('LOG_INGESTION_ALLOWED_SOURCES', '')
    allowed_sources = [
        item.strip()
        for item in str(allowed_sources_raw).split(',')
        if item.strip()
    ]

    logs_raw = current_app.config.get('LOG_LINUX_INGESTION_TEST_DOUBLE', '')
    linux_test_double_logs: dict[str, list[str]] = {}
    for pair in str(logs_raw).split(';'):
        pair = pair.strip()
        if '=' not in pair:
            continue
        key, value = pair.split('=', 1)
        key = key.strip()
        if not key:
            continue
        entries = [item.strip() for item in value.split('|') if item.strip()]
        linux_test_double_logs[key] = entries

    runtime_config = {
        'allowed_sources': allowed_sources,
        'log_ingestion_adapter': current_app.config.get('LOG_INGESTION_ADAPTER', 'linux_test_double'),
        'linux_test_double_logs': linux_test_double_logs,
        'max_entries': int(current_app.config.get('LOG_INGESTION_MAX_ENTRIES', 25)),
        'command_timeout_seconds': int(current_app.config.get('AUTOMATION_COMMAND_TIMEOUT_SECONDS', 8)),
    }

    result, error = LogService.ingest_logs(source_name, runtime_config=runtime_config)
    if error:
        log_audit_event('logs.ingest', outcome='failure', reason=error, source_name=source_name)
        if error == 'command_failed':
            return jsonify({'error': 'Log ingestion command failed', 'details': result}), 503
        return jsonify({'error': 'Validation failed', 'details': result}), 400

    persistence = {'persisted_count': 0, 'log_source_id': None}
    if current_app.config.get('LOG_PERSISTENT_STORE_ENABLED', True):
        persistence = LogService.persist_log_entries(
            organization_id=g.tenant.id,
            source_name=source_name,
            adapter=str(result.get('adapter') or 'unknown'),
            entries=result.get('entries') or [],
            capture_kind='ingest',
        )
        result['persisted_count'] = persistence['persisted_count']
        result['log_source_id'] = persistence['log_source_id']

    log_audit_event(
        'logs.ingest',
        outcome='success',
        source_name=source_name,
        adapter=result.get('adapter'),
        entry_count=result.get('entry_count', 0),
        persisted_count=result.get('persisted_count', 0),
    )
    return jsonify({'status': 'success', 'logs': result}), 200


@api_bp.route('/logs/events/query', methods=['POST'])
@limiter.limit("240 per hour")
@require_api_key_or_permission('automation.manage')
def query_windows_event_entries():
    """Query event entries via adapter boundary and persist normalized event rows."""
    payload = request.get_json(silent=True) or {}
    source_name = str(payload.get('source_name') or '').strip()
    if not source_name:
        log_audit_event('logs.events_query', outcome='failure', reason='source_name_missing')
        return jsonify({'error': 'Validation failed', 'details': {'source_name': ['Field required.']}}), 400

    allowed_sources_raw = current_app.config.get('LOG_INGESTION_ALLOWED_SOURCES', '')
    allowed_sources = [
        item.strip()
        for item in str(allowed_sources_raw).split(',')
        if item.strip()
    ]

    events_raw = current_app.config.get('LOG_LINUX_EVENT_QUERY_TEST_DOUBLE', '')
    linux_test_double_events: dict[str, list[str]] = {}
    for pair in str(events_raw).split(';'):
        pair = pair.strip()
        if '=' not in pair:
            continue
        key, value = pair.split('=', 1)
        key = key.strip()
        if not key:
            continue
        entries = [item.strip() for item in value.split('||') if item.strip()]
        linux_test_double_events[key] = entries

    runtime_config = {
        'allowed_sources': allowed_sources,
        'event_query_adapter': current_app.config.get('LOG_EVENT_QUERY_ADAPTER', 'linux_test_double'),
        'linux_test_double_events': linux_test_double_events,
        'max_entries': int(current_app.config.get('LOG_INGESTION_MAX_ENTRIES', 25)),
        'command_timeout_seconds': int(current_app.config.get('AUTOMATION_COMMAND_TIMEOUT_SECONDS', 8)),
    }

    result, error = LogService.query_event_entries(source_name, runtime_config=runtime_config)
    if error:
        log_audit_event('logs.events_query', outcome='failure', reason=error, source_name=source_name)
        if error == 'command_failed':
            return jsonify({'error': 'Event query command failed', 'details': result}), 503
        return jsonify({'error': 'Validation failed', 'details': result}), 400

    persistence = {'persisted_count': 0, 'log_source_id': None}
    if current_app.config.get('LOG_PERSISTENT_STORE_ENABLED', True):
        persistence = LogService.persist_log_entries(
            organization_id=g.tenant.id,
            source_name=source_name,
            adapter=str(result.get('adapter') or 'unknown'),
            entries=result.get('entries') or [],
            capture_kind='event_query',
        )
        result['persisted_count'] = persistence['persisted_count']
        result['log_source_id'] = persistence['log_source_id']

    log_audit_event(
        'logs.events_query',
        outcome='success',
        source_name=source_name,
        adapter=result.get('adapter'),
        entry_count=result.get('entry_count', 0),
        persisted_count=result.get('persisted_count', 0),
    )
    return jsonify({'status': 'success', 'events': result}), 200


@api_bp.route('/logs/parse', methods=['POST'])
@limiter.limit("240 per hour")
@require_api_key_or_permission('automation.manage')
def parse_log_entries():
    """Parse raw log/event entries into structured records."""
    payload = request.get_json(silent=True) or {}
    entries = payload.get('entries')
    if not isinstance(entries, list):
        log_audit_event('logs.parse', outcome='failure', reason='entries_missing_or_invalid')
        return jsonify({'error': 'Validation failed', 'details': {'entries': ['Must be a list.']}}), 400

    runtime_config = {
        'max_entries': int(current_app.config.get('LOG_INGESTION_MAX_ENTRIES', 50)),
    }

    result, error = LogService.parse_log_entries(entries, runtime_config=runtime_config)
    if error:
        log_audit_event('logs.parse', outcome='failure', reason=error)
        return jsonify({'error': 'Validation failed', 'details': result}), 400

    persisted_total = 0
    if current_app.config.get('LOG_PERSISTENT_STORE_ENABLED', True):
        grouped_events: dict[str, list[dict]] = {}
        for event in result.get('events') or []:
            source_name = str(event.get('source') or 'unknown').strip() or 'unknown'
            grouped_events.setdefault(source_name, []).append(event)

        for source_name, grouped in grouped_events.items():
            persisted = LogService.persist_log_entries(
                organization_id=g.tenant.id,
                source_name=source_name,
                adapter='parsed_payload',
                entries=grouped,
                capture_kind='parse',
            )
            persisted_total += int(persisted.get('persisted_count') or 0)

        result['persisted_count'] = persisted_total

    log_audit_event(
        'logs.parse',
        outcome='success',
        entry_count=result.get('entry_count', 0),
        structured_count=result.get('structured_count', 0),
        persisted_count=result.get('persisted_count', 0),
    )
    return jsonify({'status': 'success', 'parsed': result}), 200


@api_bp.route('/logs/events/correlate', methods=['POST'])
@limiter.limit("240 per hour")
@require_api_key_or_permission('automation.manage')
def correlate_events():
    """Filter events by severity and correlate matching groups."""
    payload = request.get_json(silent=True) or {}
    events = payload.get('events')
    if not isinstance(events, list):
        log_audit_event('logs.correlate', outcome='failure', reason='events_missing_or_invalid')
        return jsonify({'error': 'Validation failed', 'details': {'events': ['Must be a list.']}}), 400

    runtime_config = {
        'allowed_severities': payload.get('allowed_severities') or [],
        'min_group_size': int(payload.get('min_group_size') or current_app.config.get('LOG_CORRELATION_MIN_GROUP_SIZE', 2)),
    }

    result, error = LogService.filter_and_correlate_events(events, runtime_config=runtime_config)
    if error:
        log_audit_event('logs.correlate', outcome='failure', reason=error)
        return jsonify({'error': 'Validation failed', 'details': result}), 400

    log_audit_event(
        'logs.correlate',
        outcome='success',
        filtered_count=result.get('filtered_count', 0),
        group_count=result.get('group_count', 0),
    )
    return jsonify({'status': 'success', 'correlation': result}), 200


@api_bp.route('/logs/drivers/monitor', methods=['POST'])
@limiter.limit("240 per hour")
@require_api_key_or_permission('automation.manage')
def monitor_drivers():
    """Collect driver inventory via Win32_PnPSignedDriver adapter boundary."""
    payload = request.get_json(silent=True) or {}
    host_name = str(payload.get('host_name') or '').strip()
    if not host_name:
        log_audit_event('logs.drivers_monitor', outcome='failure', reason='host_name_missing')
        return jsonify({'error': 'Validation failed', 'details': {'host_name': ['Field required.']}}), 400

    allowed_hosts_raw = current_app.config.get('LOG_DRIVER_ALLOWED_HOSTS', '')
    allowed_hosts = [
        item.strip()
        for item in str(allowed_hosts_raw).split(',')
        if item.strip()
    ]

    driver_raw = current_app.config.get('LOG_LINUX_DRIVER_MONITOR_TEST_DOUBLE', '')
    linux_test_double_drivers: dict[str, list[str]] = {}
    for pair in str(driver_raw).split(';'):
        pair = pair.strip()
        if '=' not in pair:
            continue
        key, value = pair.split('=', 1)
        key = key.strip()
        if not key:
            continue
        entries = [item.strip() for item in value.split('||') if item.strip()]
        linux_test_double_drivers[key] = entries

    runtime_config = {
        'allowed_hosts': allowed_hosts,
        'driver_monitor_adapter': current_app.config.get('LOG_DRIVER_MONITOR_ADAPTER', 'linux_test_double'),
        'linux_test_double_drivers': linux_test_double_drivers,
        'max_entries': int(current_app.config.get('LOG_INGESTION_MAX_ENTRIES', 50)),
        'command_timeout_seconds': int(current_app.config.get('AUTOMATION_COMMAND_TIMEOUT_SECONDS', 8)),
    }

    result, error = LogService.monitor_drivers(host_name, runtime_config=runtime_config)
    if error:
        log_audit_event('logs.drivers_monitor', outcome='failure', reason=error, host_name=host_name)
        if error == 'command_failed':
            return jsonify({'error': 'Driver monitor command failed', 'details': result}), 503
        return jsonify({'error': 'Validation failed', 'details': result}), 400

    log_audit_event(
        'logs.drivers_monitor',
        outcome='success',
        host_name=host_name,
        adapter=result.get('adapter'),
        driver_count=result.get('driver_count', 0),
    )
    return jsonify({'status': 'success', 'drivers': result}), 200


@api_bp.route('/logs/drivers/errors', methods=['POST'])
@limiter.limit("240 per hour")
@require_api_key_or_permission('automation.manage')
def detect_driver_errors():
    """Detect driver errors via adapter boundary."""
    payload = request.get_json(silent=True) or {}
    host_name = str(payload.get('host_name') or '').strip()
    if not host_name:
        log_audit_event('logs.drivers_errors', outcome='failure', reason='host_name_missing')
        return jsonify({'error': 'Validation failed', 'details': {'host_name': ['Field required.']}}), 400

    allowed_hosts_raw = current_app.config.get('LOG_DRIVER_ALLOWED_HOSTS', '')
    allowed_hosts = [
        item.strip()
        for item in str(allowed_hosts_raw).split(',')
        if item.strip()
    ]

    error_raw = current_app.config.get('LOG_LINUX_DRIVER_ERROR_TEST_DOUBLE', '')
    linux_test_double_errors: dict[str, list[str]] = {}
    for pair in str(error_raw).split(';'):
        pair = pair.strip()
        if '=' not in pair:
            continue
        key, value = pair.split('=', 1)
        key = key.strip()
        if not key:
            continue
        entries = [item.strip() for item in value.split('||') if item.strip()]
        linux_test_double_errors[key] = entries

    runtime_config = {
        'allowed_hosts': allowed_hosts,
        'driver_error_adapter': current_app.config.get('LOG_DRIVER_ERROR_ADAPTER', 'linux_test_double'),
        'linux_test_double_driver_errors': linux_test_double_errors,
        'max_entries': int(current_app.config.get('LOG_INGESTION_MAX_ENTRIES', 50)),
        'command_timeout_seconds': int(current_app.config.get('AUTOMATION_COMMAND_TIMEOUT_SECONDS', 8)),
    }

    result, error = LogService.detect_driver_errors(host_name, runtime_config=runtime_config)
    if error:
        log_audit_event('logs.drivers_errors', outcome='failure', reason=error, host_name=host_name)
        if error == 'command_failed':
            return jsonify({'error': 'Driver error command failed', 'details': result}), 503
        return jsonify({'error': 'Validation failed', 'details': result}), 400

    log_audit_event(
        'logs.drivers_errors',
        outcome='success',
        host_name=host_name,
        adapter=result.get('adapter'),
        error_count=result.get('error_count', 0),
    )
    return jsonify({'status': 'success', 'driver_errors': result}), 200


@api_bp.route('/logs/events/stream', methods=['POST'])
@limiter.limit("240 per hour")
@require_api_key_or_permission('automation.manage')
def stream_events():
    """Stream event batch with cursor via adapter boundary."""
    payload = request.get_json(silent=True) or {}
    source_name = str(payload.get('source_name') or '').strip()
    if not source_name:
        log_audit_event('logs.events_stream', outcome='failure', reason='source_name_missing')
        return jsonify({'error': 'Validation failed', 'details': {'source_name': ['Field required.']}}), 400

    allowed_sources_raw = current_app.config.get('LOG_INGESTION_ALLOWED_SOURCES', '')
    allowed_sources = [
        item.strip()
        for item in str(allowed_sources_raw).split(',')
        if item.strip()
    ]

    stream_raw = current_app.config.get('LOG_LINUX_EVENT_STREAM_TEST_DOUBLE', '')
    linux_test_double_streams: dict[str, list[str]] = {}
    for pair in str(stream_raw).split(';'):
        pair = pair.strip()
        if '=' not in pair:
            continue
        key, value = pair.split('=', 1)
        key = key.strip()
        if not key:
            continue
        entries = [item.strip() for item in value.split('||') if item.strip()]
        linux_test_double_streams[key] = entries

    runtime_config = {
        'allowed_sources': allowed_sources,
        'event_stream_adapter': current_app.config.get('LOG_EVENT_STREAM_ADAPTER', 'linux_test_double'),
        'linux_test_double_streams': linux_test_double_streams,
        'batch_size': int(current_app.config.get('LOG_EVENT_STREAM_BATCH_SIZE', 25)),
        'command_timeout_seconds': int(current_app.config.get('AUTOMATION_COMMAND_TIMEOUT_SECONDS', 8)),
    }

    result, error = LogService.stream_events(source_name, runtime_config=runtime_config)
    if error:
        log_audit_event('logs.events_stream', outcome='failure', reason=error, source_name=source_name)
        if error == 'command_failed':
            return jsonify({'error': 'Event stream command failed', 'details': result}), 503
        return jsonify({'error': 'Validation failed', 'details': result}), 400

    log_audit_event(
        'logs.events_stream',
        outcome='success',
        source_name=source_name,
        adapter=result.get('adapter'),
        event_count=result.get('event_count', 0),
    )
    return jsonify({'status': 'success', 'stream': result}), 200


@api_bp.route('/logs/search', methods=['POST'])
@limiter.limit("240 per hour")
@require_api_key_or_permission('automation.manage')
def search_logs():
    """Search logs from persistent storage first, then fall back to adapter boundary."""
    payload = request.get_json(silent=True) or {}
    source_name = str(payload.get('source_name') or '').strip()
    query_text = str(payload.get('query_text') or '').strip()

    if not source_name:
        log_audit_event('logs.search', outcome='failure', reason='source_name_missing')
        return jsonify({'error': 'Validation failed', 'details': {'source_name': ['Field required.']}}), 400

    if not query_text:
        log_audit_event('logs.search', outcome='failure', reason='query_text_missing')
        return jsonify({'error': 'Validation failed', 'details': {'query_text': ['Field required.']}}), 400

    allowed_sources_raw = current_app.config.get('LOG_INGESTION_ALLOWED_SOURCES', '')
    allowed_sources = [
        item.strip()
        for item in str(allowed_sources_raw).split(',')
        if item.strip()
    ]

    search_raw = current_app.config.get('LOG_LINUX_SEARCH_TEST_DOUBLE', '')
    linux_test_double_search_entries: dict[str, list[str]] = {}
    for pair in str(search_raw).split(';'):
        pair = pair.strip()
        if '=' not in pair:
            continue
        key, value = pair.split('=', 1)
        key = key.strip()
        if not key:
            continue
        entries = [item.strip() for item in value.split('||') if item.strip()]
        linux_test_double_search_entries[key] = entries

    max_results = int(current_app.config.get('LOG_SEARCH_MAX_RESULTS', 25))

    result = None
    error = None
    if current_app.config.get('LOG_PERSISTENT_STORE_ENABLED', True):
        persistent_result = LogService.search_persistent_entries(
            organization_id=g.tenant.id,
            source_name=source_name,
            query_text=query_text,
            max_results=max_results,
        )
        if persistent_result.get('result_count', 0) > 0:
            result = persistent_result

    if result is None:
        runtime_config = {
            'allowed_sources': allowed_sources,
            'search_adapter': current_app.config.get('LOG_SEARCH_ADAPTER', 'linux_test_double'),
            'linux_test_double_search_entries': linux_test_double_search_entries,
            'max_results': max_results,
            'command_timeout_seconds': int(current_app.config.get('AUTOMATION_COMMAND_TIMEOUT_SECONDS', 8)),
        }

        result, error = LogService.search_and_index_logs(source_name, query_text, runtime_config=runtime_config)
        if error:
            log_audit_event(
                'logs.search',
                outcome='failure',
                reason=error,
                source_name=source_name,
                query_text=query_text[:100],
            )
            if error == 'command_failed':
                return jsonify({'error': 'Log search command failed', 'details': result}), 503
            return jsonify({'error': 'Validation failed', 'details': result}), 400

    log_audit_event(
        'logs.search',
        outcome='success',
        source_name=source_name,
        adapter=result.get('adapter'),
        query_text=query_text[:100],
        result_count=result.get('result_count', 0),
        index_token_count=(result.get('index') or {}).get('token_count', 0),
    )
    return jsonify({'status': 'success', 'search': result}), 200


@api_bp.route('/reliability/runs', methods=['GET'])
@require_api_key_or_permission('automation.manage')
def list_reliability_runs_api():
    """List tenant-scoped reliability diagnostic executions."""
    page = max(int(request.args.get('page', 1) or 1), 1)
    per_page = max(min(int(request.args.get('per_page', 25) or 25), 100), 1)
    query = ReliabilityRun.query.filter_by(organization_id=g.tenant.id)

    host_name = str(request.args.get('host_name') or '').strip()
    if host_name:
        query = query.filter_by(host_name=host_name)

    diagnostic_type = str(request.args.get('diagnostic_type') or '').strip()
    if diagnostic_type:
        query = query.filter_by(diagnostic_type=diagnostic_type)

    status = str(request.args.get('status') or '').strip()
    if status:
        query = query.filter_by(status=status)

    dump_name = str(request.args.get('dump_name') or '').strip()
    if dump_name:
        query = query.filter_by(dump_name=dump_name)

    error_reason = str(request.args.get('error_reason') or '').strip()
    if error_reason:
        query = query.filter_by(error_reason=error_reason)

    latest_per_type = str(request.args.get('latest_per_type') or '').strip().lower() in {'1', 'true', 'yes', 'on'}
    if latest_per_type:
        filtered_runs = query.order_by(ReliabilityRun.created_at.desc(), ReliabilityRun.id.desc()).all()
        latest_map: dict[tuple[str, str, str], ReliabilityRun] = {}
        for run in filtered_runs:
            key = (run.host_name, run.diagnostic_type, run.dump_name or '')
            latest_map.setdefault(key, run)
        items = list(latest_map.values())
        total = len(items)
        start = (page - 1) * per_page
        end = start + per_page
        page_items = items[start:end]
        pages = (total + per_page - 1) // per_page if total else 0
        return jsonify({
            'status': 'success',
            'page': page,
            'per_page': per_page,
            'total': total,
            'pages': pages,
            'reliability_runs': [item.to_dict() for item in page_items],
        }), 200

    pagination = query.order_by(ReliabilityRun.created_at.desc(), ReliabilityRun.id.desc()).paginate(
        page=page,
        per_page=per_page,
        error_out=False,
    )
    return jsonify({
        'status': 'success',
        'page': page,
        'per_page': per_page,
        'total': pagination.total,
        'pages': pagination.pages,
        'reliability_runs': [item.to_dict() for item in pagination.items],
    }), 200


@api_bp.route('/reliability/runs/<int:run_id>', methods=['GET'])
@require_api_key_or_permission('automation.manage')
def get_reliability_run_api(run_id):
    """Return one tenant-scoped reliability diagnostic execution."""
    item = ReliabilityRun.query.filter_by(id=run_id, organization_id=g.tenant.id).first()
    if not item:
        return jsonify({'error': 'Reliability run not found'}), 404
    return jsonify({'status': 'success', 'reliability_run': _serialize_reliability_run_with_related(item)}), 200


@api_bp.route('/reliability/report', methods=['GET'])
@require_api_key_or_permission('automation.manage')
def get_reliability_report_api():
    """Return operator-oriented aggregate reporting for reliability runs."""
    host_name = str(request.args.get('host_name') or '').strip() or None
    report = _build_reliability_report(g.tenant.id, host_name=host_name)
    return jsonify({'status': 'success', 'report': report}), 200


@api_bp.route('/reliability/history', methods=['POST'])
@limiter.limit("240 per hour")
@require_api_key_or_permission('automation.manage')
def collect_reliability_history():
    """Collect reliability history using safe WMI boundary or Linux test-double."""
    payload = request.get_json(silent=True) or {}
    host_name = str(payload.get('host_name') or '').strip()
    if not host_name:
        log_audit_event('reliability.history', outcome='failure', reason='host_name_missing')
        return jsonify({'error': 'Validation failed', 'details': {'host_name': ['Field required.']}}), 400

    allowed_hosts_raw = current_app.config.get('RELIABILITY_ALLOWED_HOSTS', '')
    allowed_hosts = [
        item.strip()
        for item in str(allowed_hosts_raw).split(',')
        if item.strip()
    ]

    history_raw = current_app.config.get('RELIABILITY_LINUX_HISTORY_TEST_DOUBLE', '')
    linux_test_double_history: dict[str, list[str]] = {}
    for pair in str(history_raw).split(';'):
        pair = pair.strip()
        if '=' not in pair:
            continue
        key, value = pair.split('=', 1)
        key = key.strip()
        if not key:
            continue
        entries = [item.strip() for item in value.split('||') if item.strip()]
        linux_test_double_history[key] = entries

    runtime_config = {
        'organization_id': g.tenant.id,
        'allowed_hosts': allowed_hosts,
        'history_adapter': current_app.config.get('RELIABILITY_HISTORY_ADAPTER', 'linux_test_double'),
        'linux_test_double_history': linux_test_double_history,
        'max_records': int(current_app.config.get('RELIABILITY_HISTORY_MAX_RECORDS', 25)),
        'command_timeout_seconds': int(current_app.config.get('AUTOMATION_COMMAND_TIMEOUT_SECONDS', 8)),
    }

    result, error = ReliabilityService.collect_reliability_history(host_name, runtime_config=runtime_config)
    _record_reliability_run(
        organization_id=g.tenant.id,
        diagnostic_type='history',
        host_name=host_name,
        request_payload={'host_name': host_name},
        result=result,
        error=error,
    )
    if error:
        log_audit_event('reliability.history', outcome='failure', reason=error, host_name=host_name)
        if error == 'command_failed':
            return jsonify({'error': 'Reliability history command failed', 'details': result}), 503
        return jsonify({'error': 'Validation failed', 'details': result}), 400

    log_audit_event(
        'reliability.history',
        outcome='success',
        host_name=host_name,
        adapter=result.get('adapter'),
        record_count=result.get('record_count', 0),
    )
    return jsonify({'status': 'success', 'history': result}), 200


@api_bp.route('/reliability/crash-dumps/parse', methods=['POST'])
@limiter.limit("240 per hour")
@require_api_key_or_permission('automation.manage')
def parse_crash_dump():
    """Parse crash dump metadata using safe file boundary or Linux test-double."""
    payload = request.get_json(silent=True) or {}
    host_name = str(payload.get('host_name') or '').strip()
    dump_name = str(payload.get('dump_name') or '').strip()
    if not host_name:
        log_audit_event('reliability.crash_dump_parse', outcome='failure', reason='host_name_missing')
        return jsonify({'error': 'Validation failed', 'details': {'host_name': ['Field required.']}}), 400
    if not dump_name:
        log_audit_event('reliability.crash_dump_parse', outcome='failure', reason='dump_name_missing')
        return jsonify({'error': 'Validation failed', 'details': {'dump_name': ['Field required.']}}), 400

    allowed_hosts_raw = current_app.config.get('RELIABILITY_ALLOWED_HOSTS', '')
    allowed_hosts = [
        item.strip()
        for item in str(allowed_hosts_raw).split(',')
        if item.strip()
    ]
    allowed_dump_roots_raw = current_app.config.get('RELIABILITY_ALLOWED_DUMP_ROOTS', '')
    allowed_dump_roots = [
        item.strip()
        for item in str(allowed_dump_roots_raw).split(',')
        if item.strip()
    ]

    crash_raw = current_app.config.get('RELIABILITY_LINUX_CRASH_DUMP_TEST_DOUBLE', '')
    linux_test_double_crash_dumps: dict[str, str] = {}
    for pair in str(crash_raw).split(';'):
        pair = pair.strip()
        if '=' not in pair:
            continue
        key, value = pair.split('=', 1)
        key = key.strip()
        value = value.strip()
        if key:
            linux_test_double_crash_dumps[key] = value

    runtime_config = {
        'organization_id': g.tenant.id,
        'allowed_hosts': allowed_hosts,
        'allowed_dump_roots': allowed_dump_roots,
        'crash_dump_adapter': current_app.config.get('RELIABILITY_CRASH_DUMP_ADAPTER', 'linux_test_double'),
        'linux_test_double_crash_dumps': linux_test_double_crash_dumps,
        'crash_dump_root': current_app.config.get('RELIABILITY_CRASH_DUMP_ROOT', r'C:\\CrashDumps'),
        'command_timeout_seconds': int(current_app.config.get('AUTOMATION_COMMAND_TIMEOUT_SECONDS', 8)),
    }

    result, error = ReliabilityService.parse_crash_dump(host_name, dump_name, runtime_config=runtime_config)
    _record_reliability_run(
        organization_id=g.tenant.id,
        diagnostic_type='crash_dump_parse',
        host_name=host_name,
        dump_name=dump_name,
        request_payload={'host_name': host_name, 'dump_name': dump_name},
        result=result,
        error=error,
    )
    if error:
        log_audit_event(
            'reliability.crash_dump_parse',
            outcome='failure',
            reason=error,
            host_name=host_name,
            dump_name=dump_name,
        )
        if error == 'command_failed':
            return jsonify({'error': 'Crash dump parse command failed', 'details': result}), 503
        return jsonify({'error': 'Validation failed', 'details': result}), 400

    log_audit_event(
        'reliability.crash_dump_parse',
        outcome='success',
        host_name=host_name,
        dump_name=dump_name,
        adapter=result.get('adapter'),
        dump_type=(result.get('parsed_dump') or {}).get('dump_type'),
    )
    return jsonify({'status': 'success', 'crash_dump': result}), 200


@api_bp.route('/reliability/exceptions/identify', methods=['POST'])
@limiter.limit("240 per hour")
@require_api_key_or_permission('automation.manage')
def identify_exception():
    """Identify exception signature from crash dump metadata boundary or Linux test-double."""
    payload = request.get_json(silent=True) or {}
    host_name = str(payload.get('host_name') or '').strip()
    dump_name = str(payload.get('dump_name') or '').strip()
    if not host_name:
        log_audit_event('reliability.exception_identify', outcome='failure', reason='host_name_missing')
        return jsonify({'error': 'Validation failed', 'details': {'host_name': ['Field required.']}}), 400
    if not dump_name:
        log_audit_event('reliability.exception_identify', outcome='failure', reason='dump_name_missing')
        return jsonify({'error': 'Validation failed', 'details': {'dump_name': ['Field required.']}}), 400

    allowed_hosts_raw = current_app.config.get('RELIABILITY_ALLOWED_HOSTS', '')
    allowed_hosts = [
        item.strip()
        for item in str(allowed_hosts_raw).split(',')
        if item.strip()
    ]
    allowed_dump_roots_raw = current_app.config.get('RELIABILITY_ALLOWED_DUMP_ROOTS', '')
    allowed_dump_roots = [
        item.strip()
        for item in str(allowed_dump_roots_raw).split(',')
        if item.strip()
    ]

    exception_raw = current_app.config.get('RELIABILITY_LINUX_EXCEPTION_TEST_DOUBLE', '')
    linux_test_double_exceptions: dict[str, str] = {}
    for pair in str(exception_raw).split(';'):
        pair = pair.strip()
        if '=' not in pair:
            continue
        key, value = pair.split('=', 1)
        key = key.strip()
        value = value.strip()
        if key:
            linux_test_double_exceptions[key] = value

    runtime_config = {
        'organization_id': g.tenant.id,
        'allowed_hosts': allowed_hosts,
        'allowed_dump_roots': allowed_dump_roots,
        'exception_identifier_adapter': current_app.config.get('RELIABILITY_EXCEPTION_IDENTIFIER_ADAPTER', 'linux_test_double'),
        'linux_test_double_exceptions': linux_test_double_exceptions,
        'crash_dump_root': current_app.config.get('RELIABILITY_CRASH_DUMP_ROOT', r'C:\\CrashDumps'),
        'command_timeout_seconds': int(current_app.config.get('AUTOMATION_COMMAND_TIMEOUT_SECONDS', 8)),
    }

    result, error = ReliabilityService.identify_exception(host_name, dump_name, runtime_config=runtime_config)
    _record_reliability_run(
        organization_id=g.tenant.id,
        diagnostic_type='exception_identify',
        host_name=host_name,
        dump_name=dump_name,
        request_payload={'host_name': host_name, 'dump_name': dump_name},
        result=result,
        error=error,
    )
    if error:
        log_audit_event(
            'reliability.exception_identify',
            outcome='failure',
            reason=error,
            host_name=host_name,
            dump_name=dump_name,
        )
        if error == 'command_failed':
            return jsonify({'error': 'Exception identifier command failed', 'details': result}), 503
        return jsonify({'error': 'Validation failed', 'details': result}), 400

    identified_exception = result.get('identified_exception') or {}
    log_audit_event(
        'reliability.exception_identify',
        outcome='success',
        host_name=host_name,
        dump_name=dump_name,
        adapter=result.get('adapter'),
        exception_code=identified_exception.get('exception_code'),
        exception_name=identified_exception.get('exception_name'),
    )
    return jsonify({'status': 'success', 'exception': result}), 200


@api_bp.route('/reliability/stack-traces/analyze', methods=['POST'])
@limiter.limit("240 per hour")
@require_api_key_or_permission('automation.manage')
def analyze_stack_trace():
    """Analyze stack trace from crash dump boundary or Linux test-double."""
    payload = request.get_json(silent=True) or {}
    host_name = str(payload.get('host_name') or '').strip()
    dump_name = str(payload.get('dump_name') or '').strip()
    if not host_name:
        log_audit_event('reliability.stack_trace_analyze', outcome='failure', reason='host_name_missing')
        return jsonify({'error': 'Validation failed', 'details': {'host_name': ['Field required.']}}), 400
    if not dump_name:
        log_audit_event('reliability.stack_trace_analyze', outcome='failure', reason='dump_name_missing')
        return jsonify({'error': 'Validation failed', 'details': {'dump_name': ['Field required.']}}), 400

    allowed_hosts_raw = current_app.config.get('RELIABILITY_ALLOWED_HOSTS', '')
    allowed_hosts = [
        item.strip()
        for item in str(allowed_hosts_raw).split(',')
        if item.strip()
    ]
    allowed_dump_roots_raw = current_app.config.get('RELIABILITY_ALLOWED_DUMP_ROOTS', '')
    allowed_dump_roots = [
        item.strip()
        for item in str(allowed_dump_roots_raw).split(',')
        if item.strip()
    ]

    stack_raw = current_app.config.get('RELIABILITY_LINUX_STACK_TRACE_TEST_DOUBLE', '')
    linux_test_double_stack_traces: dict[str, str] = {}
    for pair in str(stack_raw).split(';'):
        pair = pair.strip()
        if '=' not in pair:
            continue
        key, value = pair.split('=', 1)
        key = key.strip()
        value = value.strip()
        if key:
            linux_test_double_stack_traces[key] = value

    runtime_config = {
        'organization_id': g.tenant.id,
        'allowed_hosts': allowed_hosts,
        'allowed_dump_roots': allowed_dump_roots,
        'stack_trace_adapter': current_app.config.get('RELIABILITY_STACK_TRACE_ADAPTER', 'linux_test_double'),
        'linux_test_double_stack_traces': linux_test_double_stack_traces,
        'crash_dump_root': current_app.config.get('RELIABILITY_CRASH_DUMP_ROOT', r'C:\\CrashDumps'),
        'command_timeout_seconds': int(current_app.config.get('AUTOMATION_COMMAND_TIMEOUT_SECONDS', 8)),
    }

    result, error = ReliabilityService.analyze_stack_trace(host_name, dump_name, runtime_config=runtime_config)
    _record_reliability_run(
        organization_id=g.tenant.id,
        diagnostic_type='stack_trace_analyze',
        host_name=host_name,
        dump_name=dump_name,
        request_payload={'host_name': host_name, 'dump_name': dump_name},
        result=result,
        error=error,
    )
    if error:
        log_audit_event(
            'reliability.stack_trace_analyze',
            outcome='failure',
            reason=error,
            host_name=host_name,
            dump_name=dump_name,
        )
        if error == 'command_failed':
            return jsonify({'error': 'Stack trace analysis command failed', 'details': result}), 503
        return jsonify({'error': 'Validation failed', 'details': result}), 400

    stack_trace = result.get('stack_trace') or {}
    log_audit_event(
        'reliability.stack_trace_analyze',
        outcome='success',
        host_name=host_name,
        dump_name=dump_name,
        adapter=result.get('adapter'),
        frame_count=stack_trace.get('frame_count', 0),
        top_frame=stack_trace.get('top_frame'),
    )
    return jsonify({'status': 'success', 'stack_trace': result}), 200


@api_bp.route('/reliability/score', methods=['POST'])
@limiter.limit("240 per hour")
@require_api_key_or_permission('automation.manage')
def score_reliability():
    """Score host reliability using safe WMI boundary or Linux test-double."""
    payload = request.get_json(silent=True) or {}
    host_name = str(payload.get('host_name') or '').strip()
    if not host_name:
        log_audit_event('reliability.score', outcome='failure', reason='host_name_missing')
        return jsonify({'error': 'Validation failed', 'details': {'host_name': ['Field required.']}}), 400

    allowed_hosts_raw = current_app.config.get('RELIABILITY_ALLOWED_HOSTS', '')
    allowed_hosts = [
        item.strip()
        for item in str(allowed_hosts_raw).split(',')
        if item.strip()
    ]

    score_raw = current_app.config.get('RELIABILITY_LINUX_SCORER_TEST_DOUBLE', '')
    linux_test_double_reliability_scores: dict[str, str] = {}
    for pair in str(score_raw).split(';'):
        pair = pair.strip()
        if '=' not in pair:
            continue
        key, value = pair.split('=', 1)
        key = key.strip()
        value = value.strip()
        if key:
            linux_test_double_reliability_scores[key] = value

    runtime_config = {
        'organization_id': g.tenant.id,
        'allowed_hosts': allowed_hosts,
        'reliability_scorer_adapter': current_app.config.get('RELIABILITY_SCORER_ADAPTER', 'linux_test_double'),
        'linux_test_double_reliability_scores': linux_test_double_reliability_scores,
        'command_timeout_seconds': int(current_app.config.get('AUTOMATION_COMMAND_TIMEOUT_SECONDS', 8)),
    }

    result, error = ReliabilityService.score_reliability(host_name, runtime_config=runtime_config)
    _record_reliability_run(
        organization_id=g.tenant.id,
        diagnostic_type='score',
        host_name=host_name,
        request_payload={'host_name': host_name},
        result=result,
        error=error,
    )
    if error:
        log_audit_event('reliability.score', outcome='failure', reason=error, host_name=host_name)
        if error == 'command_failed':
            return jsonify({'error': 'Reliability score command failed', 'details': result}), 503
        return jsonify({'error': 'Validation failed', 'details': result}), 400

    reliability_score = result.get('reliability_score') or {}
    log_audit_event(
        'reliability.score',
        outcome='success',
        host_name=host_name,
        adapter=result.get('adapter'),
        current_score=reliability_score.get('current_score'),
        health_band=reliability_score.get('health_band'),
    )
    return jsonify({'status': 'success', 'reliability': result}), 200


@api_bp.route('/reliability/trends/analyze', methods=['POST'])
@limiter.limit("240 per hour")
@require_api_key_or_permission('automation.manage')
def analyze_reliability_trend():
    """Analyze reliability score trends via safe boundary or Linux test-double."""
    payload = request.get_json(silent=True) or {}
    host_name = str(payload.get('host_name') or '').strip()
    if not host_name:
        log_audit_event('reliability.trend', outcome='failure', reason='host_name_missing')
        return jsonify({'error': 'Validation failed', 'details': {'host_name': ['Field required.']}}), 400

    allowed_hosts_raw = current_app.config.get('RELIABILITY_ALLOWED_HOSTS', '')
    allowed_hosts = [
        item.strip()
        for item in str(allowed_hosts_raw).split(',')
        if item.strip()
    ]

    trend_raw = current_app.config.get('RELIABILITY_LINUX_TREND_TEST_DOUBLE', '')
    linux_test_double_reliability_trends: dict[str, str] = {}
    for pair in str(trend_raw).split(';'):
        pair = pair.strip()
        if '=' not in pair:
            continue
        key, value = pair.split('=', 1)
        key = key.strip()
        value = value.strip()
        if key:
            linux_test_double_reliability_trends[key] = value

    runtime_config = {
        'organization_id': g.tenant.id,
        'allowed_hosts': allowed_hosts,
        'trend_adapter': current_app.config.get('RELIABILITY_TREND_ADAPTER', 'linux_test_double'),
        'linux_test_double_reliability_trends': linux_test_double_reliability_trends,
        'window_size': int(current_app.config.get('RELIABILITY_TREND_WINDOW_SIZE', 6)),
        'command_timeout_seconds': int(current_app.config.get('AUTOMATION_COMMAND_TIMEOUT_SECONDS', 8)),
    }

    result, error = ReliabilityService.analyze_reliability_trend(host_name, runtime_config=runtime_config)
    _record_reliability_run(
        organization_id=g.tenant.id,
        diagnostic_type='trend',
        host_name=host_name,
        request_payload={'host_name': host_name},
        result=result,
        error=error,
    )
    if error:
        log_audit_event('reliability.trend', outcome='failure', reason=error, host_name=host_name)
        if error == 'command_failed':
            return jsonify({'error': 'Reliability trend command failed', 'details': result}), 503
        return jsonify({'error': 'Validation failed', 'details': result}), 400

    trend = result.get('trend') or {}
    log_audit_event(
        'reliability.trend',
        outcome='success',
        host_name=host_name,
        adapter=result.get('adapter'),
        direction=trend.get('direction'),
        point_count=trend.get('point_count', 0),
    )
    return jsonify({'status': 'success', 'trend': result}), 200


@api_bp.route('/reliability/predictions/analyze', methods=['POST'])
@limiter.limit("240 per hour")
@require_api_key_or_permission('automation.manage')
def analyze_reliability_prediction():
    """Predict near-term reliability using safe boundary or Linux test-double."""
    payload = request.get_json(silent=True) or {}
    host_name = str(payload.get('host_name') or '').strip()
    if not host_name:
        log_audit_event('reliability.prediction', outcome='failure', reason='host_name_missing')
        return jsonify({'error': 'Validation failed', 'details': {'host_name': ['Field required.']}}), 400

    allowed_hosts_raw = current_app.config.get('RELIABILITY_ALLOWED_HOSTS', '')
    allowed_hosts = [
        item.strip()
        for item in str(allowed_hosts_raw).split(',')
        if item.strip()
    ]

    prediction_raw = current_app.config.get('RELIABILITY_LINUX_PREDICTION_TEST_DOUBLE', '')
    linux_test_double_reliability_predictions: dict[str, str] = {}
    for pair in str(prediction_raw).split(';'):
        pair = pair.strip()
        if '=' not in pair:
            continue
        key, value = pair.split('=', 1)
        key = key.strip()
        value = value.strip()
        if key:
            linux_test_double_reliability_predictions[key] = value

    runtime_config = {
        'organization_id': g.tenant.id,
        'allowed_hosts': allowed_hosts,
        'prediction_adapter': current_app.config.get('RELIABILITY_PREDICTION_ADAPTER', 'linux_test_double'),
        'linux_test_double_reliability_predictions': linux_test_double_reliability_predictions,
        'window_size': int(current_app.config.get('RELIABILITY_PREDICTION_WINDOW_SIZE', 6)),
        'prediction_horizon': int(current_app.config.get('RELIABILITY_PREDICTION_HORIZON', 2)),
        'command_timeout_seconds': int(current_app.config.get('AUTOMATION_COMMAND_TIMEOUT_SECONDS', 8)),
    }

    result, error = ReliabilityService.predict_reliability(host_name, runtime_config=runtime_config)
    _record_reliability_run(
        organization_id=g.tenant.id,
        diagnostic_type='prediction',
        host_name=host_name,
        request_payload={'host_name': host_name},
        result=result,
        error=error,
    )
    if error:
        log_audit_event('reliability.prediction', outcome='failure', reason=error, host_name=host_name)
        if error == 'command_failed':
            return jsonify({'error': 'Reliability prediction command failed', 'details': result}), 503
        return jsonify({'error': 'Validation failed', 'details': result}), 400

    prediction = result.get('prediction') or {}
    log_audit_event(
        'reliability.prediction',
        outcome='success',
        host_name=host_name,
        adapter=result.get('adapter'),
        direction=prediction.get('direction'),
        predicted_score=prediction.get('predicted_score'),
    )
    return jsonify({'status': 'success', 'prediction': result}), 200


@api_bp.route('/reliability/patterns/detect', methods=['POST'])
@limiter.limit("240 per hour")
@require_api_key_or_permission('automation.manage')
def detect_reliability_patterns():
    """Detect reliability patterns using safe boundary or Linux test-double."""
    payload = request.get_json(silent=True) or {}
    host_name = str(payload.get('host_name') or '').strip()
    if not host_name:
        log_audit_event('reliability.patterns', outcome='failure', reason='host_name_missing')
        return jsonify({'error': 'Validation failed', 'details': {'host_name': ['Field required.']}}), 400

    allowed_hosts_raw = current_app.config.get('RELIABILITY_ALLOWED_HOSTS', '')
    allowed_hosts = [
        item.strip()
        for item in str(allowed_hosts_raw).split(',')
        if item.strip()
    ]

    pattern_raw = current_app.config.get('RELIABILITY_LINUX_PATTERN_TEST_DOUBLE', '')
    linux_test_double_reliability_patterns: dict[str, str] = {}
    for pair in str(pattern_raw).split(';'):
        pair = pair.strip()
        if '=' not in pair:
            continue
        key, value = pair.split('=', 1)
        key = key.strip()
        value = value.strip()
        if key:
            linux_test_double_reliability_patterns[key] = value

    runtime_config = {
        'organization_id': g.tenant.id,
        'allowed_hosts': allowed_hosts,
        'pattern_adapter': current_app.config.get('RELIABILITY_PATTERN_ADAPTER', 'linux_test_double'),
        'linux_test_double_reliability_patterns': linux_test_double_reliability_patterns,
        'window_size': int(current_app.config.get('RELIABILITY_PATTERN_WINDOW_SIZE', 6)),
        'command_timeout_seconds': int(current_app.config.get('AUTOMATION_COMMAND_TIMEOUT_SECONDS', 8)),
    }

    result, error = ReliabilityService.detect_reliability_patterns(host_name, runtime_config=runtime_config)
    _record_reliability_run(
        organization_id=g.tenant.id,
        diagnostic_type='patterns',
        host_name=host_name,
        request_payload={'host_name': host_name},
        result=result,
        error=error,
    )
    if error:
        log_audit_event('reliability.patterns', outcome='failure', reason=error, host_name=host_name)
        if error == 'command_failed':
            return jsonify({'error': 'Reliability pattern command failed', 'details': result}), 503
        return jsonify({'error': 'Validation failed', 'details': result}), 400

    patterns = result.get('patterns') or {}
    log_audit_event(
        'reliability.patterns',
        outcome='success',
        host_name=host_name,
        adapter=result.get('adapter'),
        primary_pattern=patterns.get('primary_pattern'),
        pattern_count=patterns.get('pattern_count', 0),
    )
    return jsonify({'status': 'success', 'patterns': result}), 200


def _parse_csv_config_list(config_key: str) -> list[str]:
    """Split a comma-separated config value into trimmed items."""
    return [
        item.strip()
        for item in str(current_app.config.get(config_key, '')).split(',')
        if item.strip()
    ]


def _parse_semicolon_kv_config(config_key: str) -> dict[str, str]:
    """Parse `key=value;key=value` config values into a dict."""
    parsed: dict[str, str] = {}
    for pair in str(current_app.config.get(config_key, '')).split(';'):
        pair = pair.strip()
        if '=' not in pair:
            continue
        key, value = pair.split('=', 1)
        key = key.strip()
        value = value.strip()
        if key:
            parsed[key] = value
    return parsed


def _build_ollama_runtime_config(model_override: str = '', **extra):
    """Build shared safe runtime config for AI/Ollama-backed routes."""
    runtime_config = {
        'adapter': current_app.config.get('OLLAMA_ADAPTER', 'linux_test_double'),
        'endpoint': current_app.config.get('OLLAMA_ENDPOINT', 'http://localhost:11434/api/generate'),
        'allowed_hosts': _parse_csv_config_list('OLLAMA_ALLOWED_HOSTS'),
        'model': model_override or current_app.config.get('OLLAMA_DEFAULT_MODEL', 'llama3.2'),
        'allowed_models': _parse_csv_config_list('OLLAMA_ALLOWED_MODELS'),
        'linux_test_double_responses': _parse_semicolon_kv_config('OLLAMA_LINUX_TEST_DOUBLE_RESPONSES'),
        'fallback_to_test_double_on_http_error': bool(
            current_app.config.get('OLLAMA_HTTP_FALLBACK_TO_TEST_DOUBLE', False)
        ),
        'timeout_seconds': int(current_app.config.get('OLLAMA_TIMEOUT_SECONDS', 8)),
        'prompt_max_chars': int(current_app.config.get('OLLAMA_PROMPT_MAX_CHARS', 4000)),
        'response_max_chars': int(current_app.config.get('OLLAMA_RESPONSE_MAX_CHARS', 4000)),
    }
    runtime_config.update(extra)
    return runtime_config


def _coerce_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _build_ai_operations_report(tenant_id: int, limit: int = 10):
    """Build a tenant-scoped operational report across AI audit events."""
    ai_actions = (
        'ai.ollama.inference',
        'ai.root_cause.analyze',
        'ai.recommendations.generate',
        'ai.troubleshooting.assist',
        'ai.learning.feedback',
        'ai.anomaly.analyze',
        'ai.incident.explain',
        'ai.confidence.score',
    )

    events = (
        AuditEvent.query
        .filter(
            ((AuditEvent.tenant_id == tenant_id) | (AuditEvent.tenant_id.is_(None)))
            & AuditEvent.action.in_(ai_actions)
        )
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
        .limit(max(limit, 1) * 5)
        .all()
    )

    action_counts: dict[str, int] = {}
    outcome_counts = {'success': 0, 'failure': 0}
    adapter_counts: dict[str, int] = {}
    primary_error_counts: dict[str, int] = {}
    fallback_count = 0
    duration_values: list[int] = []
    recent_operations: list[dict[str, object]] = []
    recent_failures: list[dict[str, object]] = []

    for event in events:
        metadata = event.event_metadata or {}
        action_counts[event.action] = action_counts.get(event.action, 0) + 1
        if event.outcome in outcome_counts:
            outcome_counts[event.outcome] += 1

        adapter = (
            metadata.get('adapter')
            or metadata.get('requested_adapter')
            or metadata.get('from_adapter')
        )
        if adapter:
            adapter = str(adapter)
            adapter_counts[adapter] = adapter_counts.get(adapter, 0) + 1

        if str(metadata.get('fallback_used')).lower() == 'true':
            fallback_count += 1

        duration_ms = _coerce_int(metadata.get('duration_ms'), default=-1)
        if duration_ms >= 0:
            duration_values.append(duration_ms)

        error_reason = metadata.get('primary_error_reason') or metadata.get('reason')
        if error_reason:
            error_reason = str(error_reason)
            primary_error_counts[error_reason] = primary_error_counts.get(error_reason, 0) + 1

        item = {
            'id': event.id,
            'created_at': event.created_at.isoformat() if event.created_at else None,
            'action': event.action,
            'outcome': event.outcome,
            'adapter': adapter,
            'model': metadata.get('model'),
            'fallback_used': str(metadata.get('fallback_used')).lower() == 'true',
            'duration_ms': duration_ms if duration_ms >= 0 else None,
            'primary_error_reason': metadata.get('primary_error_reason'),
            'reason': metadata.get('reason'),
            'metadata': metadata,
        }

        if len(recent_operations) < limit:
            recent_operations.append(item)
        if event.outcome == 'failure' and len(recent_failures) < limit:
            recent_failures.append(item)

    total_events = len(events)
    success_count = outcome_counts['success']
    failure_count = outcome_counts['failure']
    avg_duration_ms = (
        round(sum(duration_values) / len(duration_values))
        if duration_values
        else None
    )

    return {
        'summary': {
            'total_events': total_events,
            'success_count': success_count,
            'failure_count': failure_count,
            'fallback_count': fallback_count,
            'success_rate': round((success_count / total_events) * 100, 1) if total_events else None,
            'avg_duration_ms': avg_duration_ms,
        },
        'counts': {
            'by_action': action_counts,
            'by_adapter': adapter_counts,
            'by_primary_error_reason': primary_error_counts,
        },
        'recent_operations': recent_operations,
        'recent_failures': recent_failures,
    }


@api_bp.route('/ai/ollama/infer', methods=['POST'])
@limiter.limit("240 per hour")
@require_api_key_or_permission('automation.manage')
def run_ollama_inference():
    """Run local Ollama inference via safe boundary or Linux test-double."""
    payload = request.get_json(silent=True) or {}
    prompt_text = str(payload.get('prompt') or '').strip()
    if not prompt_text:
        log_audit_event('ai.ollama.inference', outcome='failure', reason='prompt_missing')
        return jsonify({'error': 'Validation failed', 'details': {'prompt': ['Field required.']}}), 400

    model_override = str(payload.get('model') or '').strip()

    runtime_config = _build_ollama_runtime_config(model_override=model_override)

    result, error = AIService.run_ollama_inference(prompt_text, runtime_config=runtime_config)
    observability = result.get('observability') or {}
    if error:
        log_audit_event(
            'ai.ollama.inference',
            outcome='failure',
            reason=error,
            model=runtime_config['model'],
            requested_adapter=runtime_config['adapter'],
            duration_ms=observability.get('duration_ms'),
            fallback_used=observability.get('fallback_used'),
            primary_error_reason=observability.get('primary_error_reason'),
        )
        if error == 'command_failed':
            return jsonify({'error': 'Ollama inference request failed', 'details': result}), 503
        return jsonify({'error': 'Validation failed', 'details': result}), 400

    inference = result.get('inference') or {}
    log_audit_event(
        'ai.ollama.inference',
        outcome='success',
        adapter=result.get('adapter'),
        model=result.get('model'),
        response_chars=inference.get('response_chars', 0),
        duration_ms=observability.get('duration_ms'),
        fallback_used=observability.get('fallback_used'),
    )
    return jsonify({'status': 'success', 'ollama': result}), 200


@api_bp.route('/ai/operations/report', methods=['GET'])
@require_api_key_or_permission('automation.manage')
def get_ai_operations_report():
    """Return a tenant-scoped operational summary across AI/Ollama activity."""
    limit = max(min(int(request.args.get('limit', 10) or 10), 25), 1)
    report = _build_ai_operations_report(g.tenant.id, limit=limit)
    return jsonify({'status': 'success', 'report': report}), 200


@api_bp.route('/ai/root-cause/analyze', methods=['POST'])
@limiter.limit("240 per hour")
@require_api_key_or_permission('automation.manage')
def analyze_root_cause():
    """Analyze probable root cause via safe Ollama wrapper boundary."""
    payload = request.get_json(silent=True) or {}
    symptom_summary = str(payload.get('symptom_summary') or '').strip()
    evidence_points = payload.get('evidence_points')

    if not symptom_summary:
        log_audit_event('ai.root_cause.analyze', outcome='failure', reason='symptom_summary_missing')
        return jsonify({'error': 'Validation failed', 'details': {'symptom_summary': ['Field required.']}}), 400

    if evidence_points is None:
        evidence_points = []
    if not isinstance(evidence_points, list):
        log_audit_event('ai.root_cause.analyze', outcome='failure', reason='evidence_points_invalid')
        return jsonify({'error': 'Validation failed', 'details': {'evidence_points': ['Must be a list.']}}), 400

    model_override = str(payload.get('model') or '').strip()

    runtime_config = _build_ollama_runtime_config(
        model_override=model_override,
        max_evidence_points=int(current_app.config.get('AI_ROOT_CAUSE_MAX_EVIDENCE_POINTS', 8)),
    )

    result, error = AIService.analyze_root_cause(
        symptom_summary,
        evidence_points=evidence_points,
        runtime_config=runtime_config,
    )
    observability = result.get('observability') or {}
    if error:
        log_audit_event(
            'ai.root_cause.analyze',
            outcome='failure',
            reason=error,
            model=runtime_config['model'],
            requested_adapter=runtime_config['adapter'],
            duration_ms=observability.get('duration_ms'),
            fallback_used=observability.get('fallback_used'),
            primary_error_reason=observability.get('primary_error_reason'),
        )
        if error == 'command_failed':
            return jsonify({'error': 'Root cause analysis request failed', 'details': result}), 503
        return jsonify({'error': 'Validation failed', 'details': result}), 400

    root_cause = result.get('root_cause') or {}
    log_audit_event(
        'ai.root_cause.analyze',
        outcome='success',
        adapter=result.get('adapter'),
        model=result.get('model'),
        confidence=root_cause.get('confidence'),
        duration_ms=observability.get('duration_ms'),
        fallback_used=observability.get('fallback_used'),
    )
    return jsonify({'status': 'success', 'analysis': result}), 200


@api_bp.route('/ai/recommendations/generate', methods=['POST'])
@limiter.limit("240 per hour")
@require_api_key_or_permission('automation.manage')
def generate_recommendations():
    """Generate remediation recommendations via safe Ollama wrapper boundary."""
    payload = request.get_json(silent=True) or {}
    symptom_summary = str(payload.get('symptom_summary') or '').strip()
    probable_cause = str(payload.get('probable_cause') or '').strip()
    evidence_points = payload.get('evidence_points')

    if not symptom_summary:
        log_audit_event('ai.recommendations.generate', outcome='failure', reason='symptom_summary_missing')
        return jsonify({'error': 'Validation failed', 'details': {'symptom_summary': ['Field required.']}}), 400

    if not probable_cause:
        log_audit_event('ai.recommendations.generate', outcome='failure', reason='probable_cause_missing')
        return jsonify({'error': 'Validation failed', 'details': {'probable_cause': ['Field required.']}}), 400

    if evidence_points is None:
        evidence_points = []
    if not isinstance(evidence_points, list):
        log_audit_event('ai.recommendations.generate', outcome='failure', reason='evidence_points_invalid')
        return jsonify({'error': 'Validation failed', 'details': {'evidence_points': ['Must be a list.']}}), 400

    model_override = str(payload.get('model') or '').strip()

    runtime_config = _build_ollama_runtime_config(
        model_override=model_override,
        max_evidence_points=int(current_app.config.get('AI_ROOT_CAUSE_MAX_EVIDENCE_POINTS', 8)),
        max_recommendations=int(current_app.config.get('AI_RECOMMENDATION_MAX_ITEMS', 3)),
    )

    result, error = AIService.generate_recommendations(
        symptom_summary,
        probable_cause,
        evidence_points=evidence_points,
        runtime_config=runtime_config,
    )
    observability = result.get('observability') or {}
    if error:
        log_audit_event(
            'ai.recommendations.generate',
            outcome='failure',
            reason=error,
            model=runtime_config['model'],
            requested_adapter=runtime_config['adapter'],
            duration_ms=observability.get('duration_ms'),
            fallback_used=observability.get('fallback_used'),
            primary_error_reason=observability.get('primary_error_reason'),
        )
        if error == 'command_failed':
            return jsonify({'error': 'Recommendation engine request failed', 'details': result}), 503
        return jsonify({'error': 'Validation failed', 'details': result}), 400

    recommendations = result.get('recommendations') or {}
    log_audit_event(
        'ai.recommendations.generate',
        outcome='success',
        adapter=result.get('adapter'),
        model=result.get('model'),
        recommendation_count=recommendations.get('count', 0),
        confidence=recommendations.get('confidence'),
        duration_ms=observability.get('duration_ms'),
        fallback_used=observability.get('fallback_used'),
    )
    return jsonify({'status': 'success', 'recommendations': result}), 200


@api_bp.route('/ai/troubleshooting/assist', methods=['POST'])
@limiter.limit("240 per hour")
@require_api_key_or_permission('automation.manage')
def assist_troubleshooting():
    """Provide troubleshooting assistant guidance via safe Ollama wrapper boundary."""
    payload = request.get_json(silent=True) or {}
    question = str(payload.get('question') or '').strip()
    context_items = payload.get('context_items')

    if not question:
        log_audit_event('ai.troubleshooting.assist', outcome='failure', reason='question_missing')
        return jsonify({'error': 'Validation failed', 'details': {'question': ['Field required.']}}), 400

    if context_items is None:
        context_items = []
    if not isinstance(context_items, list):
        log_audit_event('ai.troubleshooting.assist', outcome='failure', reason='context_items_invalid')
        return jsonify({'error': 'Validation failed', 'details': {'context_items': ['Must be a list.']}}), 400

    model_override = str(payload.get('model') or '').strip()

    runtime_config = _build_ollama_runtime_config(
        model_override=model_override,
        max_context_items=int(current_app.config.get('AI_TROUBLESHOOT_MAX_CONTEXT_ITEMS', 10)),
        max_steps=int(current_app.config.get('AI_TROUBLESHOOT_MAX_STEPS', 5)),
        max_question_chars=int(current_app.config.get('AI_TROUBLESHOOT_MAX_QUESTION_CHARS', 1200)),
    )

    result, error = AIService.assist_troubleshooting(
        question,
        context_items=context_items,
        runtime_config=runtime_config,
    )
    observability = result.get('observability') or {}
    if error:
        log_audit_event(
            'ai.troubleshooting.assist',
            outcome='failure',
            reason=error,
            model=runtime_config['model'],
            requested_adapter=runtime_config['adapter'],
            duration_ms=observability.get('duration_ms'),
            fallback_used=observability.get('fallback_used'),
            primary_error_reason=observability.get('primary_error_reason'),
        )
        if error == 'command_failed':
            return jsonify({'error': 'Troubleshooting assistant request failed', 'details': result}), 503
        return jsonify({'error': 'Validation failed', 'details': result}), 400

    guidance = result.get('guidance') or {}
    log_audit_event(
        'ai.troubleshooting.assist',
        outcome='success',
        adapter=result.get('adapter'),
        model=result.get('model'),
        step_count=guidance.get('step_count', 0),
        confidence=guidance.get('confidence'),
        duration_ms=observability.get('duration_ms'),
        fallback_used=observability.get('fallback_used'),
    )
    return jsonify({'status': 'success', 'assistant': result}), 200


@api_bp.route('/ai/learning/feedback', methods=['POST'])
@limiter.limit("240 per hour")
@require_api_key_or_permission('automation.manage')
def handle_learning_feedback():
    """Extract reusable lessons from operator feedback via safe Ollama wrapper boundary."""
    payload = request.get_json(silent=True) or {}
    issue_summary = str(payload.get('issue_summary') or '').strip()
    resolution_summary = str(payload.get('resolution_summary') or '').strip()
    outcome = str(payload.get('outcome') or 'resolved').strip()
    tags = payload.get('tags')

    if not issue_summary:
        log_audit_event('ai.learning.feedback', outcome='failure', reason='issue_summary_missing')
        return jsonify({'error': 'Validation failed', 'details': {'issue_summary': ['Field required.']}}), 400

    if not resolution_summary:
        log_audit_event('ai.learning.feedback', outcome='failure', reason='resolution_summary_missing')
        return jsonify({'error': 'Validation failed', 'details': {'resolution_summary': ['Field required.']}}), 400

    if tags is None:
        tags = []
    if not isinstance(tags, list):
        log_audit_event('ai.learning.feedback', outcome='failure', reason='tags_invalid')
        return jsonify({'error': 'Validation failed', 'details': {'tags': ['Must be a list.']}}), 400

    model_override = str(payload.get('model') or '').strip()

    runtime_config = _build_ollama_runtime_config(
        model_override=model_override,
        max_tags=int(current_app.config.get('AI_LEARNING_MAX_TAGS', 8)),
    )

    result, error = AIService.learn_from_resolution(
        issue_summary,
        resolution_summary,
        outcome=outcome,
        tags=tags,
        runtime_config=runtime_config,
    )
    observability = result.get('observability') or {}
    if error:
        log_audit_event(
            'ai.learning.feedback',
            outcome='failure',
            reason=error,
            model=runtime_config['model'],
            requested_adapter=runtime_config['adapter'],
            duration_ms=observability.get('duration_ms'),
            fallback_used=observability.get('fallback_used'),
            primary_error_reason=observability.get('primary_error_reason'),
        )
        if error == 'command_failed':
            return jsonify({'error': 'Learning feedback request failed', 'details': result}), 503
        return jsonify({'error': 'Validation failed', 'details': result}), 400

    learning = result.get('learning') or {}
    log_audit_event(
        'ai.learning.feedback',
        outcome='success',
        adapter=result.get('adapter'),
        model=result.get('model'),
        outcome_label=result.get('outcome'),
        confidence=learning.get('confidence'),
        duration_ms=observability.get('duration_ms'),
        fallback_used=observability.get('fallback_used'),
    )
    return jsonify({'status': 'success', 'learning_feedback': result}), 200


@api_bp.route('/updates/runs', methods=['GET'])
@require_api_key_or_permission('automation.manage')
def list_update_runs_api():
    """List tenant-scoped update monitoring executions."""
    page = max(int(request.args.get('page', 1) or 1), 1)
    per_page = max(min(int(request.args.get('per_page', 25) or 25), 100), 1)
    query = UpdateRun.query.filter_by(organization_id=g.tenant.id)

    host_name = str(request.args.get('host_name') or '').strip()
    if host_name:
        query = query.filter_by(host_name=host_name)

    status = str(request.args.get('status') or '').strip()
    if status:
        query = query.filter_by(status=status)

    pagination = query.order_by(UpdateRun.created_at.desc(), UpdateRun.id.desc()).paginate(
        page=page,
        per_page=per_page,
        error_out=False,
    )
    return jsonify({
        'status': 'success',
        'page': page,
        'per_page': per_page,
        'total': pagination.total,
        'pages': pagination.pages,
        'update_runs': [item.to_dict() for item in pagination.items],
    }), 200


@api_bp.route('/updates/runs/<int:run_id>', methods=['GET'])
@require_api_key_or_permission('automation.manage')
def get_update_run_api(run_id):
    """Return one tenant-scoped update monitoring execution."""
    item = UpdateRun.query.filter_by(id=run_id, organization_id=g.tenant.id).first()
    if not item:
        return jsonify({'error': 'Update run not found'}), 404
    return jsonify({'status': 'success', 'update_run': item.to_dict()}), 200


@api_bp.route('/updates/monitor', methods=['POST'])
@limiter.limit("240 per hour")
@require_api_key_or_permission('automation.manage')
def monitor_windows_updates():
    """Collect Windows Update status through safe adapter boundary."""
    payload = request.get_json(silent=True) or {}
    host_name = str(payload.get('host_name') or '').strip()
    if not host_name:
        log_audit_event('updates.monitor', outcome='failure', reason='host_name_missing')
        return jsonify({'error': 'Validation failed', 'details': {'host_name': ['Field required.']}}), 400

    allowed_hosts_raw = current_app.config.get('UPDATE_ALLOWED_HOSTS', '')
    allowed_hosts = [
        item.strip()
        for item in str(allowed_hosts_raw).split(',')
        if item.strip()
    ]

    updates_raw = current_app.config.get('UPDATE_LINUX_MONITOR_TEST_DOUBLE', '')
    linux_test_double_updates: dict[str, list[str]] = {}
    for pair in str(updates_raw).split(';'):
        pair = pair.strip()
        if '=' not in pair:
            continue
        key, value = pair.split('=', 1)
        key = key.strip()
        if not key:
            continue
        entries = [item.strip() for item in value.split('||') if item.strip()]
        linux_test_double_updates[key] = entries

    runtime_config = {
        'allowed_hosts': allowed_hosts,
        'update_monitor_adapter': current_app.config.get('UPDATE_MONITOR_ADAPTER', 'linux_test_double'),
        'linux_test_double_updates': linux_test_double_updates,
        'max_updates': int(current_app.config.get('UPDATE_MONITOR_MAX_ENTRIES', 25)),
        'command_timeout_seconds': int(current_app.config.get('AUTOMATION_COMMAND_TIMEOUT_SECONDS', 8)),
    }

    result, error = UpdateService.monitor_windows_updates(host_name, runtime_config=runtime_config)
    update_run = _record_update_run(
        organization_id=g.tenant.id,
        host_name=host_name,
        result=result,
        error=error,
    )
    if error:
        log_audit_event('updates.monitor', outcome='failure', reason=error, host_name=host_name)
        if error == 'command_failed':
            return jsonify({'error': 'Windows Update monitor command failed', 'details': result}), 503
        return jsonify({'error': 'Validation failed', 'details': result}), 400

    log_audit_event(
        'updates.monitor',
        outcome='success',
        host_name=host_name,
        adapter=result.get('adapter'),
        update_count=result.get('update_count', 0),
        latest_installed_on=result.get('latest_installed_on'),
    )
    result['update_run_id'] = update_run.id
    return jsonify({'status': 'success', 'updates': result}), 200


@api_bp.route('/ai/confidence/score', methods=['POST'])
@limiter.limit("240 per hour")
@require_api_key_or_permission('automation.manage')
def score_update_confidence():
    """Score AI confidence in reliability impact of pending updates."""
    payload = request.get_json(silent=True) or {}
    host_name = str(payload.get('host_name') or '').strip()
    if not host_name:
        log_audit_event('ai.confidence.score', outcome='failure', reason='host_name_missing')
        return jsonify({'error': 'Validation failed', 'details': {'host_name': ['Field required.']}}), 400

    updates_list = payload.get('updates') or []
    if not isinstance(updates_list, list):
        updates_list = []

    update_run_id = payload.get('update_run_id')
    update_run: UpdateRun | None = None
    if update_run_id is not None and str(update_run_id).strip().isdigit():
        update_run = UpdateRun.query.filter_by(id=int(update_run_id), organization_id=g.tenant.id).first()

    reliability_score = payload.get('reliability_score')
    if reliability_score is None:
        reliability_score = 0.5
    try:
        reliability_score = float(reliability_score)
    except (TypeError, ValueError):
        reliability_score = 0.5

    model_override = str(payload.get('model') or '').strip()

    allowed_hosts_raw = current_app.config.get('CONFIDENCE_ALLOWED_HOSTS', '')
    allowed_hosts = [
        item.strip()
        for item in str(allowed_hosts_raw).split(',')
        if item.strip()
    ]

    allowed_models_raw = current_app.config.get('CONFIDENCE_ALLOWED_MODELS', '')
    allowed_models = [
        item.strip()
        for item in str(allowed_models_raw).split(',')
        if item.strip()
    ]

    scores_raw = current_app.config.get('CONFIDENCE_LINUX_TEST_DOUBLE_SCORES', '')
    linux_test_double_confidence_scores: dict[str, str] = {}
    for pair in str(scores_raw).split(';'):
        pair = pair.strip()
        if '=' not in pair:
            continue
        key, value = pair.split('=', 1)
        key = key.strip()
        value = value.strip()
        if key:
            linux_test_double_confidence_scores[key] = value

    # Build runtime config for actual services
    ollama_responses_raw = current_app.config.get('OLLAMA_LINUX_TEST_DOUBLE_RESPONSES', '')
    linux_test_double_ollama_responses: dict[str, str] = {}
    for pair in str(ollama_responses_raw).split(';'):
        pair = pair.strip()
        if '=' not in pair:
            continue
        key, value = pair.split('=', 1)
        key = key.strip()
        value = value.strip()
        if key:
            linux_test_double_ollama_responses[key] = value

    runtime_config = {
        'allowed_hosts': allowed_hosts,
        'confidence_adapter': current_app.config.get('CONFIDENCE_ADAPTER', 'linux_test_double'),
        'confidence_allowed_models': allowed_models,
        'linux_test_double_confidence_scores': linux_test_double_confidence_scores,
        'linux_test_double_responses': linux_test_double_ollama_responses,
        'ollama_endpoint': current_app.config.get('OLLAMA_ENDPOINT', 'http://localhost:11434/api/generate'),
        'command_timeout_seconds': int(current_app.config.get('AUTOMATION_COMMAND_TIMEOUT_SECONDS', 8)),
        'prompt_max_chars': int(current_app.config.get('OLLAMA_PROMPT_MAX_CHARS', 4000)),
        'response_max_chars': int(current_app.config.get('OLLAMA_RESPONSE_MAX_CHARS', 4000)),
    }

    result, error = ConfidenceService.score_update_reliability_impact(
        host_name,
        updates_list=updates_list,
        reliability_score=reliability_score,
        ollama_model=model_override or current_app.config.get('OLLAMA_DEFAULT_MODEL', 'llama3.2'),
        runtime_config=runtime_config,
    )
    if error:
        log_audit_event('ai.confidence.score', outcome='failure', reason=error, host_name=host_name)
        if error == 'command_failed':
            return jsonify({'error': 'Confidence scoring request failed', 'details': result}), 503
        return jsonify({'error': 'Validation failed', 'details': result}), 400

    if update_run is not None:
        update_run.confidence_score = result.get('confidence_score')
        update_run.confidence_payload = result
        summary = dict(update_run.summary or {})
        summary['confidence_score'] = result.get('confidence_score')
        summary['risk_factor_count'] = len(result.get('risk_factors', []))
        update_run.summary = summary
        db.session.commit()

    log_audit_event(
        'ai.confidence.score',
        outcome='success',
        host_name=host_name,
        adapter=result.get('adapter'),
        confidence_score=result.get('confidence_score'),
        risk_factor_count=len(result.get('risk_factors', [])),
    )
    return jsonify({'status': 'success', 'confidence': result, 'update_run_id': update_run.id if update_run else None}), 200


@api_bp.route('/dashboard/status', methods=['GET'])
@limiter.limit("240 per hour")
@require_api_key_or_permission('dashboard.view')
def get_dashboard_aggregate_status():
    """Get unified dashboard status aggregating Week 15 + Week 16 outputs."""
    host_name = request.args.get('host_name', '').strip()
    if not host_name:
        log_audit_event('dashboard.status', outcome='failure', reason='host_name_missing')
        return jsonify({'error': 'Validation failed', 'details': {'host_name': ['Query parameter required.']}}), 400

    allowed_hosts_raw = current_app.config.get('DASHBOARD_ALLOWED_HOSTS', '')
    allowed_hosts = [
        item.strip()
        for item in str(allowed_hosts_raw).split(',')
        if item.strip()
    ]

    # Build sub-service configs
    reliability_allowed_hosts_raw = current_app.config.get('RELIABILITY_ALLOWED_HOSTS', '')
    reliability_allowed_hosts = [
        item.strip()
        for item in str(reliability_allowed_hosts_raw).split(',')
        if item.strip()
    ]

    history_raw = current_app.config.get('RELIABILITY_LINUX_HISTORY_TEST_DOUBLE', '')
    linux_test_double_history: dict[str, list[str]] = {}
    for pair in str(history_raw).split(';'):
        pair = pair.strip()
        if '=' not in pair:
            continue
        key, value = pair.split('=', 1)
        key = key.strip()
        if not key:
            continue
        entries = [item.strip() for item in value.split('||') if item.strip()]
        linux_test_double_history[key] = entries

    reliability_config = {
        'organization_id': g.tenant.id,
        'allowed_hosts': reliability_allowed_hosts or allowed_hosts,
        'history_adapter': current_app.config.get('RELIABILITY_HISTORY_ADAPTER', 'linux_test_double'),
        'reliability_scorer_adapter': current_app.config.get('RELIABILITY_SCORER_ADAPTER', 'linux_test_double'),
        'trend_adapter': current_app.config.get('RELIABILITY_TREND_ADAPTER', 'linux_test_double'),
        'prediction_adapter': current_app.config.get('RELIABILITY_PREDICTION_ADAPTER', 'linux_test_double'),
        'pattern_adapter': current_app.config.get('RELIABILITY_PATTERN_ADAPTER', 'linux_test_double'),
        'linux_test_double_history': linux_test_double_history,
        'linux_test_double_reliability_scores': {k: v for k, v in [item.split('=') for item in str(current_app.config.get('RELIABILITY_LINUX_SCORER_TEST_DOUBLE', '')).split(';') if item.strip() and '=' in item]},
        'linux_test_double_reliability_trends': {k: v for k, v in [item.split('=') for item in str(current_app.config.get('RELIABILITY_LINUX_TREND_TEST_DOUBLE', '')).split(';') if item.strip() and '=' in item]},
        'linux_test_double_reliability_predictions': {k: v for k, v in [item.split('=') for item in str(current_app.config.get('RELIABILITY_LINUX_PREDICTION_TEST_DOUBLE', '')).split(';') if item.strip() and '=' in item]},
        'linux_test_double_reliability_patterns': {k: v for k, v in [item.split('=') for item in str(current_app.config.get('RELIABILITY_LINUX_PATTERN_TEST_DOUBLE', '')).split(';') if item.strip() and '=' in item]},
        'command_timeout_seconds': int(current_app.config.get('AUTOMATION_COMMAND_TIMEOUT_SECONDS', 8)),
    }

    update_allowed_hosts_raw = current_app.config.get('UPDATE_ALLOWED_HOSTS', '')
    update_allowed_hosts = [
        item.strip()
        for item in str(update_allowed_hosts_raw).split(',')
        if item.strip()
    ]

    updates_raw = current_app.config.get('UPDATE_LINUX_MONITOR_TEST_DOUBLE', '')
    linux_test_double_updates: dict[str, list[str]] = {}
    for pair in str(updates_raw).split(';'):
        pair = pair.strip()
        if '=' not in pair:
            continue
        key, value = pair.split('=', 1)
        key = key.strip()
        if not key:
            continue
        entries = [item.strip() for item in value.split('||') if item.strip()]
        linux_test_double_updates[key] = entries

    update_config = {
        'allowed_hosts': update_allowed_hosts or allowed_hosts,
        'update_monitor_adapter': current_app.config.get('UPDATE_MONITOR_ADAPTER', 'linux_test_double'),
        'linux_test_double_updates': linux_test_double_updates,
        'max_updates': int(current_app.config.get('UPDATE_MONITOR_MAX_ENTRIES', 25)),
        'command_timeout_seconds': int(current_app.config.get('AUTOMATION_COMMAND_TIMEOUT_SECONDS', 8)),
    }

    confidence_allowed_hosts_raw = current_app.config.get('CONFIDENCE_ALLOWED_HOSTS', '')
    confidence_allowed_hosts = [
        item.strip()
        for item in str(confidence_allowed_hosts_raw).split(',')
        if item.strip()
    ]

    scores_raw = current_app.config.get('CONFIDENCE_LINUX_TEST_DOUBLE_SCORES', '')
    linux_test_double_confidence_scores: dict[str, str] = {}
    for pair in str(scores_raw).split(';'):
        pair = pair.strip()
        if '=' not in pair:
            continue
        key, value = pair.split('=', 1)
        key = key.strip()
        value = value.strip()
        if key:
            linux_test_double_confidence_scores[key] = value

    confidence_config = {
        'allowed_hosts': confidence_allowed_hosts or allowed_hosts,
        'confidence_adapter': current_app.config.get('CONFIDENCE_ADAPTER', 'linux_test_double'),
        'confidence_allowed_models': [item.strip() for item in str(current_app.config.get('CONFIDENCE_ALLOWED_MODELS', '')).split(',') if item.strip()],
        'linux_test_double_confidence_scores': linux_test_double_confidence_scores,
        'command_timeout_seconds': int(current_app.config.get('AUTOMATION_COMMAND_TIMEOUT_SECONDS', 8)),
    }

    runtime_config = {
        'allowed_hosts': allowed_hosts,
        'reliability_config': reliability_config,
        'update_config': update_config,
        'confidence_config': confidence_config,
    }

    cache_ttl = int(current_app.config.get('CACHE_DASHBOARD_TTL_SECONDS', 45))
    cache_key = f'dashboard:aggregate:{host_name}'

    def _load_dashboard_status():
        dashboard_result, dashboard_error = DashboardService.get_aggregate_dashboard_status(
            host_name,
            runtime_config=runtime_config,
        )
        return {
            'dashboard_result': dashboard_result,
            'dashboard_error': dashboard_error,
        }

    cached_payload, cache_hit = PerformanceService.get_or_compute(
        cache_key,
        loader=_load_dashboard_status,
        ttl_seconds=cache_ttl,
    )
    result = cached_payload.get('dashboard_result') or {}
    error = cached_payload.get('dashboard_error')
    if error:
        log_audit_event('dashboard.status', outcome='failure', reason=error, host_name=host_name)
        if error == 'command_failed':
            return jsonify({'error': 'Dashboard aggregation failed', 'details': result}), 503
        return jsonify({'error': 'Validation failed', 'details': result}), 400

    log_audit_event(
        'dashboard.status',
        outcome='success',
        host_name=host_name,
        aggregate_health=result.get('aggregate_health', {}).get('overall_status'),
        cache_hit=cache_hit,
    )
    return jsonify({'status': 'success', 'dashboard': result, 'cache_hit': cache_hit}), 200


@api_bp.route('/ai/anomaly/analyze', methods=['POST'])
@limiter.limit("120 per hour")
@require_api_key_or_permission('automation.manage')
def analyze_ai_anomalies():
    """Use AI (Ollama) to interpret and explain statistical anomalies."""
    payload = request.get_json(silent=True) or {}
    anomalies = payload.get('anomalies')

    if not anomalies or not isinstance(anomalies, list):
        log_audit_event('ai.anomaly.analyze', outcome='failure', reason='anomalies_missing_or_invalid')
        return jsonify({'error': 'Validation failed', 'details': {'anomalies': ['Must be a non-empty list.']}}), 400

    model_override = str(payload.get('model') or '').strip()

    runtime_config = _build_ollama_runtime_config(
        model_override=model_override,
        ai_anomaly_max_items=10,
    )

    result, error = AIService.analyze_anomalies(anomalies, runtime_config=runtime_config)
    observability = result.get('observability') or {}
    if error:
        log_audit_event(
            'ai.anomaly.analyze',
            outcome='failure',
            reason=error,
            requested_adapter=runtime_config['adapter'],
            model=runtime_config['model'],
            duration_ms=observability.get('duration_ms'),
            fallback_used=observability.get('fallback_used'),
            primary_error_reason=observability.get('primary_error_reason'),
        )
        if error in ('anomalies_missing_or_invalid', 'no_valid_anomalies'):
            return jsonify({'error': 'Validation failed', 'details': result}), 400
        return jsonify({'error': 'Anomaly analysis request failed', 'details': result}), 503

    log_audit_event(
        'ai.anomaly.analyze',
        outcome='success',
        adapter=result.get('adapter'),
        model=result.get('model'),
        anomaly_count=result.get('anomaly_count', 0),
        confidence=result.get('analysis', {}).get('confidence'),
        duration_ms=observability.get('duration_ms'),
        fallback_used=observability.get('fallback_used'),
    )
    return jsonify({'status': 'success', 'anomaly_analysis': result}), 200


# ---------------------------------------------------------------------------
# AI — Incident Explanation  (Phase 2 Week 15-16)
# ---------------------------------------------------------------------------

@api_bp.route('/ai/incident/explain', methods=['POST'])
@limiter.limit("60 per hour")
@require_api_key_or_permission('automation.manage')
def explain_ai_incident():
    """Use AI (Ollama) to generate a structured explanation for an incident."""
    payload = request.get_json(silent=True) or {}

    incident_title = str(payload.get('incident_title') or '').strip()
    if not incident_title:
        log_audit_event('ai.incident.explain', outcome='failure', reason='incident_title_missing')
        return jsonify({'error': 'Validation failed', 'details': {'incident_title': ['Field required.']}}), 400

    affected_systems = payload.get('affected_systems') or []
    metrics_snapshot = payload.get('metrics_snapshot') or {}
    model_override = str(payload.get('model') or '').strip()

    runtime_config = _build_ollama_runtime_config(model_override=model_override)

    result, error = AIService.explain_incident(
        incident_title=incident_title,
        affected_systems=affected_systems,
        metrics_snapshot=metrics_snapshot,
        runtime_config=runtime_config,
    )
    observability = result.get('observability') or {}
    if error:
        log_audit_event(
            'ai.incident.explain',
            outcome='failure',
            reason=error,
            requested_adapter=runtime_config['adapter'],
            model=runtime_config['model'],
            duration_ms=observability.get('duration_ms'),
            fallback_used=observability.get('fallback_used'),
            primary_error_reason=observability.get('primary_error_reason'),
        )
        if error in ('incident_title_missing', 'incident_title_too_long'):
            return jsonify({'error': 'Validation failed', 'details': result}), 400
        return jsonify({'error': 'Incident explanation request failed', 'details': result}), 503

    log_audit_event(
        'ai.incident.explain',
        outcome='success',
        adapter=result.get('adapter'),
        model=result.get('model'),
        incident_title=incident_title[:120],
        confidence=result.get('explanation', {}).get('confidence'),
        duration_ms=observability.get('duration_ms'),
        fallback_used=observability.get('fallback_used'),
    )
    return jsonify({'status': 'success', 'incident_explanation': result}), 200


# ---------------------------------------------------------------------------
# Alerts — Prioritization  (Phase 2 Week 15-16)
# ---------------------------------------------------------------------------

@api_bp.route('/alerts/prioritize', methods=['POST'])
@limiter.limit("120 per hour")
@require_api_key_or_permission('automation.manage')
def prioritize_alerts():
    """Score and rank a list of incoming alerts by severity, type, and anomaly signal."""
    payload = request.get_json(silent=True) or {}
    alerts = payload.get('alerts')

    if not alerts or not isinstance(alerts, list):
        log_audit_event('alerts.prioritize', outcome='failure', reason='alerts_missing_or_invalid')
        return jsonify({'error': 'Validation failed', 'details': {'alerts': ['Must be a non-empty list.']}}), 400

    top_n = payload.get('top_n')
    if top_n is not None:
        try:
            top_n = int(top_n)
            if top_n < 1:
                raise ValueError
        except (TypeError, ValueError):
            return jsonify({'error': 'Validation failed', 'details': {'top_n': ['Must be a positive integer.']}}), 400

    prioritized = AlertService.prioritize_alerts(alerts, top_n=top_n)
    log_audit_event(
        'alerts.prioritize',
        outcome='success',
        alert_count=len(alerts),
        returned_count=len(prioritized),
    )
    return jsonify({'status': 'success', 'prioritized_alerts': prioritized, 'total': len(prioritized)}), 200


# ---------------------------------------------------------------------------
# Automation — Scheduled Jobs  (Phase 2 Week 15-16)
# ---------------------------------------------------------------------------

@api_bp.route('/automation/scheduled-jobs', methods=['GET'])
@limiter.limit("120 per hour")
@require_api_key_or_permission('automation.manage')
def list_scheduled_jobs():
    """List all scheduled automation jobs for the current tenant."""
    organization_id = g.get('organization_id') or 1
    jobs = AutomationService.list_scheduled_jobs(organization_id)
    log_audit_event('automation.scheduled_jobs.list', outcome='success', count=len(jobs))
    return jsonify({'status': 'success', 'scheduled_jobs': [j.to_dict() for j in jobs], 'total': len(jobs)}), 200


@api_bp.route('/automation/scheduled-jobs', methods=['POST'])
@limiter.limit("60 per hour")
@require_api_key_or_permission('automation.manage')
def create_scheduled_job():
    """Create a new scheduled automation job for the current tenant."""
    organization_id = g.get('organization_id') or 1
    payload = request.get_json(silent=True) or {}

    runtime_config = {
        'scheduled_job_max_per_tenant': int(current_app.config.get('SCHEDULED_JOB_MAX_PER_TENANT', 50)),
    }

    job, errors = AutomationService.schedule_job(
        organization_id=organization_id,
        payload=payload,
        runtime_config=runtime_config,
    )
    if errors:
        log_audit_event('automation.scheduled_jobs.create', outcome='failure', reason='validation_failed')
        return jsonify({'error': 'Validation failed', 'details': errors}), 400

    log_audit_event('automation.scheduled_jobs.create', outcome='success', job_id=job.id, workflow_id=job.workflow_id)
    return jsonify({'status': 'success', 'scheduled_job': job.to_dict()}), 201


# ---------------------------------------------------------------------------
# Remote — SSH Command Execution  (Phase 2 Week 15-16)
# ---------------------------------------------------------------------------

@api_bp.route('/remote/exec', methods=['POST'])
@limiter.limit("30 per hour")
@require_api_key_or_permission('automation.manage')
def execute_remote_command():
    """Execute a command on a remote host via SSH with allowlist enforcement."""
    payload = request.get_json(silent=True) or {}

    host = str(payload.get('host') or '').strip()
    command = str(payload.get('command') or '').strip()

    if not host or not command:
        missing = [f for f, v in [('host', host), ('command', command)] if not v]
        log_audit_event('remote.exec', outcome='failure', reason='fields_missing')
        return jsonify({'error': 'Validation failed', 'details': {f: ['Field required.'] for f in missing}}), 400

    allowed_hosts_raw = current_app.config.get('REMOTE_EXEC_ALLOWED_HOSTS', '')
    allowed_commands_raw = current_app.config.get('REMOTE_EXEC_ALLOWED_COMMANDS', '')

    runtime_config = {
        'ssh_adapter': current_app.config.get('REMOTE_EXEC_ADAPTER', 'linux_test_double'),
        'allowed_hosts': [h.strip() for h in str(allowed_hosts_raw).split(',') if h.strip()],
        'allowed_commands': [c.strip() for c in str(allowed_commands_raw).split(',') if c.strip()],
        'ssh_timeout_seconds': int(current_app.config.get('REMOTE_EXEC_TIMEOUT_SECONDS', 10)),
        'linux_test_double_remote_commands': {},
    }

    result, error = RemoteExecutorService.execute_remote_command(host, command, runtime_config=runtime_config)
    if error:
        log_audit_event('remote.exec', outcome='failure', reason=error, host=host)
        if error in ('host_missing', 'command_missing', 'host_invalid', 'command_unsafe_chars', 'command_too_long'):
            return jsonify({'error': 'Validation failed', 'details': result}), 400
        if error in ('host_not_allowlisted', 'command_not_allowlisted', 'adapter_not_allowed'):
            return jsonify({'error': 'Policy blocked', 'details': result}), 403
        return jsonify({'error': 'Remote execution failed', 'details': result}), 503

    log_audit_event(
        'remote.exec',
        outcome='success',
        adapter=result.get('adapter'),
        host=host,
        returncode=result.get('returncode'),
    )
    return jsonify({'status': 'success', 'execution': result}), 200


# ---------------------------------------------------------------------------
# Automation — Self-Healing Loop  (Phase 2 Week 15-16)
# ---------------------------------------------------------------------------

@api_bp.route('/automation/self-heal', methods=['POST'])
@limiter.limit("60 per hour")
@require_api_key_or_permission('automation.manage')
def trigger_self_healing():
    """Evaluate alerts, match workflows, and optionally execute them (self-healing loop)."""
    organization_id = g.get('organization_id') or 1
    payload = request.get_json(silent=True) or {}
    alerts = payload.get('alerts') or []

    dry_run_param = payload.get('dry_run')
    if dry_run_param is None:
        dry_run = bool(current_app.config.get('SELF_HEALING_DRY_RUN', True))
    else:
        dry_run = bool(dry_run_param)

    runtime_config = {
        'self_healing_dry_run': dry_run,
        'self_healing_max_depth': int(current_app.config.get('SELF_HEALING_MAX_DEPTH', 10)),
        'command_executor_adapter': current_app.config.get('AUTOMATION_EXECUTOR_ADAPTER', 'linux_test_double'),
        'linux_test_double_commands': {},
        'allowed_services': [
            item.strip()
            for item in str(current_app.config.get('AUTOMATION_ALLOWED_SERVICES', '')).split(',')
            if item.strip()
        ],
        'restart_binary': current_app.config.get('AUTOMATION_SERVICE_RESTART_BINARY', 'systemctl'),
        'command_timeout_seconds': int(current_app.config.get('AUTOMATION_COMMAND_TIMEOUT_SECONDS', 8)),
        'script_executor_adapter': current_app.config.get('AUTOMATION_SCRIPT_EXECUTOR_ADAPTER', 'subprocess'),
        'allowed_script_roots': [
            item.strip()
            for item in str(current_app.config.get('AUTOMATION_ALLOWED_SCRIPT_ROOTS', '')).split(',')
            if item.strip()
        ],
        'webhook_adapter': current_app.config.get('AUTOMATION_WEBHOOK_ADAPTER', 'urllib'),
        'allowed_webhook_hosts': [
            item.strip()
            for item in str(current_app.config.get('AUTOMATION_ALLOWED_WEBHOOK_HOSTS', '')).split(',')
            if item.strip()
        ],
        'webhook_timeout_seconds': int(current_app.config.get('AUTOMATION_WEBHOOK_TIMEOUT_SECONDS', 5)),
    }

    result = AutomationService.trigger_self_healing(
        organization_id=organization_id,
        alerts=alerts,
        runtime_config=runtime_config,
    )

    log_audit_event(
        'automation.self_heal',
        outcome='success',
        dry_run=dry_run,
        alert_count=result.get('alert_count', 0),
        triggered_count=result.get('triggered_count', 0),
        skipped_count=result.get('skipped_count', 0),
    )
    return jsonify({'status': 'success', 'self_healing': result}), 200

