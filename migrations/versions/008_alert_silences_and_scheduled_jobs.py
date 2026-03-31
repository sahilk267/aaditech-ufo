"""add alert silences and scheduled jobs

Revision ID: 008_alert_silences_and_scheduled_jobs
Revises: 007_automation_workflows
Create Date: 2026-03-26 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '008_alert_silences_and_scheduled_jobs'
down_revision = '007_automation_workflows'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'alert_silences',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('rule_id', sa.Integer(), nullable=True),
        sa.Column('metric', sa.String(length=64), nullable=True),
        sa.Column('reason', sa.String(length=255), nullable=True),
        sa.Column('starts_at', sa.DateTime(), nullable=False),
        sa.Column('ends_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['rule_id'], ['alert_rules.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_alert_silences_organization_id', 'alert_silences', ['organization_id'], unique=False)
    op.create_index('ix_alert_silences_rule_id', 'alert_silences', ['rule_id'], unique=False)
    op.create_index('ix_alert_silences_metric', 'alert_silences', ['metric'], unique=False)

    op.create_table(
        'scheduled_jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('workflow_id', sa.Integer(), nullable=False),
        sa.Column('cron_expression', sa.String(length=64), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('last_run_at', sa.DateTime(), nullable=True),
        sa.Column('next_run_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['workflow_id'], ['automation_workflows.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_scheduled_jobs_organization_id', 'scheduled_jobs', ['organization_id'], unique=False)
    op.create_index('ix_scheduled_jobs_workflow_id', 'scheduled_jobs', ['workflow_id'], unique=False)


def downgrade():
    op.drop_index('ix_scheduled_jobs_workflow_id', table_name='scheduled_jobs')
    op.drop_index('ix_scheduled_jobs_organization_id', table_name='scheduled_jobs')
    op.drop_table('scheduled_jobs')

    op.drop_index('ix_alert_silences_metric', table_name='alert_silences')
    op.drop_index('ix_alert_silences_rule_id', table_name='alert_silences')
    op.drop_index('ix_alert_silences_organization_id', table_name='alert_silences')
    op.drop_table('alert_silences')
