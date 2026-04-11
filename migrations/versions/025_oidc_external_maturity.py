"""add oidc external maturity fields

Revision ID: 025_oidc_external_maturity
Revises: 024_log_investigations
Create Date: 2026-04-10
"""

from alembic import op
import sqlalchemy as sa


revision = '025_oidc_external_maturity'
down_revision = '024_log_investigations'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('tenant_oidc_providers', sa.Column('discovery_endpoint', sa.String(length=500), nullable=True))
    op.add_column('tenant_oidc_providers', sa.Column('jwks_uri', sa.String(length=500), nullable=True))
    op.add_column('tenant_oidc_providers', sa.Column('end_session_endpoint', sa.String(length=500), nullable=True))
    op.add_column('tenant_oidc_providers', sa.Column('last_discovery_status', sa.String(length=32), nullable=True))
    op.add_column('tenant_oidc_providers', sa.Column('last_auth_status', sa.String(length=32), nullable=True))
    op.add_column('tenant_oidc_providers', sa.Column('last_error', sa.Text(), nullable=True))
    op.add_column('tenant_oidc_providers', sa.Column('last_discovery_at', sa.DateTime(), nullable=True))
    op.add_column('tenant_oidc_providers', sa.Column('last_auth_at', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('tenant_oidc_providers', 'last_auth_at')
    op.drop_column('tenant_oidc_providers', 'last_discovery_at')
    op.drop_column('tenant_oidc_providers', 'last_error')
    op.drop_column('tenant_oidc_providers', 'last_auth_status')
    op.drop_column('tenant_oidc_providers', 'last_discovery_status')
    op.drop_column('tenant_oidc_providers', 'end_session_endpoint')
    op.drop_column('tenant_oidc_providers', 'jwks_uri')
    op.drop_column('tenant_oidc_providers', 'discovery_endpoint')
