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
    failed_login_attempts = db.Column(db.Integer, nullable=False, default=0)
    locked_until = db.Column(db.DateTime, nullable=True, index=True)
    last_login_at = db.Column(db.DateTime, nullable=True, index=True)
    auth_token_version = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    roles = db.relationship('Role', secondary=user_roles, lazy='subquery', backref=db.backref('users', lazy=True))

    __table_args__ = (
        db.UniqueConstraint('organization_id', 'email', name='uq_users_org_email'),
    )

    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}', organization_id={self.organization_id})>"


class UserTotpFactor(db.Model):
    """Encrypted TOTP MFA factor for a tenant-scoped user."""

    __tablename__ = 'user_totp_factors'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True, index=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False, index=True)
    secret_ciphertext = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(32), nullable=False, default='pending', index=True)
    enrolled_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    verified_at = db.Column(db.DateTime, nullable=True)
    last_used_at = db.Column(db.DateTime, nullable=True)
    disabled_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('totp_factor', uselist=False))

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'organization_id': self.organization_id,
            'status': self.status,
            'enrolled_at': self.enrolled_at.isoformat() if self.enrolled_at else None,
            'verified_at': self.verified_at.isoformat() if self.verified_at else None,
            'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None,
            'disabled_at': self.disabled_at.isoformat() if self.disabled_at else None,
        }


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


