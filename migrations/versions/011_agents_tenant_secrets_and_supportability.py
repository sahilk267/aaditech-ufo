"""add agents tenant secrets and supportability foundations

Revision ID: 011_agents_tenant_secrets_and_supportability
Revises: 010_incidents_workflow_runs_and_delivery_history
Create Date: 2026-03-31 00:00:01.000000
"""

from alembic import op
import sqlalchemy as sa


revision = '011_agents_tenant_secrets_and_supportability'
down_revision = '010_incidents_workflow_runs_and_delivery_history'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'agents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('display_name', sa.String(length=255), nullable=False),
        sa.Column('hostname', sa.String(length=255), nullable=False),
        sa.Column('serial_number', sa.String(length=255), nullable=False),
        sa.Column('platform', sa.String(length=64), nullable=False),
        sa.Column('agent_version', sa.String(length=64), nullable=True),
        sa.Column('enrollment_state', sa.String(length=32), nullable=False),
        sa.Column('trust_state', sa.String(length=32), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(), nullable=True),
        sa.Column('last_ip', sa.String(length=64), nullable=True),
        sa.Column('credential_rotated_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'serial_number', name='uq_agents_org_serial_number'),
    )
    op.create_index(op.f('ix_agents_enrollment_state'), 'agents', ['enrollment_state'], unique=False)
    op.create_index(op.f('ix_agents_hostname'), 'agents', ['hostname'], unique=False)
    op.create_index(op.f('ix_agents_last_seen_at'), 'agents', ['last_seen_at'], unique=False)
    op.create_index(op.f('ix_agents_organization_id'), 'agents', ['organization_id'], unique=False)
    op.create_index(op.f('ix_agents_serial_number'), 'agents', ['serial_number'], unique=False)
    op.create_index(op.f('ix_agents_trust_state'), 'agents', ['trust_state'], unique=False)

    op.create_table(
        'agent_credentials',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('agent_id', sa.Integer(), nullable=False),
        sa.Column('credential_fingerprint', sa.String(length=128), nullable=False),
        sa.Column('issued_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.Column('rotation_reason', sa.String(length=128), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_agent_credentials_agent_id'), 'agent_credentials', ['agent_id'], unique=False)
    op.create_index(op.f('ix_agent_credentials_credential_fingerprint'), 'agent_credentials', ['credential_fingerprint'], unique=True)
    op.create_index(op.f('ix_agent_credentials_expires_at'), 'agent_credentials', ['expires_at'], unique=False)
    op.create_index(op.f('ix_agent_credentials_revoked_at'), 'agent_credentials', ['revoked_at'], unique=False)
    op.create_index(op.f('ix_agent_credentials_status'), 'agent_credentials', ['status'], unique=False)

    op.create_table(
        'agent_enrollment_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('token_fingerprint', sa.String(length=128), nullable=False),
        sa.Column('intended_hostname_pattern', sa.String(length=255), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('used_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_agent_enrollment_tokens_created_by_user_id'), 'agent_enrollment_tokens', ['created_by_user_id'], unique=False)
    op.create_index(op.f('ix_agent_enrollment_tokens_expires_at'), 'agent_enrollment_tokens', ['expires_at'], unique=False)
    op.create_index(op.f('ix_agent_enrollment_tokens_organization_id'), 'agent_enrollment_tokens', ['organization_id'], unique=False)
    op.create_index(op.f('ix_agent_enrollment_tokens_status'), 'agent_enrollment_tokens', ['status'], unique=False)
    op.create_index(op.f('ix_agent_enrollment_tokens_token_fingerprint'), 'agent_enrollment_tokens', ['token_fingerprint'], unique=True)

    op.create_table(
        'tenant_secrets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('secret_type', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('ciphertext', sa.Text(), nullable=False),
        sa.Column('key_version', sa.String(length=32), nullable=False),
        sa.Column('rotated_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'secret_type', 'name', name='uq_tenant_secrets_org_type_name'),
    )
    op.create_index(op.f('ix_tenant_secrets_created_by_user_id'), 'tenant_secrets', ['created_by_user_id'], unique=False)
    op.create_index(op.f('ix_tenant_secrets_expires_at'), 'tenant_secrets', ['expires_at'], unique=False)
    op.create_index(op.f('ix_tenant_secrets_last_used_at'), 'tenant_secrets', ['last_used_at'], unique=False)
    op.create_index(op.f('ix_tenant_secrets_organization_id'), 'tenant_secrets', ['organization_id'], unique=False)
    op.create_index(op.f('ix_tenant_secrets_secret_type'), 'tenant_secrets', ['secret_type'], unique=False)
    op.create_index(op.f('ix_tenant_secrets_status'), 'tenant_secrets', ['status'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_tenant_secrets_status'), table_name='tenant_secrets')
    op.drop_index(op.f('ix_tenant_secrets_secret_type'), table_name='tenant_secrets')
    op.drop_index(op.f('ix_tenant_secrets_organization_id'), table_name='tenant_secrets')
    op.drop_index(op.f('ix_tenant_secrets_last_used_at'), table_name='tenant_secrets')
    op.drop_index(op.f('ix_tenant_secrets_expires_at'), table_name='tenant_secrets')
    op.drop_index(op.f('ix_tenant_secrets_created_by_user_id'), table_name='tenant_secrets')
    op.drop_table('tenant_secrets')

    op.drop_index(op.f('ix_agent_enrollment_tokens_token_fingerprint'), table_name='agent_enrollment_tokens')
    op.drop_index(op.f('ix_agent_enrollment_tokens_status'), table_name='agent_enrollment_tokens')
    op.drop_index(op.f('ix_agent_enrollment_tokens_organization_id'), table_name='agent_enrollment_tokens')
    op.drop_index(op.f('ix_agent_enrollment_tokens_expires_at'), table_name='agent_enrollment_tokens')
    op.drop_index(op.f('ix_agent_enrollment_tokens_created_by_user_id'), table_name='agent_enrollment_tokens')
    op.drop_table('agent_enrollment_tokens')

    op.drop_index(op.f('ix_agent_credentials_status'), table_name='agent_credentials')
    op.drop_index(op.f('ix_agent_credentials_revoked_at'), table_name='agent_credentials')
    op.drop_index(op.f('ix_agent_credentials_expires_at'), table_name='agent_credentials')
    op.drop_index(op.f('ix_agent_credentials_credential_fingerprint'), table_name='agent_credentials')
    op.drop_index(op.f('ix_agent_credentials_agent_id'), table_name='agent_credentials')
    op.drop_table('agent_credentials')

    op.drop_index(op.f('ix_agents_trust_state'), table_name='agents')
    op.drop_index(op.f('ix_agents_serial_number'), table_name='agents')
    op.drop_index(op.f('ix_agents_organization_id'), table_name='agents')
    op.drop_index(op.f('ix_agents_last_seen_at'), table_name='agents')
    op.drop_index(op.f('ix_agents_hostname'), table_name='agents')
    op.drop_index(op.f('ix_agents_enrollment_state'), table_name='agents')
    op.drop_table('agents')
