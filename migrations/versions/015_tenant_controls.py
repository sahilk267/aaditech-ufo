"""add tenant entitlements and feature flags

Revision ID: 015_tenant_controls
Revises: 014_incident_case_comments
Create Date: 2026-04-02
"""

from alembic import op
import sqlalchemy as sa


revision = '015_tenant_controls'
down_revision = '014_incident_case_comments'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'tenant_entitlements',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('entitlement_key', sa.String(length=64), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), nullable=False),
        sa.Column('limit_value', sa.Integer(), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'entitlement_key', name='uq_tenant_entitlements_org_key'),
    )
    op.create_index(op.f('ix_tenant_entitlements_organization_id'), 'tenant_entitlements', ['organization_id'], unique=False)
    op.create_index(op.f('ix_tenant_entitlements_entitlement_key'), 'tenant_entitlements', ['entitlement_key'], unique=False)
    op.create_index(op.f('ix_tenant_entitlements_is_enabled'), 'tenant_entitlements', ['is_enabled'], unique=False)

    op.create_table(
        'tenant_feature_flags',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('flag_key', sa.String(length=64), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'flag_key', name='uq_tenant_feature_flags_org_key'),
    )
    op.create_index(op.f('ix_tenant_feature_flags_organization_id'), 'tenant_feature_flags', ['organization_id'], unique=False)
    op.create_index(op.f('ix_tenant_feature_flags_flag_key'), 'tenant_feature_flags', ['flag_key'], unique=False)
    op.create_index(op.f('ix_tenant_feature_flags_is_enabled'), 'tenant_feature_flags', ['is_enabled'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_tenant_feature_flags_is_enabled'), table_name='tenant_feature_flags')
    op.drop_index(op.f('ix_tenant_feature_flags_flag_key'), table_name='tenant_feature_flags')
    op.drop_index(op.f('ix_tenant_feature_flags_organization_id'), table_name='tenant_feature_flags')
    op.drop_table('tenant_feature_flags')

    op.drop_index(op.f('ix_tenant_entitlements_is_enabled'), table_name='tenant_entitlements')
    op.drop_index(op.f('ix_tenant_entitlements_entitlement_key'), table_name='tenant_entitlements')
    op.drop_index(op.f('ix_tenant_entitlements_organization_id'), table_name='tenant_entitlements')
    op.drop_table('tenant_entitlements')
