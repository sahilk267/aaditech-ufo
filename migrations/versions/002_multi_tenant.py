"""Add multi-tenant support with organizations table

Revision ID: 002_multi_tenant
Revises: 001_initial
Create Date: 2026-03-16 22:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002_multi_tenant'
down_revision = '001_initial'
branch_labels = None
depends_on = None


def upgrade():
    """Create organizations and connect system_data to tenant context."""
    op.create_table(
        'organizations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug')
    )
    op.create_index('ix_organizations_slug', 'organizations', ['slug'], unique=True)

    op.add_column('system_data', sa.Column('organization_id', sa.Integer(), nullable=True))
    op.create_index('ix_system_data_organization_id', 'system_data', ['organization_id'], unique=False)

    # Seed a default organization and map existing rows to it.
    op.execute(
        """
        INSERT INTO organizations (name, slug, is_active, created_at, updated_at)
        VALUES ('Default Organization', 'default', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """
    )
    op.execute(
        """
        UPDATE system_data
        SET organization_id = (
            SELECT id FROM organizations WHERE slug = 'default' LIMIT 1
        )
        WHERE organization_id IS NULL
        """
    )


def downgrade():
    """Remove multi-tenant schema additions."""
    op.drop_index('ix_system_data_organization_id', table_name='system_data')
    op.drop_column('system_data', 'organization_id')

    op.drop_index('ix_organizations_slug', table_name='organizations')
    op.drop_table('organizations')
