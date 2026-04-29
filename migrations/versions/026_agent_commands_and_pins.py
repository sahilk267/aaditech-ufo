"""add agent_commands and agent_server_pins tables

Revision ID: 026_agent_commands_and_pins
Revises: 025_oidc_external_maturity
Create Date: 2026-04-29
"""

from alembic import op
import sqlalchemy as sa


revision = '026_agent_commands_and_pins'
down_revision = '025_oidc_external_maturity'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'agent_commands',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id'), nullable=False),
        sa.Column('agent_id', sa.Integer(), sa.ForeignKey('agents.id'), nullable=True),
        sa.Column('target_serial_number', sa.String(length=255), nullable=True),
        sa.Column('command_type', sa.String(length=64), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='pending'),
        sa.Column('result', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('requested_by_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('dispatched_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_agent_commands_organization_id', 'agent_commands', ['organization_id'])
    op.create_index('ix_agent_commands_agent_id', 'agent_commands', ['agent_id'])
    op.create_index('ix_agent_commands_target_serial_number', 'agent_commands', ['target_serial_number'])
    op.create_index('ix_agent_commands_status', 'agent_commands', ['status'])
    op.create_index('ix_agent_commands_command_type', 'agent_commands', ['command_type'])
    op.create_index('ix_agent_commands_created_at', 'agent_commands', ['created_at'])
    op.create_index('ix_agent_commands_expires_at', 'agent_commands', ['expires_at'])

    op.create_table(
        'agent_server_pins',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id'), nullable=False),
        sa.Column('cert_sha256', sa.String(length=128), nullable=False),
        sa.Column('label', sa.String(length=128), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('rotated_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_agent_server_pins_organization_id', 'agent_server_pins', ['organization_id'])
    op.create_index('ix_agent_server_pins_is_active', 'agent_server_pins', ['is_active'])


def downgrade():
    op.drop_index('ix_agent_server_pins_is_active', table_name='agent_server_pins')
    op.drop_index('ix_agent_server_pins_organization_id', table_name='agent_server_pins')
    op.drop_table('agent_server_pins')
    op.drop_index('ix_agent_commands_expires_at', table_name='agent_commands')
    op.drop_index('ix_agent_commands_created_at', table_name='agent_commands')
    op.drop_index('ix_agent_commands_command_type', table_name='agent_commands')
    op.drop_index('ix_agent_commands_status', table_name='agent_commands')
    op.drop_index('ix_agent_commands_target_serial_number', table_name='agent_commands')
    op.drop_index('ix_agent_commands_agent_id', table_name='agent_commands')
    op.drop_index('ix_agent_commands_organization_id', table_name='agent_commands')
    op.drop_table('agent_commands')
