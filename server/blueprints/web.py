"""
Web Blueprint
Web UI routes for dashboard and management
"""

import logging
import os
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, g
from werkzeug.utils import secure_filename
from ..models import db, SystemData
from ..extensions import limiter
from ..services import SystemService, BackupService

logger = logging.getLogger(__name__)

web_bp = Blueprint('web', __name__)


@web_bp.route('/')
def index():
    """
    Home page with dashboard.
    
    Returns:
        Rendered dashboard template
    """
    try:
        # Get recent systems
        systems = (
            SystemData.query
            .filter_by(organization_id=g.tenant.id)
            .order_by(SystemData.last_update.desc())
            .limit(10)
            .all()
        )
        
        # Calculate dashboard stats
        total_systems = SystemData.query.filter_by(organization_id=g.tenant.id).count()
        active_systems = sum(1 for s in systems if SystemService.is_active(s.last_update, SystemService.get_current_time()))
        
        return render_template('base.html', 
                             systems=systems,
                             total_systems=total_systems,
                             active_systems=active_systems)
    
    except Exception as e:
        logger.error(f"Error loading dashboard: {e}")
        return render_template('base.html', error="Failed to load dashboard"), 500


@web_bp.route('/user')
@limiter.limit("30 per minute")
def user():
    """
    User page - view user-specific system data.
    
    Returns:
        Rendered user template
    """
    try:
        systems = SystemData.query.filter_by(organization_id=g.tenant.id).all()
        return render_template('user.html', systems=systems)
    
    except Exception as e:
        logger.error(f"Error loading user page: {e}")
        return render_template('user.html', error="Failed to load user data"), 500


@web_bp.route('/admin')
@limiter.limit("30 per minute")
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
                             systems=systems,
                             stats=stats)
    
    except Exception as e:
        logger.error(f"Error loading admin page: {e}")
        return render_template('admin.html', error="Failed to load admin panel"), 500


@web_bp.route('/history')
@limiter.limit("30 per minute")
def history():
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
        
        return render_template('user_history.html', systems=systems)
    
    except Exception as e:
        logger.error(f"Error loading history page: {e}")
        return render_template('user_history.html', error="Failed to load history"), 500


@web_bp.route('/backup')
@limiter.limit("30 per minute")
def backup():
    """
    Backup management page.
    
    Returns:
        Rendered backup template
    """
    try:
        return render_template('backup.html')
    
    except Exception as e:
        logger.error(f"Error loading backup page: {e}")
        return render_template('backup.html', error="Failed to load backup page"), 500


@web_bp.route('/api/systems', methods=['GET'])
@limiter.limit("60 per minute")
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
            return jsonify({
                'status': 'success',
                'message': 'Local system data submitted successfully',
                'system_id': new_system.id
            }), 200
    
    except Exception as e:
        logger.error(f"Error processing manual submission: {e}", exc_info=True)
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@web_bp.route('/backup/create', methods=['POST'])
@limiter.limit("5 per minute")
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
            return jsonify({
                'status': 'success',
                'message': f"Backup created: {result.get('backup_filename')}",
                'backup_info': result
            }), 200
        else:
            logger.error(f"Backup creation failed: {result.get('error')}")
            return jsonify({
                'status': 'error',
                'message': result.get('error')
            }), 500
    
    except Exception as e:
        logger.error(f"Error creating backup: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@web_bp.route('/backup/restore/<filename>', methods=['POST'])
@limiter.limit("5 per minute")
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
            return jsonify({
                'status': 'success',
                'message': 'Database restored successfully',
                'backup_info': result
            }), 200
        else:
            logger.error(f"Backup restoration failed: {result.get('error')}")
            return jsonify({
                'status': 'error',
                'message': result.get('error')
            }), 500 if result.get('error') else 404
    
    except Exception as e:
        logger.error(f"Error restoring backup: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
