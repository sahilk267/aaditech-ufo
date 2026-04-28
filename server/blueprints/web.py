"""
Web Blueprint
Web UI routes for dashboard and management
"""

import logging
import os
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

from flask import Blueprint, render_template, jsonify, g, request, redirect, url_for, flash, current_app, send_file, abort, send_from_directory, make_response
from werkzeug.utils import secure_filename
from ..auth import (
    clear_web_session,
    hash_password,
    is_user_locked_out,
    record_failed_login,
    require_api_key_or_permission,
    require_web_permission,
    reset_login_state,
    start_web_session,
    verify_password,
)
from ..models import db, SystemData, Organization, User, Role
from ..extensions import limiter
from ..services import SystemService, BackupService, PerformanceService, AgentReleaseService
from ..audit import log_audit_event

logger = logging.getLogger(__name__)

web_bp = Blueprint('web', __name__)


def _should_use_long_lived_asset_cache(path: str) -> bool:
    """Only cache hashed build assets for a year; keep other files short-lived."""
    normalized = str(path or '').strip().lstrip('/')
    if not normalized.startswith('assets/'):
        return False

    filename = Path(normalized).name
    return bool(filename and re.search(r'-[A-Za-z0-9]{6,}\.', filename))


def _get_spa_dist_path() -> Path:
    """Resolve the frontend SPA dist directory path."""
    return Path(__file__).parent.parent.parent / 'frontend' / 'dist'


