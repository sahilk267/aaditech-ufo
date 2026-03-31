"""add incidents workflow runs and delivery history

Revision ID: 010_incidents_workflow_runs_and_delivery_history
Revises: 009_log_sources_and_entries
Create Date: 2026-03-31 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '010_incidents_workflow_runs_and_delivery_history'
down_revision = '009_log_sources_and_entries'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'incident_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('fingerprint', sa.String(length=255), nullable=False),
        sa.Column('system_id', sa.Integer(), nullable=True),
        sa.Column('hostname', sa.String(length=255), nullable=True),
        sa.Column('severity', sa.String(length=20), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('alert_count', sa.Integer(), nullable=False),
        sa.Column('metric_count', sa.Integer(), nullable=False),
        sa.Column('occurrence_count', sa.Integer(), nullable=False),
        sa.Column('metrics', sa.JSON(), nullable=False),
        sa.Column('sample_alerts', sa.JSON(), nullable=False),
        sa.Column('first_seen_at', sa.DateTime(), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(), nullable=False),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_incident_records_fingerprint'), 'incident_records', ['fingerprint'], unique=False)
    op.create_index(op.f('ix_incident_records_hostname'), 'incident_records', ['hostname'], unique=False)
    op.create_index(op.f('ix_incident_records_last_seen_at'), 'incident_records', ['last_seen_at'], unique=False)
    op.create_index(op.f('ix_incident_records_organization_id'), 'incident_records', ['organization_id'], unique=False)
    op.create_index(op.f('ix_incident_records_severity'), 'incident_records', ['severity'], unique=False)
    op.create_index(op.f('ix_incident_records_status'), 'incident_records', ['status'], unique=False)
    op.create_index(op.f('ix_incident_records_system_id'), 'incident_records', ['system_id'], unique=False)

    op.create_table(
        'workflow_runs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('workflow_id', sa.Integer(), nullable=False),
        sa.Column('scheduled_job_id', sa.Integer(), nullable=True),
        sa.Column('trigger_source', sa.String(length=32), nullable=False),
        sa.Column('task_id', sa.String(length=128), nullable=True),
        sa.Column('dry_run', sa.Boolean(), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('error_reason', sa.String(length=64), nullable=True),
        sa.Column('input_payload', sa.JSON(), nullable=False),
        sa.Column('action_result', sa.JSON(), nullable=True),
        sa.Column('execution_metadata', sa.JSON(), nullable=True),
        sa.Column('executed_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['scheduled_job_id'], ['scheduled_jobs.id']),
        sa.ForeignKeyConstraint(['workflow_id'], ['automation_workflows.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_workflow_runs_dry_run'), 'workflow_runs', ['dry_run'], unique=False)
    op.create_index(op.f('ix_workflow_runs_error_reason'), 'workflow_runs', ['error_reason'], unique=False)
    op.create_index(op.f('ix_workflow_runs_executed_at'), 'workflow_runs', ['executed_at'], unique=False)
    op.create_index(op.f('ix_workflow_runs_organization_id'), 'workflow_runs', ['organization_id'], unique=False)
    op.create_index(op.f('ix_workflow_runs_scheduled_job_id'), 'workflow_runs', ['scheduled_job_id'], unique=False)
    op.create_index(op.f('ix_workflow_runs_status'), 'workflow_runs', ['status'], unique=False)
    op.create_index(op.f('ix_workflow_runs_task_id'), 'workflow_runs', ['task_id'], unique=False)
    op.create_index(op.f('ix_workflow_runs_trigger_source'), 'workflow_runs', ['trigger_source'], unique=False)
    op.create_index(op.f('ix_workflow_runs_workflow_id'), 'workflow_runs', ['workflow_id'], unique=False)

    op.create_table(
        'notification_deliveries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('task_id', sa.String(length=128), nullable=True),
        sa.Column('delivery_scope', sa.String(length=32), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('channels_requested', sa.JSON(), nullable=False),
        sa.Column('delivered_channels', sa.JSON(), nullable=False),
        sa.Column('alerts_count', sa.Integer(), nullable=False),
        sa.Column('raw_alerts_count', sa.Integer(), nullable=False),
        sa.Column('deduplicated_count', sa.Integer(), nullable=False),
        sa.Column('escalated_count', sa.Integer(), nullable=False),
        sa.Column('failure_count', sa.Integer(), nullable=False),
        sa.Column('failures', sa.JSON(), nullable=False),
        sa.Column('alert_snapshot', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_notification_deliveries_created_at'), 'notification_deliveries', ['created_at'], unique=False)
    op.create_index(op.f('ix_notification_deliveries_delivery_scope'), 'notification_deliveries', ['delivery_scope'], unique=False)
    op.create_index(op.f('ix_notification_deliveries_organization_id'), 'notification_deliveries', ['organization_id'], unique=False)
    op.create_index(op.f('ix_notification_deliveries_status'), 'notification_deliveries', ['status'], unique=False)
    op.create_index(op.f('ix_notification_deliveries_task_id'), 'notification_deliveries', ['task_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_notification_deliveries_task_id'), table_name='notification_deliveries')
    op.drop_index(op.f('ix_notification_deliveries_status'), table_name='notification_deliveries')
    op.drop_index(op.f('ix_notification_deliveries_organization_id'), table_name='notification_deliveries')
    op.drop_index(op.f('ix_notification_deliveries_delivery_scope'), table_name='notification_deliveries')
    op.drop_index(op.f('ix_notification_deliveries_created_at'), table_name='notification_deliveries')
    op.drop_table('notification_deliveries')

    op.drop_index(op.f('ix_workflow_runs_workflow_id'), table_name='workflow_runs')
    op.drop_index(op.f('ix_workflow_runs_trigger_source'), table_name='workflow_runs')
    op.drop_index(op.f('ix_workflow_runs_task_id'), table_name='workflow_runs')
    op.drop_index(op.f('ix_workflow_runs_status'), table_name='workflow_runs')
    op.drop_index(op.f('ix_workflow_runs_scheduled_job_id'), table_name='workflow_runs')
    op.drop_index(op.f('ix_workflow_runs_organization_id'), table_name='workflow_runs')
    op.drop_index(op.f('ix_workflow_runs_executed_at'), table_name='workflow_runs')
    op.drop_index(op.f('ix_workflow_runs_error_reason'), table_name='workflow_runs')
    op.drop_index(op.f('ix_workflow_runs_dry_run'), table_name='workflow_runs')
    op.drop_table('workflow_runs')

    op.drop_index(op.f('ix_incident_records_system_id'), table_name='incident_records')
    op.drop_index(op.f('ix_incident_records_status'), table_name='incident_records')
    op.drop_index(op.f('ix_incident_records_severity'), table_name='incident_records')
    op.drop_index(op.f('ix_incident_records_organization_id'), table_name='incident_records')
    op.drop_index(op.f('ix_incident_records_last_seen_at'), table_name='incident_records')
    op.drop_index(op.f('ix_incident_records_hostname'), table_name='incident_records')
    op.drop_index(op.f('ix_incident_records_fingerprint'), table_name='incident_records')
    op.drop_table('incident_records')
