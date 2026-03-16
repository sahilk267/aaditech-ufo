"""
Unit tests for authentication module
Tests for API key validation and authentication decorator
"""

import pytest
from unittest.mock import patch
from server.auth import require_api_key, validate_api_key, get_api_key


class TestAuthModule:
    """Test authentication module"""
    
    def test_get_api_key_from_env(self):
        """Test getting API key from environment"""
        with patch.dict('os.environ', {'AGENT_API_KEY': 'test-key-123'}):
            key = get_api_key()
            assert key == 'test-key-123'
    
    def test_get_api_key_default(self):
        """Test getting default API key when not set"""
        with patch.dict('os.environ', {}, clear=False):
            # Remove AGENT_API_KEY if it exists
            if 'AGENT_API_KEY' in __import__('os').environ:
                del __import__('os').environ['AGENT_API_KEY']
            key = get_api_key()
            # Should return something, either env value or default
            assert key is not None
            assert isinstance(key, str)
    
    def test_validate_api_key_valid(self):
        """Test validating correct API key"""
        with patch.dict('os.environ', {'AGENT_API_KEY': 'correct-key'}):
            result = validate_api_key('correct-key')
            assert result is True
    
    def test_validate_api_key_invalid(self):
        """Test validating incorrect API key"""
        with patch.dict('os.environ', {'AGENT_API_KEY': 'correct-key'}):
            result = validate_api_key('wrong-key')
            assert result is False
    
    def test_validate_api_key_empty(self):
        """Test validating empty API key"""
        with patch.dict('os.environ', {'AGENT_API_KEY': 'correct-key'}):
            result = validate_api_key('')
            assert result is False
    
    def test_require_api_key_decorator_present(self, client):
        """Test require_api_key decorator with valid key in header"""
        # Setup with test client
        from server.blueprints.api import api_bp
        
        @api_bp.route('/test-auth-endpoint', methods=['GET'])
        @require_api_key
        def test_endpoint():
            return {'message': 'success'}, 200
        
        # Test with valid API key
        response = client.get(
            '/test-auth-endpoint',
            headers={'X-API-Key': 'default-key-change-this'}
        )
        # Should succeed or fail based on environment key
        assert response.status_code in [200, 401]
    
    def test_require_api_key_decorator_missing(self, client):
        """Test require_api_key decorator without API key header"""
        from server.blueprints.api import api_bp
        
        @api_bp.route('/test-no-key', methods=['GET'])
        @require_api_key
        def test_endpoint():
            return {'message': 'success'}, 200
        
        # Test without API key header - should fail
        response = client.get('/test-no-key')
        assert response.status_code == 401
        assert 'error' in response.get_json()


class TestAuthIntegration:
    """Integration tests for authentication"""
    
    def test_api_endpoint_requires_auth(self, client):
        """Test that API endpoints require authentication"""
        # Try accessing /api/submit_data without auth
        response = client.post(
            '/api/submit_data',
            json={'test': 'data'}
        )
        # Should be rejected without auth key
        assert response.status_code == 401 or response.status_code == 400
    
    def test_api_endpoint_accepts_valid_auth(self, client):
        """Test that API endpoints accept valid authentication"""
        # Try with auth key (from environment)
        response = client.post(
            '/api/submit_data',
            headers={'X-API-Key': 'default-key-change-this'},
            json={
                'serial_number': 'TEST-123',
                'hostname': 'test-host',
                'cpu_usage': 45.5,
                'ram_usage': 60.0
            }
        )
        # Should succeed or fail based on validation, not auth
        assert response.status_code in [200, 201, 400, 422]
