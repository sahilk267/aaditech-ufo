# server/auth.py
"""
API Authentication Module
Handles API key validation for secure endpoint access
"""

from functools import wraps
from flask import request, jsonify
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

AGENT_API_KEY = os.getenv('AGENT_API_KEY', 'default-api-key-change-me')


def require_api_key(f):
    """
    Decorator to require API key authentication on endpoints.
    
    Usage:
        @app.route('/api/submit_data', methods=['POST'])
        @require_api_key
        def submit_data():
            # Your code here
            pass
    
    Client must send:
        Headers: {'X-API-Key': 'your-api-key'}
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        
        if not api_key:
            return jsonify({
                'error': 'API key required',
                'message': 'Please provide X-API-Key in request headers'
            }), 401
        
        if api_key != AGENT_API_KEY:
            return jsonify({
                'error': 'Invalid API key',
                'message': 'The provided API key is invalid'
            }), 403
        
        return f(*args, **kwargs)
    
    return decorated_function


def get_api_key():
    """Get the current API key from environment"""
    return AGENT_API_KEY


def validate_api_key(key):
    """
    Validate an API key.
    
    Args:
        key: API key to validate
    
    Returns:
        True if valid, False otherwise
    """
    return key == AGENT_API_KEY
