"""
API Blueprint
REST API endpoints for agent data submission and system management
"""

import logging
from flask import Blueprint, request, jsonify, g
from sqlalchemy import text
from ..extensions import limiter
from ..auth import require_api_key
from ..schemas import validate_and_clean_system_data
from ..models import db, SystemData
from marshmallow import ValidationError

logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__, url_prefix='/api')


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
@require_api_key
def status():
    """
    Get API status.
    
    Returns:
        - 200: API is operational
    """
    return jsonify({
        'status': 'operational',
        'message': 'API is running',
        'version': '1.0.0'
    }), 200


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
