"""
Aaditech UFO - Agent Monitoring System
Main Flask Application
"""

import os
import logging
import time
import uuid
from dotenv import load_dotenv
from flask import Flask, g
from werkzeug.middleware.proxy_fix import ProxyFix

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Load configuration based on environment
from .config import get_config
app.config.from_object(get_config())

if app.config.get('ENABLE_PROXY_FIX', True):
    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_for=app.config.get('PROXY_FIX_X_FOR', 1),
        x_proto=app.config.get('PROXY_FIX_X_PROTO', 1),
        x_host=app.config.get('PROXY_FIX_X_HOST', 1),
        x_port=app.config.get('PROXY_FIX_X_PORT', 1),
        x_prefix=app.config.get('PROXY_FIX_X_PREFIX', 1),
    )

from .tenant_context import init_tenant_context
init_tenant_context(app)

from .auth import init_auth_context
init_auth_context(app)

from .queue import init_queue
init_queue(app)


@app.before_request
def bind_request_context_headers():
    """Bind gateway-friendly request metadata to request context."""
    from flask import request

    g.request_started_at = time.time()
    g.request_id = request.headers.get('X-Request-ID') or str(uuid.uuid4())


@app.after_request
def apply_gateway_response_headers(response):
    """Add traceability and transformation headers for gateway compatibility."""
    request_id = getattr(g, 'request_id', None)
    if request_id:
        response.headers['X-Request-ID'] = request_id

    started_at = getattr(g, 'request_started_at', None)
    if started_at is not None:
        elapsed_ms = int((time.time() - started_at) * 1000)
        response.headers['X-Response-Time-Ms'] = str(elapsed_ms)

    response.headers['X-API-Gateway-Ready'] = 'true'
    if app.config.get('CDN_ENABLED', False):
        response.headers['X-Static-Asset-Base'] = app.config.get('CDN_STATIC_BASE_URL', '')
    return response

# Initialize extensions with app
from .extensions import init_extensions, db, migrate, limiter
init_extensions(app)

from .services import PerformanceService
PerformanceService.init_cache(app)


# Import and register blueprints
from .blueprints import api_bp, web_bp
app.register_blueprint(api_bp)
app.register_blueprint(web_bp)

# Import models (must be after app initialization)
from .models import SystemData, Organization

# Create database tables on startup
with app.app_context():
    db.create_all()
    logger.info("Database tables initialized")

# Template filters
@app.template_filter('ist_format')
def ist_format(value):
    """Format datetime to IST string"""
    if not value:
        return 'N/A'
    
    from datetime import datetime
    import pytz
    
    ist = pytz.timezone('Asia/Kolkata')
    
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except:
            return 'N/A'
    
    if value.tzinfo is None:
        value = ist.localize(value)
    else:
        value = value.astimezone(ist)
    
    return value.strftime('%d-%m-%Y %I:%M:%S %p')


@app.context_processor
def inject_template_globals():
    """
    Inject global variables and functions into all templates.
    
    Makes the following available in Jinja2 templates:
    - is_active(last_update, now): Check if system is active
    - get_current_time(): Get current time in IST
    """
    from .services import SystemService

    def asset_url(asset_path: str) -> str:
        return PerformanceService.build_static_asset_url(asset_path, app.config)
    
    return {
        'is_active': SystemService.is_active,
        'current_time': SystemService.get_current_time,
        'current_user': getattr(g, 'current_user', None),
        'current_tenant': getattr(g, 'tenant', None),
        'is_authenticated': getattr(g, 'current_user', None) is not None,
        'asset_url': asset_url,
    }

# Error handlers
@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    from flask import jsonify
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def server_error(error):
    """Handle 500 errors"""
    from flask import jsonify
    logger.error(f"Server error: {error}")
    return jsonify({'error': 'Internal server error'}), 500

@app.errorhandler(429)
def ratelimit_handler(e):
    """Handle rate limit errors"""
    from flask import jsonify
    return jsonify({'error': 'Rate limit exceeded', 'message': str(e.description)}), 429

# Health check endpoint
@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    from flask import jsonify
    from sqlalchemy import text
    try:
        db.session.execute(text('SELECT 1'))
        return jsonify({'status': 'healthy', 'database': 'connected'}), 200
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({'status': 'unhealthy', 'database': 'disconnected'}), 503

if __name__ == '__main__':
    app.run(
        host=os.getenv('HOST', '0.0.0.0'),
        port=int(os.getenv('PORT', 5000)),
        debug=os.getenv('FLASK_DEBUG', False)
    )
