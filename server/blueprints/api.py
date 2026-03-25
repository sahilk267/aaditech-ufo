"""
API Blueprint
REST API endpoints for agent data submission and system management
"""

import logging
import os
import re
from flask import current_app
from flask import Blueprint, request, jsonify, g, send_file, abort, url_for
from sqlalchemy import text
from werkzeug.utils import secure_filename
from ..extensions import limiter
from ..auth import (
    require_api_key,
    hash_password,
    verify_password,
    issue_jwt_tokens,
    require_refresh_token,
    require_jwt_auth,
    require_permission,
    require_api_key_or_permission,
    revoke_token,
)
from ..schemas import validate_and_clean_system_data
from ..models import db, SystemData, Organization, User, Role, Permission, AuditEvent
from ..audit import log_audit_event
from ..queue import (
    get_queue_status,
    enqueue_maintenance_job,
    enqueue_alert_notification_job,
    enqueue_automation_workflow_job,
)
from ..services import AlertService, AutomationService, LogService, ReliabilityService, AIService, UpdateService, ConfidenceService, DashboardService, RemoteExecutorService, PerformanceService, AgentReleaseService, BackupService
from marshmallow import ValidationError

logger = logging.getLogger(__name__)

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
        item['download_url'] = url_for('api.download_agent_release_api', filename=release.filename, _external=True)
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
    payload['download_url'] = url_for('api.download_agent_release_api', filename=release.filename, _external=True)
    log_audit_event('agent.release.upload.api', outcome='success', version=release.version, filename=release.filename)
    return jsonify({'status': 'success', 'release': payload}), 201


