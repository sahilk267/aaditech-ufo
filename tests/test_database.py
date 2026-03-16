"""
Database operation tests
Tests for database models and operations
"""

import pytest
from datetime import datetime
from server.extensions import db
from server.models import SystemData


class TestSystemDataModel:
    """Test SystemData model operations"""
    
    def test_create_system_data(self, app_fixture):
        """Test creating a SystemData record"""
        with app_fixture.app_context():
            data = SystemData(
                serial_number='TEST-001',
                hostname='test-host',
                cpu_usage=45.5,
                ram_usage=60.0
            )
            db.session.add(data)
            db.session.commit()
            
            # Verify it was created
            result = SystemData.query.filter_by(serial_number='TEST-001').first()
            assert result is not None
            assert result.hostname == 'test-host'
            assert result.cpu_usage == 45.5
    
    def test_system_data_with_all_fields(self, app_fixture):
        """Test creating SystemData with all fields"""
        with app_fixture.app_context():
            data = SystemData(
                serial_number='TEST-002',
                hostname='test-host-2',
                model_number='Model X',
                ip_address='192.168.1.1',
                local_ip='192.168.1.2',
                public_ip='8.8.8.8',
                cpu_usage=50.0,
                cpu_cores=4,
                cpu_threads=8,
                ram_usage=65.0,
                storage_usage=75.0,
                status='active',
                current_user='admin'
            )
            db.session.add(data)
            db.session.commit()
            
            result = SystemData.query.filter_by(serial_number='TEST-002').first()
            assert result is not None
            assert result.model_number == 'Model X'
            assert result.cpu_cores == 4
            assert result.status == 'active'
    
    def test_system_data_timestamps(self, app_fixture):
        """Test that timestamps are set correctly"""
        with app_fixture.app_context():
            before_time = datetime.utcnow()
            
            data = SystemData(
                serial_number='TEST-003',
                hostname='test-host-3'
            )
            db.session.add(data)
            db.session.commit()
            
            after_time = datetime.utcnow()
            
            result = SystemData.query.filter_by(serial_number='TEST-003').first()
            assert result.created_at is not None
            assert result.updated_at is not None
            assert before_time <= result.created_at <= after_time
    
    def test_system_data_json_fields(self, app_fixture):
        """Test JSON field storage"""
        with app_fixture.app_context():
            import json
            
            cpu_freq = {'current': 2400, 'min': 1600, 'max': 3600}
            ram_info = {'total': 16000000000, 'available': 8000000000}
            disk_info = [
                {'device': '/dev/sda1', 'used': 500000000, 'free': 500000000}
            ]
            
            data = SystemData(
                serial_number='TEST-004',
                hostname='test-host-4',
                cpu_frequency=cpu_freq,
                ram_info=ram_info,
                disk_info=disk_info
            )
            db.session.add(data)
            db.session.commit()
            
            result = SystemData.query.filter_by(serial_number='TEST-004').first()
            assert result.cpu_frequency == cpu_freq
            assert result.ram_info == ram_info
            assert result.disk_info == disk_info
    
    def test_query_by_serial_number(self, app_fixture):
        """Test querying by serial number"""
        with app_fixture.app_context():
            data = SystemData(
                serial_number='QUERY-TEST-001',
                hostname='test-host'
            )
            db.session.add(data)
            db.session.commit()
            
            # Query by serial number (should use index)
            result = SystemData.query.filter_by(serial_number='QUERY-TEST-001').first()
            assert result is not None
    
    def test_query_by_last_update(self, app_fixture):
        """Test querying by last_update timestamp (indexed)"""
        with app_fixture.app_context():
            now = datetime.utcnow()
            data = SystemData(
                serial_number='TIME-TEST-001',
                hostname='test-host',
                last_update=now
            )
            db.session.add(data)
            db.session.commit()
            
            # Query by last_update
            result = SystemData.query.filter(
                SystemData.last_update >= now
            ).first()
            assert result is not None
    
    def test_soft_delete(self, app_fixture):
        """Test soft delete functionality"""
        with app_fixture.app_context():
            data = SystemData(
                serial_number='DELETE-TEST-001',
                hostname='test-host',
                deleted=False
            )
            db.session.add(data)
            db.session.commit()
            
            # Soft delete
            result = SystemData.query.filter_by(serial_number='DELETE-TEST-001').first()
            result.deleted = True
            db.session.commit()
            
            # Verify it's marked as deleted
            updated = SystemData.query.filter_by(serial_number='DELETE-TEST-001').first()
            assert updated.deleted is True
    
    def test_model_to_dict(self, app_fixture):
        """Test converting model to dictionary"""
        with app_fixture.app_context():
            data = SystemData(
                serial_number='DICT-TEST-001',
                hostname='test-host',
                status='active'
            )
            db.session.add(data)
            db.session.commit()
            
            result = SystemData.query.filter_by(serial_number='DICT-TEST-001').first()
            data_dict = result.to_dict()
            
            assert isinstance(data_dict, dict)
            assert data_dict['serial_number'] == 'DICT-TEST-001'
            assert data_dict['hostname'] == 'test-host'
            assert data_dict['status'] == 'active'
    
    def test_model_repr(self, app_fixture):
        """Test model string representation"""
        with app_fixture.app_context():
            data = SystemData(
                serial_number='REPR-TEST-001',
                hostname='test-host'
            )
            db.session.add(data)
            db.session.commit()
            
            result = SystemData.query.filter_by(serial_number='REPR-TEST-001').first()
            repr_string = repr(result)
            
            assert 'SystemData' in repr_string
            assert 'REPR-TEST-001' in repr_string


class TestDatabaseConstraints:
    """Test database constraints"""
    
    def test_serial_number_required(self, app_fixture):
        """Test that serial_number is required"""
        with app_fixture.app_context():
            data = SystemData(
                hostname='test-host'
                # Missing serial_number
            )
            
            with pytest.raises(Exception):  # Should raise integrity error
                db.session.add(data)
                db.session.commit()
            
            db.session.rollback()
    
    def test_hostname_required(self, app_fixture):
        """Test that hostname is required"""
        with app_fixture.app_context():
            data = SystemData(
                serial_number='TEST-001'
                # Missing hostname
            )
            
            with pytest.raises(Exception):  # Should raise integrity error
                db.session.add(data)
                db.session.commit()
            
            db.session.rollback()
    
    def test_duplicate_serial_number(self, app_fixture):
        """Test that duplicate serial numbers are allowed (multiple records per host)"""
        with app_fixture.app_context():
            # Create first record
            data1 = SystemData(
                serial_number='DUP-TEST-001',
                hostname='test-host-1'
            )
            db.session.add(data1)
            db.session.commit()
            
            # Create second record with same serial (should be allowed for historical data)
            data2 = SystemData(
                serial_number='DUP-TEST-001',
                hostname='test-host-1'
            )
            db.session.add(data2)
            db.session.commit()
            
            # Both should exist
            count = SystemData.query.filter_by(serial_number='DUP-TEST-001').count()
            assert count == 2


class TestDatabaseTransactions:
    """Test database transaction handling"""
    
    def test_rollback_on_error(self, app_fixture):
        """Test that changes are rolled back on error"""
        with app_fixture.app_context():
            initial_count = SystemData.query.count()
            
            try:
                data = SystemData(
                    serial_number='ROLLBACK-TEST-001',
                    hostname='test-host'
                )
                db.session.add(data)
                # Force an error
                raise Exception('Test error')
            except:
                db.session.rollback()
            
            # Verify nothing was added
            final_count = SystemData.query.count()
            assert final_count == initial_count
