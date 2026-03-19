"""add automation workflows

Revision ID: 007_automation_workflows
Revises: 006_alert_rules
Create Date: 2026-03-18 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '007_automation_workflows'
down_revision = '006_alert_rules'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'automation_workflows',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('trigger_type', sa.String(length=32), nullable=False),
        sa.Column('trigger_conditions', sa.JSON(), nullable=False),
        sa.Column('action_type', sa.String(length=32), nullable=False),
        sa.Column('action_config', sa.JSON(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('last_triggered_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'name', name='uq_automation_workflows_org_name'),
    )
    op.create_index('ix_automation_workflows_organization_id', 'automation_workflows', ['organization_id'])


def downgrade():
    op.drop_index('ix_automation_workflows_organization_id', table_name='automation_workflows')
    op.drop_table('automation_workflows')