@api_bp.route('/agent/build/status', methods=['GET'])
@require_api_key_or_permission('dashboard.view')
def get_agent_build_status_api():
    """Report whether a server-built agent binary is currently available."""
    binary_path = AgentReleaseService.resolve_built_binary_path(current_app.root_path)
    payload = {
        'binary_available': binary_path.exists() and binary_path.is_file(),
        'binary_name': binary_path.name,
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
    return jsonify({'status': 'success', 'build': result}), 200


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
@require_api_key
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
        release['download_url'] = url_for('api.download_agent_release_api', filename=release.get('filename', ''), _external=True)
    for release in guide.get('downgrade_candidates', []):
        release['download_url'] = url_for('api.download_agent_release_api', filename=release.get('filename', ''), _external=True)

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

    if len(password) < 8:
        log_audit_event('auth.register', outcome='failure', reason='password_too_short', email=email)
        return jsonify({'error': 'Validation failed', 'details': {'password': ['Minimum length is 8']}}), 400

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

    if not verify_password(password, user.password_hash):
        log_audit_event('auth.login', outcome='failure', reason='invalid_credentials', email=email)
        return jsonify({'error': 'Unauthorized', 'message': 'Invalid credentials'}), 401

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
        }
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

    log_audit_event(
        'alerts.evaluate',
        outcome='success',
        threshold_count=len(threshold_alerts),
        anomaly_count=len(anomaly_alerts),
        pattern_count=len(pattern_alerts),
        silenced_count=len(silenced_alerts),
        correlated_count=len(correlated_alerts),
    )

    return jsonify({
        'status': 'success',
        'triggered_count': len(all_alerts),
        'threshold_count': len(threshold_alerts),
        'anomaly_count': len(anomaly_alerts),
        'pattern_count': len(pattern_alerts),
        'silenced_count': len(silenced_alerts),
        'correlated_count': len(correlated_alerts),
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

    inline_result = result.get('result') if result.get('inline') else None
    if inline_result is not None:
        delivery_outcome = 'failure' if inline_result.get('failure_count', 0) > 0 else 'success'
        log_audit_event(
            'alerts.dispatch.delivery',
            outcome=delivery_outcome,
            alerts_count=inline_result.get('alerts_count', 0),
            delivered_channels=','.join(inline_result.get('delivered_channels', [])),
            failure_count=inline_result.get('failure_count', 0),
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


@api_bp.route('/logs/ingest', methods=['POST'])
@limiter.limit("240 per hour")
@require_api_key_or_permission('automation.manage')
def ingest_logs_pipeline():
    """Ingest logs using safe adapter boundary and deterministic test-doubles."""
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

    log_audit_event(
        'logs.ingest',
        outcome='success',
        source_name=source_name,
        adapter=result.get('adapter'),
        entry_count=result.get('entry_count', 0),
    )
    return jsonify({'status': 'success', 'logs': result}), 200


@api_bp.route('/logs/events/query', methods=['POST'])
@limiter.limit("240 per hour")
@require_api_key_or_permission('automation.manage')
def query_windows_event_entries():
    """Query event entries via Windows wrapper adapter or Linux deterministic test-double."""
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

    log_audit_event(
        'logs.events_query',
        outcome='success',
        source_name=source_name,
        adapter=result.get('adapter'),
        entry_count=result.get('entry_count', 0),
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

    log_audit_event(
        'logs.parse',
        outcome='success',
        entry_count=result.get('entry_count', 0),
        structured_count=result.get('structured_count', 0),
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
    """Search logs and return indexed results via adapter boundary."""
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

    runtime_config = {
        'allowed_sources': allowed_sources,
        'search_adapter': current_app.config.get('LOG_SEARCH_ADAPTER', 'linux_test_double'),
        'linux_test_double_search_entries': linux_test_double_search_entries,
        'max_results': int(current_app.config.get('LOG_SEARCH_MAX_RESULTS', 25)),
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
        'allowed_hosts': allowed_hosts,
        'history_adapter': current_app.config.get('RELIABILITY_HISTORY_ADAPTER', 'linux_test_double'),
        'linux_test_double_history': linux_test_double_history,
        'max_records': int(current_app.config.get('RELIABILITY_HISTORY_MAX_RECORDS', 25)),
        'command_timeout_seconds': int(current_app.config.get('AUTOMATION_COMMAND_TIMEOUT_SECONDS', 8)),
    }

    result, error = ReliabilityService.collect_reliability_history(host_name, runtime_config=runtime_config)
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
        'allowed_hosts': allowed_hosts,
        'allowed_dump_roots': allowed_dump_roots,
        'crash_dump_adapter': current_app.config.get('RELIABILITY_CRASH_DUMP_ADAPTER', 'linux_test_double'),
        'linux_test_double_crash_dumps': linux_test_double_crash_dumps,
        'crash_dump_root': current_app.config.get('RELIABILITY_CRASH_DUMP_ROOT', r'C:\\CrashDumps'),
        'command_timeout_seconds': int(current_app.config.get('AUTOMATION_COMMAND_TIMEOUT_SECONDS', 8)),
    }

    result, error = ReliabilityService.parse_crash_dump(host_name, dump_name, runtime_config=runtime_config)
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
        'allowed_hosts': allowed_hosts,
        'allowed_dump_roots': allowed_dump_roots,
        'exception_identifier_adapter': current_app.config.get('RELIABILITY_EXCEPTION_IDENTIFIER_ADAPTER', 'linux_test_double'),
        'linux_test_double_exceptions': linux_test_double_exceptions,
        'crash_dump_root': current_app.config.get('RELIABILITY_CRASH_DUMP_ROOT', r'C:\\CrashDumps'),
        'command_timeout_seconds': int(current_app.config.get('AUTOMATION_COMMAND_TIMEOUT_SECONDS', 8)),
    }

    result, error = ReliabilityService.identify_exception(host_name, dump_name, runtime_config=runtime_config)
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
        'allowed_hosts': allowed_hosts,
        'allowed_dump_roots': allowed_dump_roots,
        'stack_trace_adapter': current_app.config.get('RELIABILITY_STACK_TRACE_ADAPTER', 'linux_test_double'),
        'linux_test_double_stack_traces': linux_test_double_stack_traces,
        'crash_dump_root': current_app.config.get('RELIABILITY_CRASH_DUMP_ROOT', r'C:\\CrashDumps'),
        'command_timeout_seconds': int(current_app.config.get('AUTOMATION_COMMAND_TIMEOUT_SECONDS', 8)),
    }

    result, error = ReliabilityService.analyze_stack_trace(host_name, dump_name, runtime_config=runtime_config)
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
        'allowed_hosts': allowed_hosts,
        'reliability_scorer_adapter': current_app.config.get('RELIABILITY_SCORER_ADAPTER', 'linux_test_double'),
        'linux_test_double_reliability_scores': linux_test_double_reliability_scores,
        'command_timeout_seconds': int(current_app.config.get('AUTOMATION_COMMAND_TIMEOUT_SECONDS', 8)),
    }

    result, error = ReliabilityService.score_reliability(host_name, runtime_config=runtime_config)
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
        'allowed_hosts': allowed_hosts,
        'trend_adapter': current_app.config.get('RELIABILITY_TREND_ADAPTER', 'linux_test_double'),
        'linux_test_double_reliability_trends': linux_test_double_reliability_trends,
        'window_size': int(current_app.config.get('RELIABILITY_TREND_WINDOW_SIZE', 6)),
        'command_timeout_seconds': int(current_app.config.get('AUTOMATION_COMMAND_TIMEOUT_SECONDS', 8)),
    }

    result, error = ReliabilityService.analyze_reliability_trend(host_name, runtime_config=runtime_config)
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
        'allowed_hosts': allowed_hosts,
        'prediction_adapter': current_app.config.get('RELIABILITY_PREDICTION_ADAPTER', 'linux_test_double'),
        'linux_test_double_reliability_predictions': linux_test_double_reliability_predictions,
        'window_size': int(current_app.config.get('RELIABILITY_PREDICTION_WINDOW_SIZE', 6)),
        'prediction_horizon': int(current_app.config.get('RELIABILITY_PREDICTION_HORIZON', 2)),
        'command_timeout_seconds': int(current_app.config.get('AUTOMATION_COMMAND_TIMEOUT_SECONDS', 8)),
    }

    result, error = ReliabilityService.predict_reliability(host_name, runtime_config=runtime_config)
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
        'allowed_hosts': allowed_hosts,
        'pattern_adapter': current_app.config.get('RELIABILITY_PATTERN_ADAPTER', 'linux_test_double'),
        'linux_test_double_reliability_patterns': linux_test_double_reliability_patterns,
        'window_size': int(current_app.config.get('RELIABILITY_PATTERN_WINDOW_SIZE', 6)),
        'command_timeout_seconds': int(current_app.config.get('AUTOMATION_COMMAND_TIMEOUT_SECONDS', 8)),
    }

    result, error = ReliabilityService.detect_reliability_patterns(host_name, runtime_config=runtime_config)
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

    allowed_models_raw = current_app.config.get('OLLAMA_ALLOWED_MODELS', '')
    allowed_models = [
        item.strip()
        for item in str(allowed_models_raw).split(',')
        if item.strip()
    ]

    responses_raw = current_app.config.get('OLLAMA_LINUX_TEST_DOUBLE_RESPONSES', '')
    linux_test_double_responses: dict[str, str] = {}
    for pair in str(responses_raw).split(';'):
        pair = pair.strip()
        if '=' not in pair:
            continue
        key, value = pair.split('=', 1)
        key = key.strip()
        value = value.strip()
        if key:
            linux_test_double_responses[key] = value

    runtime_config = {
        'adapter': current_app.config.get('OLLAMA_ADAPTER', 'linux_test_double'),
        'endpoint': current_app.config.get('OLLAMA_ENDPOINT', 'http://localhost:11434/api/generate'),
        'model': model_override or current_app.config.get('OLLAMA_DEFAULT_MODEL', 'llama3.2'),
        'allowed_models': allowed_models,
        'linux_test_double_responses': linux_test_double_responses,
        'timeout_seconds': int(current_app.config.get('OLLAMA_TIMEOUT_SECONDS', 8)),
        'prompt_max_chars': int(current_app.config.get('OLLAMA_PROMPT_MAX_CHARS', 4000)),
        'response_max_chars': int(current_app.config.get('OLLAMA_RESPONSE_MAX_CHARS', 4000)),
    }

    result, error = AIService.run_ollama_inference(prompt_text, runtime_config=runtime_config)
    if error:
        log_audit_event('ai.ollama.inference', outcome='failure', reason=error, model=runtime_config['model'])
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
    )
    return jsonify({'status': 'success', 'ollama': result}), 200


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

    allowed_models_raw = current_app.config.get('OLLAMA_ALLOWED_MODELS', '')
    allowed_models = [
        item.strip()
        for item in str(allowed_models_raw).split(',')
        if item.strip()
    ]

    responses_raw = current_app.config.get('OLLAMA_LINUX_TEST_DOUBLE_RESPONSES', '')
    linux_test_double_responses: dict[str, str] = {}
    for pair in str(responses_raw).split(';'):
        pair = pair.strip()
        if '=' not in pair:
            continue
        key, value = pair.split('=', 1)
        key = key.strip()
        value = value.strip()
        if key:
            linux_test_double_responses[key] = value

    runtime_config = {
        'adapter': current_app.config.get('OLLAMA_ADAPTER', 'linux_test_double'),
        'endpoint': current_app.config.get('OLLAMA_ENDPOINT', 'http://localhost:11434/api/generate'),
        'model': model_override or current_app.config.get('OLLAMA_DEFAULT_MODEL', 'llama3.2'),
        'allowed_models': allowed_models,
        'linux_test_double_responses': linux_test_double_responses,
        'timeout_seconds': int(current_app.config.get('OLLAMA_TIMEOUT_SECONDS', 8)),
        'prompt_max_chars': int(current_app.config.get('OLLAMA_PROMPT_MAX_CHARS', 4000)),
        'response_max_chars': int(current_app.config.get('OLLAMA_RESPONSE_MAX_CHARS', 4000)),
        'max_evidence_points': int(current_app.config.get('AI_ROOT_CAUSE_MAX_EVIDENCE_POINTS', 8)),
    }

    result, error = AIService.analyze_root_cause(
        symptom_summary,
        evidence_points=evidence_points,
        runtime_config=runtime_config,
    )
    if error:
        log_audit_event('ai.root_cause.analyze', outcome='failure', reason=error, model=runtime_config['model'])
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

    allowed_models_raw = current_app.config.get('OLLAMA_ALLOWED_MODELS', '')
    allowed_models = [
        item.strip()
        for item in str(allowed_models_raw).split(',')
        if item.strip()
    ]

    responses_raw = current_app.config.get('OLLAMA_LINUX_TEST_DOUBLE_RESPONSES', '')
    linux_test_double_responses: dict[str, str] = {}
    for pair in str(responses_raw).split(';'):
        pair = pair.strip()
        if '=' not in pair:
            continue
        key, value = pair.split('=', 1)
        key = key.strip()
        value = value.strip()
        if key:
            linux_test_double_responses[key] = value

    runtime_config = {
        'adapter': current_app.config.get('OLLAMA_ADAPTER', 'linux_test_double'),
        'endpoint': current_app.config.get('OLLAMA_ENDPOINT', 'http://localhost:11434/api/generate'),
        'model': model_override or current_app.config.get('OLLAMA_DEFAULT_MODEL', 'llama3.2'),
        'allowed_models': allowed_models,
        'linux_test_double_responses': linux_test_double_responses,
        'timeout_seconds': int(current_app.config.get('OLLAMA_TIMEOUT_SECONDS', 8)),
        'prompt_max_chars': int(current_app.config.get('OLLAMA_PROMPT_MAX_CHARS', 4000)),
        'response_max_chars': int(current_app.config.get('OLLAMA_RESPONSE_MAX_CHARS', 4000)),
        'max_evidence_points': int(current_app.config.get('AI_ROOT_CAUSE_MAX_EVIDENCE_POINTS', 8)),
        'max_recommendations': int(current_app.config.get('AI_RECOMMENDATION_MAX_ITEMS', 3)),
    }

    result, error = AIService.generate_recommendations(
        symptom_summary,
        probable_cause,
        evidence_points=evidence_points,
        runtime_config=runtime_config,
    )
    if error:
        log_audit_event('ai.recommendations.generate', outcome='failure', reason=error, model=runtime_config['model'])
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

    allowed_models_raw = current_app.config.get('OLLAMA_ALLOWED_MODELS', '')
    allowed_models = [
        item.strip()
        for item in str(allowed_models_raw).split(',')
        if item.strip()
    ]

    responses_raw = current_app.config.get('OLLAMA_LINUX_TEST_DOUBLE_RESPONSES', '')
    linux_test_double_responses: dict[str, str] = {}
    for pair in str(responses_raw).split(';'):
        pair = pair.strip()
        if '=' not in pair:
            continue
        key, value = pair.split('=', 1)
        key = key.strip()
        value = value.strip()
        if key:
            linux_test_double_responses[key] = value

    runtime_config = {
        'adapter': current_app.config.get('OLLAMA_ADAPTER', 'linux_test_double'),
        'endpoint': current_app.config.get('OLLAMA_ENDPOINT', 'http://localhost:11434/api/generate'),
        'model': model_override or current_app.config.get('OLLAMA_DEFAULT_MODEL', 'llama3.2'),
        'allowed_models': allowed_models,
        'linux_test_double_responses': linux_test_double_responses,
        'timeout_seconds': int(current_app.config.get('OLLAMA_TIMEOUT_SECONDS', 8)),
        'prompt_max_chars': int(current_app.config.get('OLLAMA_PROMPT_MAX_CHARS', 4000)),
        'response_max_chars': int(current_app.config.get('OLLAMA_RESPONSE_MAX_CHARS', 4000)),
        'max_context_items': int(current_app.config.get('AI_TROUBLESHOOT_MAX_CONTEXT_ITEMS', 10)),
        'max_steps': int(current_app.config.get('AI_TROUBLESHOOT_MAX_STEPS', 5)),
        'max_question_chars': int(current_app.config.get('AI_TROUBLESHOOT_MAX_QUESTION_CHARS', 1200)),
    }

    result, error = AIService.assist_troubleshooting(
        question,
        context_items=context_items,
        runtime_config=runtime_config,
    )
    if error:
        log_audit_event('ai.troubleshooting.assist', outcome='failure', reason=error, model=runtime_config['model'])
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

    allowed_models_raw = current_app.config.get('OLLAMA_ALLOWED_MODELS', '')
    allowed_models = [
        item.strip()
        for item in str(allowed_models_raw).split(',')
        if item.strip()
    ]

    responses_raw = current_app.config.get('OLLAMA_LINUX_TEST_DOUBLE_RESPONSES', '')
    linux_test_double_responses: dict[str, str] = {}
    for pair in str(responses_raw).split(';'):
        pair = pair.strip()
        if '=' not in pair:
            continue
        key, value = pair.split('=', 1)
        key = key.strip()
        value = value.strip()
        if key:
            linux_test_double_responses[key] = value

    runtime_config = {
        'adapter': current_app.config.get('OLLAMA_ADAPTER', 'linux_test_double'),
        'endpoint': current_app.config.get('OLLAMA_ENDPOINT', 'http://localhost:11434/api/generate'),
        'model': model_override or current_app.config.get('OLLAMA_DEFAULT_MODEL', 'llama3.2'),
        'allowed_models': allowed_models,
        'linux_test_double_responses': linux_test_double_responses,
        'timeout_seconds': int(current_app.config.get('OLLAMA_TIMEOUT_SECONDS', 8)),
        'prompt_max_chars': int(current_app.config.get('OLLAMA_PROMPT_MAX_CHARS', 4000)),
        'response_max_chars': int(current_app.config.get('OLLAMA_RESPONSE_MAX_CHARS', 4000)),
        'max_tags': int(current_app.config.get('AI_LEARNING_MAX_TAGS', 8)),
    }

    result, error = AIService.learn_from_resolution(
        issue_summary,
        resolution_summary,
        outcome=outcome,
        tags=tags,
        runtime_config=runtime_config,
    )
    if error:
        log_audit_event('ai.learning.feedback', outcome='failure', reason=error, model=runtime_config['model'])
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
    )
    return jsonify({'status': 'success', 'learning_feedback': result}), 200


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

    log_audit_event(
        'ai.confidence.score',
        outcome='success',
        host_name=host_name,
        adapter=result.get('adapter'),
        confidence_score=result.get('confidence_score'),
        risk_factor_count=len(result.get('risk_factors', [])),
    )
    return jsonify({'status': 'success', 'confidence': result}), 200