def _is_safe_redirect_target(target: str) -> bool:
    if not target:
        return False
    host_url = request.host_url
    ref_url = urlparse(host_url)
    test_url = urlparse(urljoin(host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc


def _coerce_backup_rows():
    backups = []
    for backup in BackupService.list_backups():
        backups.append({
            'filename': backup['filename'],
            'timestamp': backup['modified'],
            'size': backup['size_mb'],
        })
    return backups


@web_bp.route('/app')
@web_bp.route('/app/<path:path>')
def spa_shell(path=None):
    """
    Serve the SPA shell and hard-refresh support for /app routing.
    All /app/* routes are handled by the React router on the client side.
    
    This handler:
    - Serves index.html for / and /app routes (SPA shell entry points)
    - Serves static assets (JS, CSS, images) from dist/assets
    - Returns 404 for non-existent static files
    """
    dist_path = _get_spa_dist_path()
    
    if not dist_path.exists():
        logger.warning(f"SPA dist path not found: {dist_path}")
        return jsonify({'error': 'SPA not deployed'}), 503
    
    # Request for specific static asset
    if path and '.' in path.split('/')[-1]:
        try:
            response = make_response(send_from_directory(dist_path, path))
            if _should_use_long_lived_asset_cache(path):
                # Hashed build assets are safe to cache for a year.
                response.cache_control.max_age = 31536000
                response.cache_control.public = True
            else:
                # Non-hashed assets should be refreshable across deploys.
                response.cache_control.no_cache = True
                response.cache_control.no_store = True
            return response
        except Exception as e:
            logger.debug(f"Static asset not found: {path}")
            return jsonify({'error': 'Asset not found'}), 404
    
    # Hard-refresh support: serve index.html for any route to let React Router take over
    index_path = dist_path / 'index.html'
    if index_path.exists():
        response = make_response(send_from_directory(dist_path, 'index.html'))
        # No-cache for index.html to ensure latest shell is served
        response.cache_control.no_cache = True
        response.cache_control.no_store = True
        return response
    
    return jsonify({'error': 'SPA shell not found'}), 503


@web_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("20 per hour")
def login():
    """Browser-compatible login page backed by Flask session cookies."""
    next_url = request.args.get('next', '')
    if getattr(g, 'current_user', None) is not None:
        destination = next_url if _is_safe_redirect_target(next_url) else url_for('web.index')
        return redirect(destination)

    if request.method == 'POST':
        tenant_slug = (request.form.get('tenant_slug') or '').strip().lower()
        email = (request.form.get('email') or '').strip().lower()
        password = (request.form.get('password') or '').strip()
        next_url = request.form.get('next', '')

        if not tenant_slug or not email or not password:
            log_audit_event('web.login', outcome='failure', reason='required_fields_missing', email=email, tenant_slug=tenant_slug)
            flash('Tenant slug, email, and password are required.', 'danger')
            return render_template('login.html', next_url=next_url, tenant_slug=tenant_slug), 400

        tenant = Organization.query.filter_by(slug=tenant_slug, is_active=True).first()
        if tenant is None:
            log_audit_event('web.login', outcome='failure', reason='tenant_not_found', email=email, tenant_slug=tenant_slug)
            flash('Tenant not found or inactive.', 'danger')
            return render_template('login.html', next_url=next_url, tenant_slug=tenant_slug), 401

        user = User.query.filter_by(organization_id=tenant.id, email=email).first()
        if user is None or not user.is_active:
            log_audit_event('web.login', outcome='failure', reason='invalid_credentials', email=email, tenant_slug=tenant_slug)
            flash('Invalid credentials.', 'danger')
            return render_template('login.html', next_url=next_url, tenant_slug=tenant_slug), 401

        if is_user_locked_out(user):
            log_audit_event('web.login', outcome='failure', reason='lockout_active', email=email, tenant_slug=tenant_slug, user_id=user.id)
            flash('Account temporarily locked.', 'danger')
            return render_template('login.html', next_url=next_url, tenant_slug=tenant_slug), 401

        if not verify_password(password, user.password_hash):
            record_failed_login(user)
            log_audit_event('web.login', outcome='failure', reason='invalid_credentials', email=email, tenant_slug=tenant_slug)
            flash('Invalid credentials.', 'danger')
            return render_template('login.html', next_url=next_url, tenant_slug=tenant_slug), 401

        reset_login_state(user)
        start_web_session(user)
        log_audit_event('web.login', outcome='success', user_id=user.id, user_email=user.email, tenant_slug=tenant_slug)
        flash('Logged in successfully.', 'success')

        destination = next_url if _is_safe_redirect_target(next_url) else url_for('web.index')
        return redirect(destination)

    return render_template('login.html', next_url=next_url, tenant_slug='')


@web_bp.route('/logout', methods=['GET', 'POST'])
def logout():
    """Clear browser session and redirect to login."""
    log_audit_event('web.logout', outcome='success')
    clear_web_session()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('web.login'))


@web_bp.route('/forbidden', methods=['GET'])
def forbidden_page():
    """Render forbidden page for browser session permission failures."""
    return render_template('forbidden.html'), 403


@web_bp.route('/')
@require_web_permission('dashboard.view')
def index():
    """
    Home page with dashboard.
    
    Conducts Wave 1 redirect if SPA_WAVE_1_ENABLED is true.
    
    Returns:
        Rendered dashboard template or redirect to SPA when wave-1 is active
    """
    # Wave 1 redirect: redirect to SPA if enabled
    if current_app.config.get('SPA_WAVE_1_ENABLED', False):
        return redirect('/app/dashboard', code=302)
    
    try:
        recent_limit = int(current_app.config.get('QUERY_RECENT_SYSTEMS_LIMIT', 10))
        if current_app.config.get('QUERY_OPTIMIZER_ENABLED', True):
            systems = PerformanceService.get_recent_system_rows(g.tenant.id, limit=recent_limit)
            counts = PerformanceService.get_dashboard_counts(g.tenant.id)
            total_systems = counts['total_systems']
            active_systems = counts['active_systems']
        else:
            systems = (
                SystemData.query
                .filter_by(organization_id=g.tenant.id)
                .order_by(SystemData.last_update.desc())
                .limit(recent_limit)
                .all()
            )
            total_systems = SystemData.query.filter_by(organization_id=g.tenant.id).count()
            active_systems = sum(1 for s in systems if SystemService.is_active(s.last_update, SystemService.get_current_time()))
        
        return render_template('base.html', 
                             systems=systems,
                             total_systems=total_systems,
                             active_systems=active_systems)
    
    except Exception as e:
        logger.error(f"Error loading dashboard: {e}")
        return render_template('base.html', error="Failed to load dashboard"), 500


@web_bp.route('/features')
@require_web_permission('dashboard.view')
def features_hub():
    """Feature hub page listing web and API capabilities."""
    web_features = [
        {
            'name': 'Dashboard',
            'path': url_for('web.index'),
            'description': 'Live overview of active systems and recent updates.',
            'permission': 'dashboard.view',
        },
        {
            'name': 'System Detail',
            'path': url_for('web.user'),
            'description': 'Deep dive into CPU, RAM, storage and network metrics.',
            'permission': 'dashboard.view',
        },
        {
            'name': 'History',
            'path': url_for('web.history'),
            'description': 'Historical performance snapshots and trend view.',
            'permission': 'dashboard.view',
        },
        {
            'name': 'Admin',
            'path': url_for('web.admin'),
            'description': 'Tenant administration and system-level management actions.',
            'permission': 'tenant.manage',
        },
        {
            'name': 'Backup',
            'path': url_for('web.backup'),
            'description': 'Create and restore backups for your tenant data.',
            'permission': 'backup.manage',
        },
        {
            'name': 'Agent Releases',
            'path': url_for('web.agent_releases_page'),
            'description': 'Upload and download Windows agent release binaries.',
            'permission': 'dashboard.view',
        },
    ]

    api_feature_groups = [
        {
            'title': 'Auth + Session APIs',
            'items': [
                {'method': 'POST', 'endpoint': '/api/auth/login', 'purpose': 'JWT login for API clients.'},
                {'method': 'POST', 'endpoint': '/api/auth/refresh', 'purpose': 'Refresh JWT access token.'},
                {'method': 'POST', 'endpoint': '/api/auth/logout', 'purpose': 'Revoke JWT tokens.'},
            ],
        },
        {
            'title': 'System Data + Dashboard APIs',
            'items': [
                {'method': 'POST', 'endpoint': '/api/submit_data', 'purpose': 'Agent uploads benchmark payload.'},
                {'method': 'GET', 'endpoint': '/api/get_data', 'purpose': 'List tenant systems.'},
                {'method': 'POST', 'endpoint': '/manual_submit', 'purpose': 'Manual local benchmark submit.'},
            ],
        },
        {
            'title': 'Operations APIs',
            'items': [
                {'method': 'POST', 'endpoint': '/api/automation/run', 'purpose': 'Run automation workflow.'},
                {'method': 'POST', 'endpoint': '/api/alerts/evaluate', 'purpose': 'Evaluate alert rules.'},
                {'method': 'POST', 'endpoint': '/api/backup/create', 'purpose': 'Trigger backup creation.'},
            ],
        },
        {
            'title': 'Agent Release Lifecycle APIs',
            'items': [
                {'method': 'GET', 'endpoint': '/api/agent/releases', 'purpose': 'List release binaries.'},
                {'method': 'POST', 'endpoint': '/api/agent/releases/upload', 'purpose': 'Upload release artifact.'},
                {'method': 'GET', 'endpoint': '/api/agent/releases/guide?current_version=x.y.z', 'purpose': 'Get upgrade/downgrade recommendation.'},
            ],
        },
    ]

    users = User.query.filter_by(organization_id=g.tenant.id).all()
    roles = Role.query.filter_by(organization_id=g.tenant.id).all()
    try:
        releases = AgentReleaseService.list_releases(current_app.config, current_app.instance_path)
    except Exception:
        releases = []

    dist_binary = os.path.join(
        current_app.root_path, '..', 'agent', 'dist', 'aaditech-agent'
    )
    agent_built = os.path.exists(os.path.realpath(dist_binary))

    return render_template(
        'features.html',
        web_features=web_features,
        api_feature_groups=api_feature_groups,
        users=users,
        roles=roles,
        releases=releases,
        agent_built=agent_built,
    )


@web_bp.route('/features/create-user', methods=['POST'])
@limiter.limit("20 per hour")
@require_web_permission('tenant.manage')
def features_create_user():
    """Create a new user for the current tenant from the control panel."""
    full_name = (request.form.get('full_name') or '').strip()
    email = (request.form.get('email') or '').strip().lower()
    password = (request.form.get('password') or '').strip()
    role_id = (request.form.get('role_id') or '').strip()

    if not full_name or not email or not password:
        flash('Full name, email, and password are all required.', 'danger')
        return redirect(url_for('web.features_hub') + '#tab-users')

    if len(password) < 8:
        flash('Password must be at least 8 characters.', 'danger')
        return redirect(url_for('web.features_hub') + '#tab-users')

    existing = User.query.filter_by(organization_id=g.tenant.id, email=email).first()
    if existing:
        flash(f'A user with email {email} already exists.', 'danger')
        return redirect(url_for('web.features_hub') + '#tab-users')

    new_user = User(
        organization_id=g.tenant.id,
        email=email,
        full_name=full_name,
        password_hash=hash_password(password),
        is_active=True,
    )
    if role_id:
        role = Role.query.filter_by(id=int(role_id), organization_id=g.tenant.id).first()
        if role:
            new_user.roles.append(role)

    db.session.add(new_user)
    db.session.commit()
    log_audit_event('user.create', outcome='success', email=email, created_by=g.current_user.id)
    flash(f'User {email} created successfully!', 'success')
    return redirect(url_for('web.features_hub') + '#tab-users')


@web_bp.route('/features/build-agent', methods=['POST'])
@limiter.limit("5 per hour")
@require_web_permission('tenant.manage')
def features_build_agent():
    """Trigger a PyInstaller build of the agent binary inside the container."""
    import subprocess

    spec_path = os.path.realpath(
        os.path.join(current_app.root_path, '..', 'agent', 'build.spec')
    )
    dist_path = os.path.realpath(
        os.path.join(current_app.root_path, '..', 'agent', 'dist')
    )
    work_path = os.path.realpath(
        os.path.join(current_app.root_path, '..', 'agent', 'build')
    )

    if not os.path.exists(spec_path):
        flash('Build spec (agent/build.spec) not found on server.', 'danger')
        return redirect(url_for('web.features_hub') + '#tab-agent')

    try:
        result = subprocess.run(
            ['pyinstaller', '--distpath', dist_path, '--workpath', work_path,
             '--noconfirm', spec_path],
            capture_output=True, text=True, timeout=180,
        )
        if result.returncode == 0:
            log_audit_event('agent.build', outcome='success', built_by=g.current_user.id)
            flash('Agent built successfully! Use the Download button below.', 'success')
        else:
            err_tail = (result.stderr or result.stdout or '')[-800:]
            log_audit_event('agent.build', outcome='failure', error=err_tail[:200])
            flash(f'Build failed. PyInstaller output: {err_tail}', 'danger')
    except FileNotFoundError:
        flash('PyInstaller not installed in this environment. '
              'Add pyinstaller to requirements.txt and rebuild the container.', 'warning')
    except subprocess.TimeoutExpired:
        flash('Build timed out after 180 seconds.', 'danger')
    except Exception as exc:
        logger.error('Agent build error: %s', exc, exc_info=True)
        flash('Build failed due to an unexpected server error.', 'danger')

    return redirect(url_for('web.features_hub') + '#tab-agent')


@web_bp.route('/features/download-built-agent')
@limiter.limit("30 per hour")
@require_web_permission('dashboard.view')
def features_download_built_agent():
    """Download the most recently compiled agent binary."""
    binary_path = AgentReleaseService.resolve_built_binary_path(current_app.root_path)
    if not binary_path.exists() or not binary_path.is_file():
        flash('No built binary found. Build the agent first.', 'warning')
        return redirect(url_for('web.features_hub') + '#tab-agent')

    log_audit_event('agent.build.download', outcome='success', downloaded_by=g.current_user.id)
    return send_file(binary_path, as_attachment=True, download_name=binary_path.name)


@web_bp.route('/user')
@web_bp.route('/user/<serial_number>')
@limiter.limit("30 per minute")
@require_web_permission('dashboard.view')
def user(serial_number=None):
    """
    User page - view user-specific system data.
    
    Conducts Wave 1 redirect if SPA_WAVE_1_ENABLED is true.
    
    Returns:
        Rendered user template or redirect to SPA when wave-1 is active
    """
    # Wave 1 redirect: redirect to SPA if enabled
    if current_app.config.get('SPA_WAVE_1_ENABLED', False):
        if serial_number:
            return redirect(f'/app/systems?serial={serial_number}', code=302)
        return redirect('/app/systems', code=302)
    
    try:
        query = SystemData.query.filter_by(organization_id=g.tenant.id)
        if serial_number:
            system = query.filter_by(serial_number=serial_number).first()
        else:
            system = query.order_by(SystemData.last_update.desc()).first()

        return render_template('user.html', system_data=system)
    
    except Exception as e:
        logger.error(f"Error loading user page: {e}")
        return render_template('user.html', error="Failed to load user data"), 500


@web_bp.route('/admin')
@limiter.limit("30 per minute")
@require_web_permission('tenant.manage')
def admin():
    """
    Admin page - manage systems and configurations.
    
    Returns:
        Rendered admin template
    """
    try:
        systems = SystemData.query.filter_by(organization_id=g.tenant.id).all()
        stats = {
            'total_systems': len(systems),
            'active_systems': sum(1 for s in systems if SystemService.is_active(s.last_update, SystemService.get_current_time())),
            'total_backups': 0  # Will be populated with backup service
        }
        
        return render_template('admin.html', 
                             system_data=systems,
                             stats=stats,
                             now=SystemService.get_current_time())
    
    except Exception as e:
        logger.error(f"Error loading admin page: {e}")
        return render_template('admin.html', error="Failed to load admin panel"), 500


@web_bp.route('/history')
@limiter.limit("30 per minute")
@require_web_permission('dashboard.view')
def history():
    """
    History page - reliability history and trends.
    
    Conducts Wave 1 redirect if SPA_WAVE_1_ENABLED is true.
    """
    # Wave 1 redirect: redirect to SPA if enabled
    if current_app.config.get('SPA_WAVE_1_ENABLED', False):
        return redirect('/app/history', code=302)
    
    """
    System history page - view historical data and trends.
    
    Returns:
        Rendered history template
    """
    try:
        # Get all systems with historical data
        systems = (
            SystemData.query
            .filter_by(organization_id=g.tenant.id)
            .order_by(SystemData.last_update.desc())
            .all()
        )
        
        return render_template(
            'user_history.html',
            system_data=systems,
            now=SystemService.get_current_time()
        )
    
    except Exception as e:
        logger.error(f"Error loading history page: {e}")
        return render_template('user_history.html', error="Failed to load history"), 500


@web_bp.route('/backup')
@limiter.limit("30 per minute")
@require_web_permission('backup.manage')
def backup():
    """
    Backup page - backup management console.
    
    Conducts Wave 1 redirect if SPA_WAVE_1_ENABLED is true.
    """
    # Wave 1 redirect: redirect to SPA if enabled
    if current_app.config.get('SPA_WAVE_1_ENABLED', False):
        return redirect('/app/backup', code=302)
    
    """
    Backup management page.
    
    Returns:
        Rendered backup template
    """
    try:
        return render_template('backup.html', backups=_coerce_backup_rows())
    
    except Exception as e:
        logger.error(f"Error loading backup page: {e}")
        return render_template('backup.html', error="Failed to load backup page"), 500


@web_bp.route('/agent/releases', methods=['GET'])
@limiter.limit("60 per minute")
@require_web_permission('dashboard.view')
def agent_releases_page():
    """Render agent release portal page with version-wise exe downloads."""
    try:
        releases = AgentReleaseService.list_releases(current_app.config, current_app.instance_path)
        return render_template('agent_releases.html', releases=releases)
    except Exception as exc:
        logger.error("Error loading agent release portal: %s", exc, exc_info=True)
        return render_template('agent_releases.html', releases=[], error='Failed to load agent releases'), 500


@web_bp.route('/agent/releases/upload', methods=['POST'])
@limiter.limit("30 per hour")
@require_web_permission('tenant.manage')
def upload_agent_release():
    """Upload a new versioned agent exe to server-side release storage."""
    release_file = request.files.get('release_file')
    version = str(request.form.get('version') or '').strip()

    if release_file is None:
        flash('Release file is required.', 'danger')
        return redirect(url_for('web.agent_releases_page'))

    max_mb = int(current_app.config.get('AGENT_RELEASE_MAX_MB', 256))
    max_bytes = max_mb * 1024 * 1024
    if request.content_length and request.content_length > max_bytes:
        flash(f'File is too large. Max allowed size is {max_mb} MB.', 'danger')
        return redirect(url_for('web.agent_releases_page'))

    try:
        release = AgentReleaseService.save_uploaded_release(
            release_file,
            version,
            current_app.config,
            current_app.instance_path,
        )
    except ValueError as exc:
        flash(f'Upload failed: {str(exc)}', 'danger')
        log_audit_event('agent.release.upload', outcome='failure', reason=str(exc), version=version)
        return redirect(url_for('web.agent_releases_page'))
    except Exception as exc:
        flash('Upload failed due to server error.', 'danger')
        log_audit_event('agent.release.upload', outcome='failure', reason='server_error', error=str(exc), version=version)
        return redirect(url_for('web.agent_releases_page'))

    log_audit_event(
        'agent.release.upload',
        outcome='success',
        version=release.version,
        filename=release.filename,
        size_bytes=release.size_bytes,
    )
    flash(f'Agent release uploaded: {release.filename}', 'success')
    return redirect(url_for('web.agent_releases_page'))


@web_bp.route('/agent/releases/download/<path:filename>', methods=['GET'])
@limiter.limit("240 per hour")
@require_web_permission('dashboard.view')
def download_agent_release(filename):
    """Download versioned agent exe from release portal."""
    file_path = AgentReleaseService.resolve_download_path(filename, current_app.config, current_app.instance_path)
    if file_path is None:
        log_audit_event('agent.release.download', outcome='failure', reason='not_found', filename=filename)
        abort(404)

    log_audit_event('agent.release.download', outcome='success', filename=file_path.name)
    return send_file(file_path, as_attachment=True, download_name=file_path.name)


@web_bp.route('/api/systems', methods=['GET'])
@limiter.limit("60 per minute")
@require_api_key_or_permission('dashboard.view')
def get_systems():
    """
    Get list of all systems as JSON.
    
    Returns:
        JSON list of systems
    """
    try:
        systems = SystemData.query.filter_by(organization_id=g.tenant.id).all()
        systems_data = [{
            'id': s.id,
            'serial_number': s.serial_number,
            'hostname': s.hostname,
            'last_update': s.last_update.isoformat() if s.last_update else None,
            'status': s.status
        } for s in systems]
        
        return jsonify({
            'success': True,
            'systems': systems_data,
            'count': len(systems_data)
        }), 200
    
    except Exception as e:
        logger.error(f"Error fetching systems: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@web_bp.route('/api/system/<int:system_id>', methods=['GET'])
@limiter.limit("60 per minute")
@require_api_key_or_permission('dashboard.view')
def get_system(system_id):
    """
    Get detailed information for a specific system.
    
    Args:
        system_id: System ID to retrieve
    
    Returns:
        JSON with system details
    """
    try:
        system = SystemData.query.filter_by(
            id=system_id,
            organization_id=g.tenant.id
        ).first()
        
        if not system:
            return jsonify({
                'success': False,
                'error': 'System not found'
            }), 404
        
        return jsonify({
            'success': True,
            'system': {
                'id': system.id,
                'serial_number': system.serial_number,
                'hostname': system.hostname,
                'system_info': system.system_info,
                'performance_metrics': system.performance_metrics,
                'benchmark_results': system.benchmark_results,
                'last_update': system.last_update.isoformat() if system.last_update else None,
                'status': system.status
            }
        }), 200
    
    except Exception as e:
        logger.error(f"Error fetching system {system_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@web_bp.route('/manual_submit', methods=['POST'])
@limiter.limit("30 per minute")
@require_api_key_or_permission('system.submit')
def manual_submit():
    """
    Manually submit or update local system data.
    
    This endpoint collects current system metrics and submits them to the database.
    Useful for immediate data refresh without waiting for agent submission.
    
    Returns:
        - 200: Success with message
        - 500: Server error
    """
    try:
        # Get local system data
        data = SystemService.get_local_system_data()
        
        if not data:
            logger.warning("No system data collected")
            log_audit_event('system.manual_submit', outcome='failure', reason='no_system_data')
            return jsonify({
                'status': 'error',
                'message': 'Failed to collect system data'
            }), 500
        
        # Check if system already exists
        existing_system = SystemData.query.filter_by(
            serial_number=data.get('serial_number'),
            organization_id=g.tenant.id
        ).first()
        
        if existing_system:
            # Update existing record
            for key, value in data.items():
                if hasattr(existing_system, key):
                    setattr(existing_system, key, value)
            db.session.commit()
            logger.info(f"Updated system data: {data.get('hostname')}")
            log_audit_event('system.manual_submit', outcome='success', mode='update', serial_number=data.get('serial_number'))
            return jsonify({
                'status': 'success',
                'message': 'Local system data updated successfully',
                'system_id': existing_system.id
            }), 200
        else:
            # Create new record
            data['organization_id'] = g.tenant.id
            new_system = SystemData(**data)
            db.session.add(new_system)
            db.session.commit()
            logger.info(f"Submitted system data: {data.get('hostname')}")
            log_audit_event('system.manual_submit', outcome='success', mode='create', serial_number=data.get('serial_number'))
            return jsonify({
                'status': 'success',
                'message': 'Local system data submitted successfully',
                'system_id': new_system.id
            }), 200
    
    except Exception as e:
        logger.error(f"Error processing manual submission: {e}", exc_info=True)
        log_audit_event('system.manual_submit', outcome='failure', reason='exception', error=e)
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@web_bp.route('/backup/create', methods=['POST'])
@limiter.limit("5 per minute")
@require_api_key_or_permission('backup.manage')
def create_backup_route():
    """
    Create a database backup.
    
    Returns:
        - 200: Success with backup details
        - 500: Server error
    """
    try:
        # Get database path
        db_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'toolboxgalaxy.db'
        )
        
        result = BackupService.create_backup(db_path)
        
        if result.get('success'):
            logger.info(f"Backup created: {result.get('backup_filename')}")
            log_audit_event('backup.create', outcome='success', backup_filename=result.get('backup_filename'))
            return jsonify({
                'status': 'success',
                'message': f"Backup created: {result.get('backup_filename')}",
                'backup_info': result
            }), 200
        else:
            logger.error(f"Backup creation failed: {result.get('error')}")
            log_audit_event('backup.create', outcome='failure', reason='service_failed', error=result.get('error'))
            return jsonify({
                'status': 'error',
                'message': result.get('error')
            }), 500
    
    except Exception as e:
        logger.error(f"Error creating backup: {e}", exc_info=True)
        log_audit_event('backup.create', outcome='failure', reason='exception', error=e)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@web_bp.route('/backup/restore/<filename>', methods=['POST'])
@limiter.limit("5 per minute")
@require_api_key_or_permission('backup.manage')
def restore_backup_route(filename):
    """
    Restore database from a backup.
    
    Args:
        filename: Backup filename to restore from
    
    Returns:
        - 200: Success with restoration details
        - 404: Backup not found
        - 500: Server error
    """
    try:
        # Secure the filename
        safe_filename = secure_filename(filename)
        
        # Construct backup path
        backup_path = os.path.join(
            BackupService.BACKUP_DIR,
            safe_filename
        )
        
        # Get database path
        db_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'toolboxgalaxy.db'
        )
        
        result = BackupService.restore_backup(backup_path, db_path)
        
        if result.get('success'):
            logger.info(f"Backup restored: {safe_filename}")
            log_audit_event('backup.restore', outcome='success', backup_filename=safe_filename)
            return jsonify({
                'status': 'success',
                'message': 'Database restored successfully',
                'backup_info': result
            }), 200
        else:
            logger.error(f"Backup restoration failed: {result.get('error')}")
            log_audit_event('backup.restore', outcome='failure', reason='service_failed', backup_filename=safe_filename, error=result.get('error'))
            return jsonify({
                'status': 'error',
                'message': result.get('error')
            }), 500 if result.get('error') else 404
    
    except Exception as e:
        logger.error(f"Error restoring backup: {e}", exc_info=True)
        log_audit_event('backup.restore', outcome='failure', reason='exception', backup_filename=filename, error=e)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
