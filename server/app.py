"""
Aaditech UFO - Agent Monitoring System
Main Flask Application
"""

import os
import logging
from dotenv import load_dotenv
from flask import Flask

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

# Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
    'DATABASE_URL',
    'sqlite:///toolboxgalaxy.db'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv(
    'SECRET_KEY',
    'dev-key-change-in-production'
)

# Initialize extensions with app
from .extensions import init_extensions, db, migrate, limiter
init_extensions(app)


# Import and register blueprints
from .blueprints import api_bp, web_bp
app.register_blueprint(api_bp)
app.register_blueprint(web_bp)

# Import models (must be after app initialization)
from .models import SystemData

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
    try:
        db.session.execute('SELECT 1')
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
