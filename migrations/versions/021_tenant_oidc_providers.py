"""add tenant oidc providers

Revision ID: 021_tenant_oidc_providers
Revises: 020_update_runs
Create Date: 2026-04-09
"""

from alembic import op
import sqlalchemy as sa


revision = '021_tenant_oidc_providers'
down_revision = '020_update_runs'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'tenant_oidc_providers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('issuer', sa.String(length=255), nullable=False),
        sa.Column('client_id', sa.String(length=255), nullable=False),
        sa.Column('client_secret_secret_name', sa.String(length=255), nullable=True),
        sa.Column('authorization_endpoint', sa.String(length=500), nullable=False),
        sa.Column('token_endpoint', sa.String(length=500), nullable=True),
        sa.Column('userinfo_endpoint', sa.String(length=500), nullable=True),
        sa.Column('scopes', sa.JSON(), nullable=False),
        sa.Column('claim_mappings', sa.JSON(), nullable=False),
        sa.Column('role_mappings', sa.JSON(), nullable=False),
        sa.Column('test_mode', sa.Boolean(), nullable=False),
        sa.Column('test_claims', sa.JSON(), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), nullable=False),
        sa.Column('is_default', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'name', name='uq_tenant_oidc_providers_org_name'),
    )
    op.create_index(op.f('ix_tenant_oidc_providers_organization_id'), 'tenant_oidc_providers', ['organization_id'], unique=False)
    op.create_index(op.f('ix_tenant_oidc_providers_is_enabled'), 'tenant_oidc_providers', ['is_enabled'], unique=False)
    op.create_index(op.f('ix_tenant_oidc_providers_is_default'), 'tenant_oidc_providers', ['is_default'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_tenant_oidc_providers_is_default'), table_name='tenant_oidc_providers')
    op.drop_index(op.f('ix_tenant_oidc_providers_is_enabled'), table_name='tenant_oidc_providers')
    op.drop_index(op.f('ix_tenant_oidc_providers_organization_id'), table_name='tenant_oidc_providers')
    op.drop_table('tenant_oidc_providers')
