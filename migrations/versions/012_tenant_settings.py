"""add tenant settings table

Revision ID: 012_tenant_settings
Revises: 011_agents_tenant_secrets_and_supportability
Create Date: 2026-03-31 00:00:02.000000
"""

from alembic import op
import sqlalchemy as sa


revision = '012_tenant_settings'
down_revision = '011_agents_tenant_secrets_and_supportability'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'tenant_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('notification_settings', sa.JSON(), nullable=False),
        sa.Column('retention_settings', sa.JSON(), nullable=False),
        sa.Column('branding_settings', sa.JSON(), nullable=False),
        sa.Column('auth_policy', sa.JSON(), nullable=False),
        sa.Column('feature_flags', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id'),
    )
    op.create_index(op.f('ix_tenant_settings_organization_id'), 'tenant_settings', ['organization_id'], unique=True)


def downgrade():
    op.drop_index(op.f('ix_tenant_settings_organization_id'), table_name='tenant_settings')
    op.drop_table('tenant_settings')
