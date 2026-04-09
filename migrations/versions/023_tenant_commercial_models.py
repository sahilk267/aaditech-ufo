"""add tenant commercial models

Revision ID: 023_tenant_commercial_models
Revises: 022_tenant_quotas_and_usage_metrics
Create Date: 2026-04-09 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = '023_tenant_commercial_models'
down_revision = '022_tenant_quotas_and_usage_metrics'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'tenant_plans',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('plan_key', sa.String(length=64), nullable=False),
        sa.Column('display_name', sa.String(length=120), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('billing_cycle', sa.String(length=32), nullable=True),
        sa.Column('effective_from', sa.DateTime(), nullable=True),
        sa.Column('external_customer_ref', sa.String(length=128), nullable=True),
        sa.Column('external_subscription_ref', sa.String(length=128), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id'),
    )
    op.create_index(op.f('ix_tenant_plans_organization_id'), 'tenant_plans', ['organization_id'], unique=True)
    op.create_index(op.f('ix_tenant_plans_status'), 'tenant_plans', ['status'], unique=False)
    op.create_index(op.f('ix_tenant_plans_external_customer_ref'), 'tenant_plans', ['external_customer_ref'], unique=False)
    op.create_index(op.f('ix_tenant_plans_external_subscription_ref'), 'tenant_plans', ['external_subscription_ref'], unique=False)

    op.create_table(
        'tenant_billing_profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('billing_email', sa.String(length=255), nullable=True),
        sa.Column('billing_name', sa.String(length=255), nullable=True),
        sa.Column('contact_email', sa.String(length=255), nullable=True),
        sa.Column('country_code', sa.String(length=8), nullable=True),
        sa.Column('provider_name', sa.String(length=64), nullable=True),
        sa.Column('provider_customer_ref', sa.String(length=128), nullable=True),
        sa.Column('tax_id_hint', sa.String(length=32), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id'),
    )
    op.create_index(op.f('ix_tenant_billing_profiles_organization_id'), 'tenant_billing_profiles', ['organization_id'], unique=True)
    op.create_index(op.f('ix_tenant_billing_profiles_provider_customer_ref'), 'tenant_billing_profiles', ['provider_customer_ref'], unique=False)

    op.create_table(
        'tenant_licenses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('license_status', sa.String(length=32), nullable=False),
        sa.Column('license_key_hint', sa.String(length=32), nullable=True),
        sa.Column('seat_limit', sa.Integer(), nullable=True),
        sa.Column('enforcement_mode', sa.String(length=32), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id'),
    )
    op.create_index(op.f('ix_tenant_licenses_organization_id'), 'tenant_licenses', ['organization_id'], unique=True)
    op.create_index(op.f('ix_tenant_licenses_license_status'), 'tenant_licenses', ['license_status'], unique=False)
    op.create_index(op.f('ix_tenant_licenses_expires_at'), 'tenant_licenses', ['expires_at'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_tenant_licenses_expires_at'), table_name='tenant_licenses')
    op.drop_index(op.f('ix_tenant_licenses_license_status'), table_name='tenant_licenses')
    op.drop_index(op.f('ix_tenant_licenses_organization_id'), table_name='tenant_licenses')
    op.drop_table('tenant_licenses')

    op.drop_index(op.f('ix_tenant_billing_profiles_provider_customer_ref'), table_name='tenant_billing_profiles')
    op.drop_index(op.f('ix_tenant_billing_profiles_organization_id'), table_name='tenant_billing_profiles')
    op.drop_table('tenant_billing_profiles')

    op.drop_index(op.f('ix_tenant_plans_external_subscription_ref'), table_name='tenant_plans')
    op.drop_index(op.f('ix_tenant_plans_external_customer_ref'), table_name='tenant_plans')
    op.drop_index(op.f('ix_tenant_plans_status'), table_name='tenant_plans')
    op.drop_index(op.f('ix_tenant_plans_organization_id'), table_name='tenant_plans')
    op.drop_table('tenant_plans')
