"""add tenant quotas and usage metrics

Revision ID: 022_tenant_quotas_and_usage_metrics
Revises: 021_tenant_oidc_providers
Create Date: 2026-04-09 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = '022_tenant_quotas_and_usage_metrics'
down_revision = '021_tenant_oidc_providers'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'tenant_quota_policies',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('quota_key', sa.String(length=64), nullable=False),
        sa.Column('limit_value', sa.Integer(), nullable=True),
        sa.Column('is_enforced', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'quota_key', name='uq_tenant_quota_policies_org_key'),
    )
    op.create_index(op.f('ix_tenant_quota_policies_organization_id'), 'tenant_quota_policies', ['organization_id'], unique=False)
    op.create_index(op.f('ix_tenant_quota_policies_quota_key'), 'tenant_quota_policies', ['quota_key'], unique=False)
    op.create_index(op.f('ix_tenant_quota_policies_is_enforced'), 'tenant_quota_policies', ['is_enforced'], unique=False)

    op.create_table(
        'tenant_usage_metrics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('metric_key', sa.String(length=64), nullable=False),
        sa.Column('current_value', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('measured_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'metric_key', name='uq_tenant_usage_metrics_org_key'),
    )
    op.create_index(op.f('ix_tenant_usage_metrics_organization_id'), 'tenant_usage_metrics', ['organization_id'], unique=False)
    op.create_index(op.f('ix_tenant_usage_metrics_metric_key'), 'tenant_usage_metrics', ['metric_key'], unique=False)
    op.create_index(op.f('ix_tenant_usage_metrics_measured_at'), 'tenant_usage_metrics', ['measured_at'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_tenant_usage_metrics_measured_at'), table_name='tenant_usage_metrics')
    op.drop_index(op.f('ix_tenant_usage_metrics_metric_key'), table_name='tenant_usage_metrics')
    op.drop_index(op.f('ix_tenant_usage_metrics_organization_id'), table_name='tenant_usage_metrics')
    op.drop_table('tenant_usage_metrics')

    op.drop_index(op.f('ix_tenant_quota_policies_is_enforced'), table_name='tenant_quota_policies')
    op.drop_index(op.f('ix_tenant_quota_policies_quota_key'), table_name='tenant_quota_policies')
    op.drop_index(op.f('ix_tenant_quota_policies_organization_id'), table_name='tenant_quota_policies')
    op.drop_table('tenant_quota_policies')
