"""add log investigations

Revision ID: 024_log_investigations
Revises: 023_tenant_commercial_models
Create Date: 2026-04-10 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = '024_log_investigations'
down_revision = '023_tenant_commercial_models'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'log_investigations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(length=160), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('source_name', sa.String(length=128), nullable=True),
        sa.Column('pinned_source_id', sa.Integer(), nullable=True),
        sa.Column('pinned_entry_id', sa.Integer(), nullable=True),
        sa.Column('filter_snapshot', sa.JSON(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('last_result_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_matched_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['pinned_entry_id'], ['log_entries.id']),
        sa.ForeignKeyConstraint(['pinned_source_id'], ['log_sources.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'name', name='uq_log_investigations_org_name'),
    )
    op.create_index(op.f('ix_log_investigations_organization_id'), 'log_investigations', ['organization_id'], unique=False)
    op.create_index(op.f('ix_log_investigations_created_by_user_id'), 'log_investigations', ['created_by_user_id'], unique=False)
    op.create_index(op.f('ix_log_investigations_status'), 'log_investigations', ['status'], unique=False)
    op.create_index(op.f('ix_log_investigations_source_name'), 'log_investigations', ['source_name'], unique=False)
    op.create_index(op.f('ix_log_investigations_pinned_source_id'), 'log_investigations', ['pinned_source_id'], unique=False)
    op.create_index(op.f('ix_log_investigations_pinned_entry_id'), 'log_investigations', ['pinned_entry_id'], unique=False)
    op.create_index(op.f('ix_log_investigations_last_matched_at'), 'log_investigations', ['last_matched_at'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_log_investigations_last_matched_at'), table_name='log_investigations')
    op.drop_index(op.f('ix_log_investigations_pinned_entry_id'), table_name='log_investigations')
    op.drop_index(op.f('ix_log_investigations_pinned_source_id'), table_name='log_investigations')
    op.drop_index(op.f('ix_log_investigations_source_name'), table_name='log_investigations')
    op.drop_index(op.f('ix_log_investigations_status'), table_name='log_investigations')
    op.drop_index(op.f('ix_log_investigations_created_by_user_id'), table_name='log_investigations')
    op.drop_index(op.f('ix_log_investigations_organization_id'), table_name='log_investigations')
    op.drop_table('log_investigations')