@api_bp.route('/dashboard/status', methods=['GET'])
@limiter.limit("240 per hour")
@require_api_key_or_permission('automation.manage')
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

    allowed_models_raw = current_app.config.get('OLLAMA_ALLOWED_MODELS', '')
    allowed_models = [
        item.strip()
        for item in str(allowed_models_raw).split(',')
        if item.strip()
    ]

    responses_raw = current_app.config.get('OLLAMA_LINUX_TEST_DOUBLE_RESPONSES', '')
    linux_test_double_responses: dict[str, str] = {}
    for pair in str(responses_raw).split(';'):
        pair = pair.strip()
        if '=' not in pair:
            continue
        key, value = pair.split('=', 1)
        key = key.strip()
        if not key:
            continue
        linux_test_double_responses[key] = value

    runtime_config = {
        'adapter': current_app.config.get('OLLAMA_ADAPTER', 'linux_test_double'),
        'endpoint': current_app.config.get('OLLAMA_ENDPOINT', 'http://localhost:11434/api/generate'),
        'model': model_override or current_app.config.get('OLLAMA_DEFAULT_MODEL', 'llama3.2'),
        'allowed_models': allowed_models,
        'timeout_seconds': int(current_app.config.get('OLLAMA_TIMEOUT_SECONDS', 8)),
        'prompt_max_chars': int(current_app.config.get('OLLAMA_PROMPT_MAX_CHARS', 4000)),
        'response_max_chars': int(current_app.config.get('OLLAMA_RESPONSE_MAX_CHARS', 4000)),
        'linux_test_double_responses': linux_test_double_responses,
        'ai_anomaly_max_items': 10,
    }

    result, error = AIService.analyze_anomalies(anomalies, runtime_config=runtime_config)
    if error:
        log_audit_event('ai.anomaly.analyze', outcome='failure', reason=error)
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

    allowed_models_raw = current_app.config.get('OLLAMA_ALLOWED_MODELS', '')
    allowed_models = [item.strip() for item in str(allowed_models_raw).split(',') if item.strip()]

    responses_raw = current_app.config.get('OLLAMA_LINUX_TEST_DOUBLE_RESPONSES', '')
    linux_test_double_responses: dict[str, str] = {}
    for pair in str(responses_raw).split(';'):
        pair = pair.strip()
        if '=' not in pair:
            continue
        key, value = pair.split('=', 1)
        key = key.strip()
        if not key:
            continue
        linux_test_double_responses[key] = value

    runtime_config = {
        'adapter': current_app.config.get('OLLAMA_ADAPTER', 'linux_test_double'),
        'endpoint': current_app.config.get('OLLAMA_ENDPOINT', 'http://localhost:11434/api/generate'),
        'model': model_override or current_app.config.get('OLLAMA_DEFAULT_MODEL', 'llama3.2'),
        'allowed_models': allowed_models,
        'timeout_seconds': int(current_app.config.get('OLLAMA_TIMEOUT_SECONDS', 8)),
        'prompt_max_chars': int(current_app.config.get('OLLAMA_PROMPT_MAX_CHARS', 4000)),
        'response_max_chars': int(current_app.config.get('OLLAMA_RESPONSE_MAX_CHARS', 4000)),
        'linux_test_double_responses': linux_test_double_responses,
    }

    result, error = AIService.explain_incident(
        incident_title=incident_title,
        affected_systems=affected_systems,
        metrics_snapshot=metrics_snapshot,
        runtime_config=runtime_config,
    )
    if error:
        log_audit_event('ai.incident.explain', outcome='failure', reason=error)
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

