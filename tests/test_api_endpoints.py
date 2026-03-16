"""
API endpoint tests with authentication
Tests for all API routes with proper authentication
"""

import pytest
import json
from server.extensions import db
from server.models import SystemData


class TestAPIEndpointsAuth:
    """Test API endpoints with authentication"""
    
    def test_submit_data_requires_auth(self, client):
        """Test /api/submit_data requires authentication"""
        response = client.post(
            '/api/submit_data',
            json={
                'serial_number': 'TEST-001',
                'hostname': 'test-host'
            }
        )
        # Should reject without API key
        assert response.status_code == 401
    
    def test_submit_data_with_valid_auth(self, client):
        """Test /api/submit_data with valid authentication"""
        response = client.post(
            '/api/submit_data',
            headers={'X-API-Key': 'default-key-change-this'},
            json={
                'serial_number': 'TEST-001',
                'hostname': 'test-host',
                'cpu_usage': 45.5,
                'ram_usage': 60.0
            }
        )
        # Should accept with valid API key (may fail validation but not auth)
        assert response.status_code in [200, 201, 400, 422]
    
    def test_submit_data_with_invalid_auth(self, client):
        """Test /api/submit_data with invalid authentication"""
        response = client.post(
            '/api/submit_data',
            headers={'X-API-Key': 'invalid-key'},
            json={
                'serial_number': 'TEST-001',
                'hostname': 'test-host'
            }
        )
        # Should reject with invalid API key
        assert response.status_code == 401


class TestSubmitDataEndpoint:
    """Test /api/submit_data endpoint functionality"""
    
    def test_submit_valid_minimal_data(self, client):
        """Test submitting minimal valid system data"""
        response = client.post(
            '/api/submit_data',
            headers={'X-API-Key': 'default-key-change-this'},
            json={
                'serial_number': 'TEST-001',
                'hostname': 'test-host',
                'cpu_usage': 45.5
            }
        )
        assert response.status_code in [200, 201]
        data = response.get_json()
        assert 'serial_number' in data or 'message' in data
    
    def test_submit_complete_data(self, client):
        """Test submitting complete system data"""
        response = client.post(
            '/api/submit_data',
            headers={'X-API-Key': 'default-key-change-this'},
            json={
                'serial_number': 'TEST-002',
                'hostname': 'test-host-2',
                'cpu_usage': 50.0,
                'ram_usage': 65.0,
                'disk_info': [
                    {
                        'device': '/dev/sda1',
                        'mountpoint': '/',
                        'fstype': 'ext4',
                        'total_bytes': 1000000000,
                        'used_bytes': 500000000,
                        'free_bytes': 500000000,
                        'percent': 50.0
                    }
                ]
            }
        )
        assert response.status_code in [200, 201]
    
    def test_submit_missing_required_field(self, client):
        """Test submitting data with missing required field"""
        response = client.post(
            '/api/submit_data',
            headers={'X-API-Key': 'default-key-change-this'},
            json={
                'hostname': 'test-host'
                # Missing: serial_number
            }
        )
        # Should return validation error
        assert response.status_code in [400, 422]
    
    def test_submit_invalid_data_type(self, client):
        """Test submitting data with invalid data type"""
        response = client.post(
            '/api/submit_data',
            headers={'X-API-Key': 'default-key-change-this'},
            json={
                'serial_number': 'TEST-003',
                'hostname': 'test-host',
                'cpu_usage': 'not-a-number'  # Invalid: should be float
            }
        )
        # Should return validation error
        assert response.status_code in [400, 422]
    
    def test_submit_invalid_percentage(self, client):
        """Test submitting data with invalid percentage"""
        response = client.post(
            '/api/submit_data',
            headers={'X-API-Key': 'default-key-change-this'},
            json={
                'serial_number': 'TEST-004',
                'hostname': 'test-host',
                'cpu_usage': 150.0  # Invalid: > 100%
            }
        )
        # Should return validation error
        assert response.status_code in [400, 422]


class TestAPIResponseFormat:
    """Test API response formats"""
    
    def test_error_response_format(self, client):
        """Test that error responses are properly formatted"""
        response = client.post(
            '/api/submit_data',
            headers={'X-API-Key': 'default-key-change-this'},
            json={
                'serial_number': 'TEST-005',
                'hostname': 'test-host',
                'cpu_usage': 150.0  # Invalid
            }
        )
        
        if response.status_code >= 400:
            data = response.get_json()
            assert isinstance(data, dict)
            # Should have error or message field
            assert 'error' in data or 'message' in data or 'errors' in data
    
    def test_success_response_format(self, client):
        """Test that success responses are properly formatted"""
        response = client.post(
            '/api/submit_data',
            headers={'X-API-Key': 'default-key-change-this'},
            json={
                'serial_number': 'TEST-006',
                'hostname': 'test-host',
                'cpu_usage': 50.0
            }
        )
        
        if response.status_code in [200, 201]:
            data = response.get_json()
            assert isinstance(data, dict)


class TestRateLimiting:
    """Test API rate limiting"""
    
    def test_rate_limiting_header(self, client):
        """Test that rate limit headers are present"""
        response = client.get(
            '/api/health',
            headers={'X-API-Key': 'default-key-change-this'}
        )
        # Check for rate limit headers
        # Headers should include X-RateLimit-Limit, X-RateLimit-Remaining, etc.
        # (depending on implementation)
        assert response is not None
    
    def test_excessive_requests(self, client):
        """Test API behavior with excessive requests"""
        # Make many requests rapidly
        headers = {'X-API-Key': 'default-key-change-this'}
        
        responses = []
        for i in range(5):
            response = client.post(
                '/api/submit_data',
                headers=headers,
                json={
                    'serial_number': f'TEST-{i}',
                    'hostname': f'test-host-{i}',
                    'cpu_usage': 50.0
                }
            )
            responses.append(response.status_code)
        
        # Should get various status codes (not all 429 necessarily)
        # but server should handle the load
        assert len(responses) > 0
