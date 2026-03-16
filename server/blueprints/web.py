"""
Web Blueprint
Web UI routes for dashboard and management
"""

import logging
from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from ..models import db, SystemData
from ..extensions import limiter
from ..services import SystemService

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
        systems = SystemData.query.order_by(SystemData.last_update.desc()).limit(10).all()
        
        # Calculate dashboard stats
        total_systems = SystemData.query.count()
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
        systems = SystemData.query.all()
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
        systems = SystemData.query.all()
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
        systems = SystemData.query.order_by(SystemData.last_update.desc()).all()
        
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
        systems = SystemData.query.all()
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
        system = SystemData.query.get(system_id)
        
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
