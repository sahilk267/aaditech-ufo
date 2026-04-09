"""add log source investigation metadata

Revision ID: 018_logs_investigation_productization
Revises: 017_user_totp_factors
Create Date: 2026-04-07
"""

from alembic import op
import sqlalchemy as sa


revision = '018_logs_investigation_productization'
down_revision = '017_user_totp_factors'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('log_sources', schema=None) as batch_op:
        batch_op.add_column(sa.Column('description', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('host_name', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()))
        batch_op.add_column(sa.Column('source_metadata', sa.JSON(), nullable=True))
        batch_op.create_index(batch_op.f('ix_log_sources_host_name'), ['host_name'], unique=False)
        batch_op.create_index(batch_op.f('ix_log_sources_is_active'), ['is_active'], unique=False)

    op.execute("UPDATE log_sources SET is_active = 1 WHERE is_active IS NULL")

    with op.batch_alter_table('log_sources', schema=None) as batch_op:
        batch_op.alter_column('is_active', server_default=None)


def downgrade():
    with op.batch_alter_table('log_sources', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_log_sources_is_active'))
        batch_op.drop_index(batch_op.f('ix_log_sources_host_name'))
        batch_op.drop_column('source_metadata')
        batch_op.drop_column('is_active')
        batch_op.drop_column('host_name')
        batch_op.drop_column('description')
