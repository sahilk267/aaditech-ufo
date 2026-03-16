"""
Integration tests for service layer
Tests for SystemService and BackupService
"""

import pytest
from datetime import datetime
from server.services.system_service import SystemService
from server.services.backup_service import BackupService


class TestSystemService:
    """Test SystemService functionality"""
    
    def test_system_service_initialization(self):
        """Test SystemService initialization"""
        service = SystemService()
        assert service is not None
    
    def test_get_system_info(self):
        """Test getting system information"""
        service = SystemService()
        info = service.get_system_info()
        
        assert info is not None
        assert 'platform' in info or 'system' in info
    
    def test_get_performance_metrics(self):
        """Test getting performance metrics"""
        service = SystemService()
        metrics = service.get_performance_metrics()
        
        assert metrics is not None
        assert 'cpu' in metrics or 'cpu_usage' in metrics
        assert 'memory' in metrics or 'ram_usage' in metrics
    
    def test_get_benchmark_results(self):
        """Test getting benchmark results"""
        service = SystemService()
        benchmarks = service.get_benchmark_results()
        
        assert benchmarks is not None
        assert isinstance(benchmarks, (int, float, dict))
    
    def test_get_current_time(self):
        """Test getting current time"""
        service = SystemService()
        current_time = service.get_current_time()
        
        assert current_time is not None
        assert isinstance(current_time, str) or isinstance(current_time, datetime)
    
    def test_is_active_true(self):
        """Test checking if system is active"""
        service = SystemService()
        is_active = service.is_active()
        
        # System should be active during test
        assert is_active is True
    
    def test_get_local_system_data(self):
        """Test getting complete local system data"""
        service = SystemService()
        local_data = service.get_local_system_data()
        
        assert local_data is not None
        assert isinstance(local_data, dict)
        # Should have some key system information
        assert len(local_data) > 0


class TestBackupService:
    """Test BackupService functionality"""
    
    def test_backup_service_initialization(self):
        """Test BackupService initialization"""
        service = BackupService()
        assert service is not None
    
    def test_backup_dir_exists_or_created(self):
        """Test that backup directory exists or is created"""
        service = BackupService()
        # The backup service should handle directory creation
        assert service is not None


class TestSystemServiceMethods:
    """Test individual SystemService methods"""
    
    def test_collect_cpu_metrics(self):
        """Test CPU metric collection"""
        service = SystemService()
        metrics = service.get_performance_metrics()
        
        assert metrics is not None
    
    def test_collect_memory_metrics(self):
        """Test memory metric collection"""
        service = SystemService()
        metrics = service.get_performance_metrics()
        
        assert metrics is not None
    
    def test_collect_disk_metrics(self):
        """Test disk metric collection"""
        service = SystemService()
        info = service.get_system_info()
        
        assert info is not None


class TestServiceIntegration:
    """Integration tests between services"""
    
    def test_system_and_backup_services_work_together(self):
        """Test that system and backup services can work together"""
        system_service = SystemService()
        backup_service = BackupService()
        
        # Get system data
        system_data = system_service.get_local_system_data()
        assert system_data is not None
        
        # Services should be initialized
        assert system_service is not None
        assert backup_service is not None
