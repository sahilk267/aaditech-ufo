"""add agent_sessions table

Revision ID: 027_agent_sessions
Revises: 026_agent_commands_and_pins
Create Date: 2026-05-03
"""

from alembic import op
import sqlalchemy as sa


revision = '027_agent_sessions'
down_revision = '026_agent_commands_and_pins'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'agent_sessions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id'), nullable=False),
        sa.Column('session_id', sa.String(length=64), nullable=False),
        sa.Column('request_text', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='pending'),
        sa.Column('plan_steps', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('step_outputs', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('final_result', sa.JSON(), nullable=True),
        sa.Column('error_reason', sa.String(length=64), nullable=True),
        sa.Column('metadata_payload', sa.JSON(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_agent_sessions_organization_id', 'agent_sessions', ['organization_id'])
    op.create_index('ix_agent_sessions_session_id', 'agent_sessions', ['session_id'], unique=True)
    op.create_index('ix_agent_sessions_status', 'agent_sessions', ['status'])
    op.create_index('ix_agent_sessions_created_at', 'agent_sessions', ['created_at'])


def downgrade():
    op.drop_index('ix_agent_sessions_created_at', table_name='agent_sessions')
    op.drop_index('ix_agent_sessions_status', table_name='agent_sessions')
    op.drop_index('ix_agent_sessions_session_id', table_name='agent_sessions')
    op.drop_index('ix_agent_sessions_organization_id', table_name='agent_sessions')
    op.drop_table('agent_sessions')
