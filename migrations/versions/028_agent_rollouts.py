"""add agent_rollouts and agent_rollout_batches tables

Revision ID: 028_agent_rollouts
Revises: 027_agent_sessions
Create Date: 2026-05-10
"""

from alembic import op
import sqlalchemy as sa

revision = '028_agent_rollouts'
down_revision = '027_agent_sessions'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'agent_rollouts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id'), nullable=False),
        sa.Column('version', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='draft'),
        sa.Column('total_batches', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('current_batch', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('batch_config', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('github_run_id', sa.String(length=64), nullable=True),
        sa.Column('github_run_url', sa.String(length=512), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('tested_at', sa.DateTime(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.String(length=255), nullable=True),
    )
    op.create_index('ix_agent_rollouts_org_id', 'agent_rollouts', ['organization_id'])
    op.create_index('ix_agent_rollouts_status', 'agent_rollouts', ['status'])

    op.create_table(
        'agent_rollout_batches',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('rollout_id', sa.Integer(), sa.ForeignKey('agent_rollouts.id'), nullable=False),
        sa.Column('batch_num', sa.Integer(), nullable=False),
        sa.Column('percentage', sa.Integer(), nullable=False, server_default='25'),
        sa.Column('agent_serials', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='pending'),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('agents_total', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('agents_updated', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('agents_failed', sa.Integer(), nullable=False, server_default='0'),
    )
    op.create_index('ix_agent_rollout_batches_rollout_id', 'agent_rollout_batches', ['rollout_id'])


def downgrade():
    op.drop_table('agent_rollout_batches')
    op.drop_table('agent_rollouts')
