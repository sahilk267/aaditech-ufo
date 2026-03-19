"""
Database Models
SystemData model for storing system information
"""

from datetime import datetime
from .extensions import db


user_roles = db.Table(
    'user_roles',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('role_id', db.Integer, db.ForeignKey('roles.id'), primary_key=True),
)


role_permissions = db.Table(
    'role_permissions',
    db.Column('role_id', db.Integer, db.ForeignKey('roles.id'), primary_key=True),
    db.Column('permission_id', db.Integer, db.ForeignKey('permissions.id'), primary_key=True),
)


class Organization(db.Model):
    """Tenant organization for multi-tenant data isolation."""

    __tablename__ = 'organizations'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(100), nullable=False, unique=True, index=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    systems = db.relationship('SystemData', backref='organization', lazy=True)
    users = db.relationship('User', backref='organization', lazy=True)
    roles = db.relationship('Role', backref='organization', lazy=True)

    def __repr__(self):
        return f"<Organization(id={self.id}, slug='{self.slug}', name='{self.name}')>"

    def to_dict(self):
        """Convert organization model to dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'slug': self.slug,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class User(db.Model):
    """Tenant-scoped user for authentication and RBAC."""

    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False, index=True)
    email = db.Column(db.String(255), nullable=False, index=True)
    full_name = db.Column(db.String(255), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    roles = db.relationship('Role', secondary=user_roles, lazy='subquery', backref=db.backref('users', lazy=True))

    __table_args__ = (
        db.UniqueConstraint('organization_id', 'email', name='uq_users_org_email'),
    )

    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}', organization_id={self.organization_id})>"


class Role(db.Model):
    """Role definition for RBAC."""

    __tablename__ = 'roles'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    is_system = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    permissions = db.relationship(
        'Permission',
        secondary=role_permissions,
        lazy='subquery',
        backref=db.backref('roles', lazy=True)
    )

    __table_args__ = (
        db.UniqueConstraint('organization_id', 'name', name='uq_roles_org_name'),
    )

    def __repr__(self):
        return f"<Role(id={self.id}, name='{self.name}', organization_id={self.organization_id})>"


class Permission(db.Model):
    """Permission definition assignable to roles."""

    __tablename__ = 'permissions'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(100), nullable=False, unique=True, index=True)
    description = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Permission(id={self.id}, code='{self.code}')>"


class RevokedToken(db.Model):
    """Store revoked JWT token identifiers (JTI) for logout/revocation checks."""

    __tablename__ = 'revoked_tokens'

    id = db.Column(db.Integer, primary_key=True)
    jti = db.Column(db.String(64), nullable=False, unique=True, index=True)
    token_type = db.Column(db.String(20), nullable=False)
    revoked_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True, index=True)

    def __repr__(self):
        return f"<RevokedToken(id={self.id}, jti='{self.jti}', token_type='{self.token_type}')>"


class AuditEvent(db.Model):
    """Persistent audit events for compliance and security investigations."""

    __tablename__ = 'audit_events'

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    action = db.Column(db.String(120), nullable=False, index=True)
    outcome = db.Column(db.String(20), nullable=False, index=True)

    tenant_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)

    method = db.Column(db.String(10), nullable=True)
    path = db.Column(db.String(255), nullable=True)
    remote_addr = db.Column(db.String(64), nullable=True)

    event_metadata = db.Column(db.JSON, nullable=True)

    def __repr__(self):
        return (
            f"<AuditEvent(id={self.id}, action='{self.action}', outcome='{self.outcome}', "
            f"tenant_id={self.tenant_id}, user_id={self.user_id})>"
        )


class AlertRule(db.Model):
    """Tenant-scoped threshold alert rule."""

    __tablename__ = 'alert_rules'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    metric = db.Column(db.String(64), nullable=False)
    operator = db.Column(db.String(2), nullable=False)
    threshold = db.Column(db.Float, nullable=False)
    severity = db.Column(db.String(20), nullable=False, default='warning')
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('organization_id', 'name', name='uq_alert_rules_org_name'),
    )

    def __repr__(self):
        return (
            f"<AlertRule(id={self.id}, organization_id={self.organization_id}, name='{self.name}', "
            f"metric='{self.metric}', operator='{self.operator}', threshold={self.threshold})>"
        )

    def to_dict(self):
        """Serialize alert rule for API responses."""
        return {
            'id': self.id,
            'organization_id': self.organization_id,
            'name': self.name,
            'metric': self.metric,
            'operator': self.operator,
            'threshold': self.threshold,
            'severity': self.severity,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class AutomationWorkflow(db.Model):
    """Tenant-scoped automation workflow definition."""

    __tablename__ = 'automation_workflows'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    trigger_type = db.Column(db.String(32), nullable=False, default='manual')
    trigger_conditions = db.Column(db.JSON, nullable=False, default=dict)
    action_type = db.Column(db.String(32), nullable=False)
    action_config = db.Column(db.JSON, nullable=False, default=dict)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    last_triggered_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('organization_id', 'name', name='uq_automation_workflows_org_name'),
    )

    def __repr__(self):
        return (
            f"<AutomationWorkflow(id={self.id}, organization_id={self.organization_id}, "
            f"name='{self.name}', trigger_type='{self.trigger_type}', action_type='{self.action_type}')>"
        )

    def to_dict(self):
        """Serialize workflow for API responses."""
        return {
            'id': self.id,
            'organization_id': self.organization_id,
            'name': self.name,
            'trigger_type': self.trigger_type,
            'trigger_conditions': self.trigger_conditions or {},
            'action_type': self.action_type,
            'action_config': self.action_config or {},
            'is_active': self.is_active,
            'last_triggered_at': self.last_triggered_at.isoformat() if self.last_triggered_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class SystemData(db.Model):
    """Model for storing system monitoring data"""
    
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(
        db.Integer,
        db.ForeignKey('organizations.id'),
        nullable=True,
        index=True
    )
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
        return (
            f"<SystemData(id={self.id}, organization_id={self.organization_id}, "
            f"serial_number='{self.serial_number}', hostname='{self.hostname}')>"
        )
    
    def to_dict(self):
        """Convert model to dictionary"""
        return {
            'id': self.id,
            'organization_id': self.organization_id,
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