class AlertSilence(db.Model):
    """Tenant-scoped alert silence window — suppress alerts during maintenance periods."""

    __tablename__ = 'alert_silences'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False, index=True)
    rule_id = db.Column(db.Integer, db.ForeignKey('alert_rules.id'), nullable=True, index=True)
    metric = db.Column(db.String(64), nullable=True, index=True)
    reason = db.Column(db.String(255), nullable=True)
    starts_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    ends_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return (
            f"<AlertSilence(id={self.id}, organization_id={self.organization_id}, "
            f"rule_id={self.rule_id}, metric='{self.metric}', ends_at={self.ends_at})>"
        )

    def to_dict(self):
        """Serialize alert silence for API responses."""
        return {
            'id': self.id,
            'organization_id': self.organization_id,
            'rule_id': self.rule_id,
            'metric': self.metric,
            'reason': self.reason,
            'starts_at': self.starts_at.isoformat() if self.starts_at else None,
            'ends_at': self.ends_at.isoformat() if self.ends_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
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


class ScheduledJob(db.Model):
    """Tenant-scoped scheduled automation job (cron-style trigger)."""

    __tablename__ = 'scheduled_jobs'

    CRON_EXPRESSION_PATTERN = r'^(\*|[0-9,\-*/]+)\s+(\*|[0-9,\-*/]+)\s+(\*|[0-9,\-*/]+)\s+(\*|[0-9,\-*/]+)\s+(\*|[0-9,\-*/]+)$'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False, index=True)
    workflow_id = db.Column(db.Integer, db.ForeignKey('automation_workflows.id'), nullable=False, index=True)
    cron_expression = db.Column(db.String(64), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    last_run_at = db.Column(db.DateTime, nullable=True)
    next_run_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return (
            f"<ScheduledJob(id={self.id}, organization_id={self.organization_id}, "
            f"workflow_id={self.workflow_id}, cron='{self.cron_expression}')>"
        )

    def to_dict(self):
        """Serialize scheduled job for API responses."""
        return {
            'id': self.id,
            'organization_id': self.organization_id,
            'workflow_id': self.workflow_id,
            'cron_expression': self.cron_expression,
            'is_active': self.is_active,
            'last_run_at': self.last_run_at.isoformat() if self.last_run_at else None,
            'next_run_at': self.next_run_at.isoformat() if self.next_run_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class LogSource(db.Model):
    """Tenant-scoped persistent log source metadata."""

    __tablename__ = 'log_sources'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False, index=True)
    name = db.Column(db.String(128), nullable=False)
    adapter = db.Column(db.String(32), nullable=False, default='linux_test_double')
    description = db.Column(db.String(255), nullable=True)
    host_name = db.Column(db.String(255), nullable=True, index=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    source_metadata = db.Column(db.JSON, nullable=True)
    last_ingested_at = db.Column(db.DateTime, nullable=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('organization_id', 'name', name='uq_log_sources_org_name'),
    )

    def to_dict(self):
        """Serialize log source for API responses."""
        return {
            'id': self.id,
            'organization_id': self.organization_id,
            'name': self.name,
            'adapter': self.adapter,
            'description': self.description,
            'host_name': self.host_name,
            'is_active': self.is_active,
            'source_metadata': self.source_metadata or {},
            'last_ingested_at': self.last_ingested_at.isoformat() if self.last_ingested_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class LogEntry(db.Model):
    """Tenant-scoped persistent log entry."""

    __tablename__ = 'log_entries'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False, index=True)
    log_source_id = db.Column(db.Integer, db.ForeignKey('log_sources.id'), nullable=True, index=True)
    source_name = db.Column(db.String(128), nullable=False, index=True)
    adapter = db.Column(db.String(32), nullable=False, default='linux_test_double')
    capture_kind = db.Column(db.String(32), nullable=False, default='ingest', index=True)
    observed_at = db.Column(db.DateTime, nullable=True, index=True)
    severity = db.Column(db.String(20), nullable=True, index=True)
    event_id = db.Column(db.String(64), nullable=True, index=True)
    message = db.Column(db.Text, nullable=False)
    raw_entry = db.Column(db.Text, nullable=False)
    entry_metadata = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    source = db.relationship('LogSource', backref=db.backref('entries', lazy=True))

    def to_dict(self):
        """Serialize log entry for API responses."""
        return {
            'id': self.id,
            'organization_id': self.organization_id,
            'log_source_id': self.log_source_id,
            'source_name': self.source_name,
            'adapter': self.adapter,
            'capture_kind': self.capture_kind,
            'observed_at': self.observed_at.isoformat() if self.observed_at else None,
            'severity': self.severity,
            'event_id': self.event_id,
            'message': self.message,
            'raw_entry': self.raw_entry,
            'entry_metadata': self.entry_metadata or {},
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class LogInvestigation(db.Model):
    """Tenant-scoped saved log investigation context."""

    __tablename__ = 'log_investigations'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False, index=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    name = db.Column(db.String(160), nullable=False)
    status = db.Column(db.String(32), nullable=False, default='open', index=True)
    source_name = db.Column(db.String(128), nullable=True, index=True)
    pinned_source_id = db.Column(db.Integer, db.ForeignKey('log_sources.id'), nullable=True, index=True)
    pinned_entry_id = db.Column(db.Integer, db.ForeignKey('log_entries.id'), nullable=True, index=True)
    filter_snapshot = db.Column(db.JSON, nullable=False, default=dict)
    notes = db.Column(db.Text, nullable=True)
    last_result_count = db.Column(db.Integer, nullable=False, default=0)
    last_matched_at = db.Column(db.DateTime, nullable=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('organization_id', 'name', name='uq_log_investigations_org_name'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'organization_id': self.organization_id,
            'created_by_user_id': self.created_by_user_id,
            'name': self.name,
            'status': self.status,
            'source_name': self.source_name,
            'pinned_source_id': self.pinned_source_id,
            'pinned_entry_id': self.pinned_entry_id,
            'filter_snapshot': self.filter_snapshot or {},
            'notes': self.notes,
            'last_result_count': self.last_result_count,
            'last_matched_at': self.last_matched_at.isoformat() if self.last_matched_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class IncidentRecord(db.Model):
    """Tenant-scoped durable incident record derived from correlated alerts."""

    __tablename__ = 'incident_records'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False, index=True)
    fingerprint = db.Column(db.String(255), nullable=False, index=True)
    system_id = db.Column(db.Integer, nullable=True, index=True)
    hostname = db.Column(db.String(255), nullable=True, index=True)
    severity = db.Column(db.String(20), nullable=False, default='warning', index=True)
    status = db.Column(db.String(20), nullable=False, default='open', index=True)
    title = db.Column(db.String(255), nullable=False)
    alert_count = db.Column(db.Integer, nullable=False, default=0)
    metric_count = db.Column(db.Integer, nullable=False, default=0)
    occurrence_count = db.Column(db.Integer, nullable=False, default=1)
    assigned_to_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    acknowledged_at = db.Column(db.DateTime, nullable=True)
    resolution_summary = db.Column(db.String(1000), nullable=True)
    metrics = db.Column(db.JSON, nullable=False, default=list)
    sample_alerts = db.Column(db.JSON, nullable=False, default=list)
    first_seen_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    last_seen_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    resolved_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        """Serialize incident record for API responses."""
        return {
            'id': self.id,
            'organization_id': self.organization_id,
            'fingerprint': self.fingerprint,
            'system_id': self.system_id,
            'hostname': self.hostname,
            'severity': self.severity,
            'status': self.status,
            'title': self.title,
            'alert_count': self.alert_count,
            'metric_count': self.metric_count,
            'occurrence_count': self.occurrence_count,
            'assigned_to_user_id': self.assigned_to_user_id,
            'acknowledged_at': self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            'resolution_summary': self.resolution_summary,
            'metrics': self.metrics or [],
            'sample_alerts': self.sample_alerts or [],
            'first_seen_at': self.first_seen_at.isoformat() if self.first_seen_at else None,
            'last_seen_at': self.last_seen_at.isoformat() if self.last_seen_at else None,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class IncidentCaseComment(db.Model):
    """Tenant-scoped incident investigation note/comment."""

    __tablename__ = 'incident_case_comments'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False, index=True)
    incident_id = db.Column(db.Integer, db.ForeignKey('incident_records.id'), nullable=False, index=True)
    author_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    comment_type = db.Column(db.String(32), nullable=False, default='note', index=True)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    incident = db.relationship('IncidentRecord', backref=db.backref('case_comments', lazy=True, order_by='IncidentCaseComment.created_at.desc()'))

    def to_dict(self):
        return {
            'id': self.id,
            'organization_id': self.organization_id,
            'incident_id': self.incident_id,
            'author_user_id': self.author_user_id,
            'comment_type': self.comment_type,
            'body': self.body,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class WorkflowRun(db.Model):
    """Tenant-scoped durable workflow execution history."""

    __tablename__ = 'workflow_runs'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False, index=True)
    workflow_id = db.Column(db.Integer, db.ForeignKey('automation_workflows.id'), nullable=False, index=True)
    scheduled_job_id = db.Column(db.Integer, db.ForeignKey('scheduled_jobs.id'), nullable=True, index=True)
    trigger_source = db.Column(db.String(32), nullable=False, default='manual', index=True)
    task_id = db.Column(db.String(128), nullable=True, index=True)
    dry_run = db.Column(db.Boolean, nullable=False, default=True, index=True)
    status = db.Column(db.String(32), nullable=False, index=True)
    error_reason = db.Column(db.String(64), nullable=True, index=True)
    input_payload = db.Column(db.JSON, nullable=False, default=dict)
    action_result = db.Column(db.JSON, nullable=True)
    execution_metadata = db.Column(db.JSON, nullable=True)
    executed_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    workflow = db.relationship('AutomationWorkflow', backref=db.backref('runs', lazy=True))
    scheduled_job = db.relationship('ScheduledJob', backref=db.backref('workflow_runs', lazy=True))

    def to_dict(self):
        """Serialize workflow run for API responses."""
        return {
            'id': self.id,
            'organization_id': self.organization_id,
            'workflow_id': self.workflow_id,
            'scheduled_job_id': self.scheduled_job_id,
            'trigger_source': self.trigger_source,
            'task_id': self.task_id,
            'dry_run': self.dry_run,
            'status': self.status,
            'error_reason': self.error_reason,
            'input_payload': self.input_payload or {},
            'action_result': self.action_result or {},
            'execution_metadata': self.execution_metadata or {},
            'executed_at': self.executed_at.isoformat() if self.executed_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class NotificationDelivery(db.Model):
    """Tenant-scoped durable alert notification delivery history."""

    __tablename__ = 'notification_deliveries'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False, index=True)
    task_id = db.Column(db.String(128), nullable=True, index=True)
    delivery_scope = db.Column(db.String(32), nullable=False, default='alerts.dispatch', index=True)
    status = db.Column(db.String(32), nullable=False, index=True)
    channels_requested = db.Column(db.JSON, nullable=False, default=list)
    delivered_channels = db.Column(db.JSON, nullable=False, default=list)
    alerts_count = db.Column(db.Integer, nullable=False, default=0)
    raw_alerts_count = db.Column(db.Integer, nullable=False, default=0)
    deduplicated_count = db.Column(db.Integer, nullable=False, default=0)
    escalated_count = db.Column(db.Integer, nullable=False, default=0)
    failure_count = db.Column(db.Integer, nullable=False, default=0)
    failures = db.Column(db.JSON, nullable=False, default=list)
    alert_snapshot = db.Column(db.JSON, nullable=False, default=list)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    def to_dict(self):
        """Serialize delivery history for API responses."""
        return {
            'id': self.id,
            'organization_id': self.organization_id,
            'task_id': self.task_id,
            'delivery_scope': self.delivery_scope,
            'status': self.status,
            'channels_requested': self.channels_requested or [],
            'delivered_channels': self.delivered_channels or [],
            'alerts_count': self.alerts_count,
            'raw_alerts_count': self.raw_alerts_count,
            'deduplicated_count': self.deduplicated_count,
            'escalated_count': self.escalated_count,
            'failure_count': self.failure_count,
            'failures': self.failures or [],
            'alert_snapshot': self.alert_snapshot or [],
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class ReliabilityRun(db.Model):
    """Tenant-scoped durable reliability diagnostic execution history."""

    __tablename__ = 'reliability_runs'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False, index=True)
    diagnostic_type = db.Column(db.String(64), nullable=False, index=True)
    host_name = db.Column(db.String(255), nullable=False, index=True)
    dump_name = db.Column(db.String(255), nullable=True, index=True)
    adapter = db.Column(db.String(32), nullable=True, index=True)
    status = db.Column(db.String(32), nullable=False, index=True)
    error_reason = db.Column(db.String(64), nullable=True, index=True)
    request_payload = db.Column(db.JSON, nullable=False, default=dict)
    result_payload = db.Column(db.JSON, nullable=True)
    summary = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    def to_dict(self):
        return {
            'id': self.id,
            'organization_id': self.organization_id,
            'diagnostic_type': self.diagnostic_type,
            'host_name': self.host_name,
            'dump_name': self.dump_name,
            'adapter': self.adapter,
            'status': self.status,
            'error_reason': self.error_reason,
            'request_payload': self.request_payload or {},
            'result_payload': self.result_payload or {},
            'summary': self.summary or {},
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class UpdateRun(db.Model):
    """Tenant-scoped durable update monitoring execution history."""

    __tablename__ = 'update_runs'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False, index=True)
    host_name = db.Column(db.String(255), nullable=False, index=True)
    adapter = db.Column(db.String(32), nullable=True, index=True)
    status = db.Column(db.String(32), nullable=False, index=True)
    error_reason = db.Column(db.String(64), nullable=True, index=True)
    update_count = db.Column(db.Integer, nullable=False, default=0)
    latest_installed_on = db.Column(db.String(32), nullable=True)
    updates_payload = db.Column(db.JSON, nullable=True)
    summary = db.Column(db.JSON, nullable=True)
    confidence_score = db.Column(db.Float, nullable=True)
    confidence_payload = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    def to_dict(self):
        return {
            'id': self.id,
            'organization_id': self.organization_id,
            'host_name': self.host_name,
            'adapter': self.adapter,
            'status': self.status,
            'error_reason': self.error_reason,
            'update_count': self.update_count,
            'latest_installed_on': self.latest_installed_on,
            'updates_payload': self.updates_payload or {},
            'summary': self.summary or {},
            'confidence_score': self.confidence_score,
            'confidence_payload': self.confidence_payload or {},
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Agent(db.Model):
    """Tenant-scoped agent inventory and enrollment state."""

    __tablename__ = 'agents'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False, index=True)
    display_name = db.Column(db.String(255), nullable=False)
    hostname = db.Column(db.String(255), nullable=False, index=True)
    serial_number = db.Column(db.String(255), nullable=False, index=True)
    platform = db.Column(db.String(64), nullable=False, default='unknown')
    agent_version = db.Column(db.String(64), nullable=True)
    enrollment_state = db.Column(db.String(32), nullable=False, default='pending', index=True)
    trust_state = db.Column(db.String(32), nullable=False, default='untrusted', index=True)
    last_seen_at = db.Column(db.DateTime, nullable=True, index=True)
    last_ip = db.Column(db.String(64), nullable=True)
    credential_rotated_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('organization_id', 'serial_number', name='uq_agents_org_serial_number'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'organization_id': self.organization_id,
            'display_name': self.display_name,
            'hostname': self.hostname,
            'serial_number': self.serial_number,
            'platform': self.platform,
            'agent_version': self.agent_version,
            'enrollment_state': self.enrollment_state,
            'trust_state': self.trust_state,
            'last_seen_at': self.last_seen_at.isoformat() if self.last_seen_at else None,
            'last_ip': self.last_ip,
            'credential_rotated_at': self.credential_rotated_at.isoformat() if self.credential_rotated_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class AgentCredential(db.Model):
    """Issued per-agent credential fingerprint and lifecycle."""

    __tablename__ = 'agent_credentials'

    id = db.Column(db.Integer, primary_key=True)
    agent_id = db.Column(db.Integer, db.ForeignKey('agents.id'), nullable=False, index=True)
    credential_fingerprint = db.Column(db.String(128), nullable=False, unique=True, index=True)
    issued_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True, index=True)
    revoked_at = db.Column(db.DateTime, nullable=True, index=True)
    rotation_reason = db.Column(db.String(128), nullable=True)
    status = db.Column(db.String(32), nullable=False, default='active', index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    agent = db.relationship('Agent', backref=db.backref('credentials', lazy=True))

    def to_dict(self):
        return {
            'id': self.id,
            'agent_id': self.agent_id,
            'credential_fingerprint': self.credential_fingerprint,
            'issued_at': self.issued_at.isoformat() if self.issued_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'revoked_at': self.revoked_at.isoformat() if self.revoked_at else None,
            'rotation_reason': self.rotation_reason,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class AgentEnrollmentToken(db.Model):
    """Short-lived tenant-scoped bootstrap token for agent enrollment."""

    __tablename__ = 'agent_enrollment_tokens'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False, index=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    token_fingerprint = db.Column(db.String(128), nullable=False, unique=True, index=True)
    intended_hostname_pattern = db.Column(db.String(255), nullable=True)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    used_at = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(32), nullable=False, default='issued', index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'organization_id': self.organization_id,
            'created_by_user_id': self.created_by_user_id,
            'token_fingerprint': self.token_fingerprint,
            'intended_hostname_pattern': self.intended_hostname_pattern,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'used_at': self.used_at.isoformat() if self.used_at else None,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class TenantSecret(db.Model):
    """Encrypted tenant-scoped operational secret metadata."""

    __tablename__ = 'tenant_secrets'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False, index=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    secret_type = db.Column(db.String(64), nullable=False, index=True)
    name = db.Column(db.String(128), nullable=False)
    status = db.Column(db.String(32), nullable=False, default='active', index=True)
    ciphertext = db.Column(db.Text, nullable=False)
    key_version = db.Column(db.String(32), nullable=False, default='v1')
    rotated_at = db.Column(db.DateTime, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True, index=True)
    last_used_at = db.Column(db.DateTime, nullable=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('organization_id', 'secret_type', 'name', name='uq_tenant_secrets_org_type_name'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'organization_id': self.organization_id,
            'created_by_user_id': self.created_by_user_id,
            'secret_type': self.secret_type,
            'name': self.name,
            'status': self.status,
            'key_version': self.key_version,
            'rotated_at': self.rotated_at.isoformat() if self.rotated_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class TenantSetting(db.Model):
    """First-class tenant settings surface for product-level configuration."""

    __tablename__ = 'tenant_settings'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False, unique=True, index=True)
    notification_settings = db.Column(db.JSON, nullable=False, default=dict)
    retention_settings = db.Column(db.JSON, nullable=False, default=dict)
    branding_settings = db.Column(db.JSON, nullable=False, default=dict)
    auth_policy = db.Column(db.JSON, nullable=False, default=dict)
    feature_flags = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'organization_id': self.organization_id,
            'notification_settings': self.notification_settings or {},
            'retention_settings': self.retention_settings or {},
            'branding_settings': self.branding_settings or {},
            'auth_policy': self.auth_policy or {},
            'feature_flags': self.feature_flags or {},
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class TenantOidcProvider(db.Model):
    """Tenant-scoped OIDC provider configuration."""

    __tablename__ = 'tenant_oidc_providers'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    issuer = db.Column(db.String(255), nullable=False)
    client_id = db.Column(db.String(255), nullable=False)
    client_secret_secret_name = db.Column(db.String(255), nullable=True)
    discovery_endpoint = db.Column(db.String(500), nullable=True)
    authorization_endpoint = db.Column(db.String(500), nullable=False)
    token_endpoint = db.Column(db.String(500), nullable=True)
    userinfo_endpoint = db.Column(db.String(500), nullable=True)
    jwks_uri = db.Column(db.String(500), nullable=True)
    end_session_endpoint = db.Column(db.String(500), nullable=True)
    scopes = db.Column(db.JSON, nullable=False, default=list)
    claim_mappings = db.Column(db.JSON, nullable=False, default=dict)
    role_mappings = db.Column(db.JSON, nullable=False, default=dict)
    test_mode = db.Column(db.Boolean, nullable=False, default=False)
    test_claims = db.Column(db.JSON, nullable=False, default=dict)
    is_enabled = db.Column(db.Boolean, nullable=False, default=True, index=True)
    is_default = db.Column(db.Boolean, nullable=False, default=False, index=True)
    last_discovery_status = db.Column(db.String(32), nullable=True)
    last_auth_status = db.Column(db.String(32), nullable=True)
    last_error = db.Column(db.Text, nullable=True)
    last_discovery_at = db.Column(db.DateTime, nullable=True)
    last_auth_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('organization_id', 'name', name='uq_tenant_oidc_providers_org_name'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'organization_id': self.organization_id,
            'name': self.name,
            'issuer': self.issuer,
            'client_id': self.client_id,
            'discovery_endpoint': self.discovery_endpoint,
            'authorization_endpoint': self.authorization_endpoint,
            'token_endpoint': self.token_endpoint,
            'userinfo_endpoint': self.userinfo_endpoint,
            'jwks_uri': self.jwks_uri,
            'end_session_endpoint': self.end_session_endpoint,
            'scopes': self.scopes or [],
            'claim_mappings': self.claim_mappings or {},
            'role_mappings': self.role_mappings or {},
            'test_mode': self.test_mode,
            'test_claim_codes': sorted((self.test_claims or {}).keys()),
            'is_enabled': self.is_enabled,
            'is_default': self.is_default,
            'has_client_secret': bool(self.client_secret_secret_name),
            'client_secret_secret_name': self.client_secret_secret_name,
            'last_discovery_status': self.last_discovery_status,
            'last_auth_status': self.last_auth_status,
            'last_error': self.last_error,
            'last_discovery_at': self.last_discovery_at.isoformat() if self.last_discovery_at else None,
            'last_auth_at': self.last_auth_at.isoformat() if self.last_auth_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class TenantEntitlement(db.Model):
    """Tenant-scoped entitlement/plan control for commercial and platform gating."""

    __tablename__ = 'tenant_entitlements'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False, index=True)
    entitlement_key = db.Column(db.String(64), nullable=False, index=True)
    is_enabled = db.Column(db.Boolean, nullable=False, default=True, index=True)
    limit_value = db.Column(db.Integer, nullable=True)
    metadata_json = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('organization_id', 'entitlement_key', name='uq_tenant_entitlements_org_key'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'organization_id': self.organization_id,
            'entitlement_key': self.entitlement_key,
            'is_enabled': self.is_enabled,
            'limit_value': self.limit_value,
            'metadata': self.metadata_json or {},
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class TenantFeatureFlag(db.Model):
    """Tenant-scoped feature flag for controlled rollout of product capabilities."""

    __tablename__ = 'tenant_feature_flags'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False, index=True)
    flag_key = db.Column(db.String(64), nullable=False, index=True)
    is_enabled = db.Column(db.Boolean, nullable=False, default=True, index=True)
    description = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('organization_id', 'flag_key', name='uq_tenant_feature_flags_org_key'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'organization_id': self.organization_id,
            'flag_key': self.flag_key,
            'is_enabled': self.is_enabled,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class TenantQuotaPolicy(db.Model):
    """Tenant-scoped quota policy for enforceable resource boundaries."""

    __tablename__ = 'tenant_quota_policies'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False, index=True)
    quota_key = db.Column(db.String(64), nullable=False, index=True)
    limit_value = db.Column(db.Integer, nullable=True)
    is_enforced = db.Column(db.Boolean, nullable=False, default=False, index=True)
    metadata_json = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('organization_id', 'quota_key', name='uq_tenant_quota_policies_org_key'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'organization_id': self.organization_id,
            'quota_key': self.quota_key,
            'limit_value': self.limit_value,
            'is_enforced': self.is_enforced,
            'metadata': self.metadata_json or {},
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class TenantUsageMetric(db.Model):
    """Tenant-scoped current usage snapshot for quota reporting."""

    __tablename__ = 'tenant_usage_metrics'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False, index=True)
    metric_key = db.Column(db.String(64), nullable=False, index=True)
    current_value = db.Column(db.Integer, nullable=False, default=0)
    metadata_json = db.Column(db.JSON, nullable=True)
    measured_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('organization_id', 'metric_key', name='uq_tenant_usage_metrics_org_key'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'organization_id': self.organization_id,
            'metric_key': self.metric_key,
            'current_value': self.current_value,
            'metadata': self.metadata_json or {},
            'measured_at': self.measured_at.isoformat() if self.measured_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class TenantPlan(db.Model):
    """Tenant-scoped commercial plan record decoupled from entitlements and quotas."""

    __tablename__ = 'tenant_plans'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False, unique=True, index=True)
    plan_key = db.Column(db.String(64), nullable=False, default='starter')
    display_name = db.Column(db.String(120), nullable=False, default='Starter')
    status = db.Column(db.String(32), nullable=False, default='active', index=True)
    billing_cycle = db.Column(db.String(32), nullable=True)
    effective_from = db.Column(db.DateTime, nullable=True)
    external_customer_ref = db.Column(db.String(128), nullable=True, index=True)
    external_subscription_ref = db.Column(db.String(128), nullable=True, index=True)
    metadata_json = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'organization_id': self.organization_id,
            'plan_key': self.plan_key,
            'display_name': self.display_name,
            'status': self.status,
            'billing_cycle': self.billing_cycle,
            'effective_from': self.effective_from.isoformat() if self.effective_from else None,
            'external_customer_ref': self.external_customer_ref,
            'external_subscription_ref': self.external_subscription_ref,
            'metadata': self.metadata_json or {},
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class TenantBillingProfile(db.Model):
    """Tenant-scoped billing contact and provider-boundary metadata."""

    __tablename__ = 'tenant_billing_profiles'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False, unique=True, index=True)
    billing_email = db.Column(db.String(255), nullable=True)
    billing_name = db.Column(db.String(255), nullable=True)
    contact_email = db.Column(db.String(255), nullable=True)
    country_code = db.Column(db.String(8), nullable=True)
    provider_name = db.Column(db.String(64), nullable=True)
    provider_customer_ref = db.Column(db.String(128), nullable=True, index=True)
    tax_id_hint = db.Column(db.String(32), nullable=True)
    metadata_json = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'organization_id': self.organization_id,
            'billing_email': self.billing_email,
            'billing_name': self.billing_name,
            'contact_email': self.contact_email,
            'country_code': self.country_code,
            'provider_name': self.provider_name,
            'provider_customer_ref': self.provider_customer_ref,
            'tax_id_hint': self.tax_id_hint,
            'metadata': self.metadata_json or {},
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class TenantLicense(db.Model):
    """Tenant-scoped licensing snapshot kept separate from entitlements/quota policy."""

    __tablename__ = 'tenant_licenses'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False, unique=True, index=True)
    license_status = db.Column(db.String(32), nullable=False, default='draft', index=True)
    license_key_hint = db.Column(db.String(32), nullable=True)
    seat_limit = db.Column(db.Integer, nullable=True)
    enforcement_mode = db.Column(db.String(32), nullable=False, default='advisory')
    expires_at = db.Column(db.DateTime, nullable=True, index=True)
    metadata_json = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'organization_id': self.organization_id,
            'license_status': self.license_status,
            'license_key_hint': self.license_key_hint,
            'seat_limit': self.seat_limit,
            'enforcement_mode': self.enforcement_mode,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'metadata': self.metadata_json or {},
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


class AgentCommand(db.Model):
    """Server-issued command queued for an agent to poll, execute and report back."""

    __tablename__ = 'agent_commands'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False, index=True)
    agent_id = db.Column(db.Integer, db.ForeignKey('agents.id'), nullable=True, index=True)
    target_serial_number = db.Column(db.String(255), nullable=True, index=True)
    command_type = db.Column(db.String(64), nullable=False, index=True)
    payload = db.Column(db.JSON, nullable=True)
    status = db.Column(db.String(32), nullable=False, default='pending', index=True)
    result = db.Column(db.JSON, nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    requested_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    dispatched_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True, index=True)

    def to_dict(self):
        return {
            'id': self.id,
            'organization_id': self.organization_id,
            'agent_id': self.agent_id,
            'target_serial_number': self.target_serial_number,
            'command_type': self.command_type,
            'payload': self.payload or {},
            'status': self.status,
            'result': self.result,
            'error_message': self.error_message,
            'requested_by_user_id': self.requested_by_user_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'dispatched_at': self.dispatched_at.isoformat() if self.dispatched_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
        }


class AgentServerPin(db.Model):
    """Pinned server-cert SHA-256 fingerprint advertised to enrolled agents."""

    __tablename__ = 'agent_server_pins'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False, index=True)
    cert_sha256 = db.Column(db.String(128), nullable=False)
    label = db.Column(db.String(128), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    rotated_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'organization_id': self.organization_id,
            'cert_sha256': self.cert_sha256,
            'label': self.label,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'rotated_at': self.rotated_at.isoformat() if self.rotated_at else None,
        }
