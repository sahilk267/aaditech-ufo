"""
Database Models
SystemData model for storing system information
"""

from datetime import datetime
from .extensions import db


class SystemData(db.Model):
    """Model for storing system monitoring data"""
    
    id = db.Column(db.Integer, primary_key=True)
    serial_number = db.Column(db.String(255), nullable=False, index=True)
    hostname = db.Column(db.String(255), nullable=False)
    model_number = db.Column(db.String(255))
    ip_address = db.Column(db.String(20))
    local_ip = db.Column(db.String(20))
    public_ip = db.Column(db.String(20))
    
    # System information stored as JSON
    system_info = db.Column(db.JSON)
    
    # Performance metrics
    cpu_usage = db.Column(db.Float)
    cpu_per_core = db.Column(db.JSON)
    cpu_frequency = db.Column(db.JSON)
    cpu_info = db.Column(db.String(255))
    cpu_cores = db.Column(db.Integer)
    cpu_threads = db.Column(db.Integer)
    
    # Memory metrics
    ram_usage = db.Column(db.Float)
    ram_info = db.Column(db.JSON)
    
    # Disk metrics
    disk_info = db.Column(db.JSON)
    storage_usage = db.Column(db.Float)
    
    # Benchmark results
    software_benchmark = db.Column(db.Float)
    hardware_benchmark = db.Column(db.Float)
    overall_benchmark = db.Column(db.Float)
    benchmark_results = db.Column(db.JSON)
    
    # Performance metrics stored as JSON
    performance_metrics = db.Column(db.JSON)
    
    # Timestamps and status
    last_update = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    status = db.Column(db.String(20), default='active')
    current_user = db.Column(db.String(255))
    deleted = db.Column(db.Boolean, default=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<SystemData(id={self.id}, serial_number='{self.serial_number}', hostname='{self.hostname}')>"
    
    def to_dict(self):
        """Convert model to dictionary"""
        return {
            'id': self.id,
            'serial_number': self.serial_number,
            'hostname': self.hostname,
            'model_number': self.model_number,
            'local_ip': self.local_ip,
            'public_ip': self.public_ip,
            'system_info': self.system_info,
            'performance_metrics': self.performance_metrics,
            'benchmark_results': self.benchmark_results,
            'last_update': self.last_update.isoformat() if self.last_update else None,
            'status': self.status,
            'current_user': self.current_user
        }
