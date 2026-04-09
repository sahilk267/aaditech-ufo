"""add update runs

Revision ID: 020_update_runs
Revises: 019_reliability_runs
Create Date: 2026-04-08
"""

from alembic import op
import sqlalchemy as sa


revision = '020_update_runs'
down_revision = '019_reliability_runs'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'update_runs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('host_name', sa.String(length=255), nullable=False),
        sa.Column('adapter', sa.String(length=32), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('error_reason', sa.String(length=64), nullable=True),
        sa.Column('update_count', sa.Integer(), nullable=False),
        sa.Column('latest_installed_on', sa.String(length=32), nullable=True),
        sa.Column('updates_payload', sa.JSON(), nullable=True),
        sa.Column('summary', sa.JSON(), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('confidence_payload', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_update_runs_organization_id'), 'update_runs', ['organization_id'], unique=False)
    op.create_index(op.f('ix_update_runs_host_name'), 'update_runs', ['host_name'], unique=False)
    op.create_index(op.f('ix_update_runs_adapter'), 'update_runs', ['adapter'], unique=False)
    op.create_index(op.f('ix_update_runs_status'), 'update_runs', ['status'], unique=False)
    op.create_index(op.f('ix_update_runs_error_reason'), 'update_runs', ['error_reason'], unique=False)
    op.create_index(op.f('ix_update_runs_created_at'), 'update_runs', ['created_at'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_update_runs_created_at'), table_name='update_runs')
    op.drop_index(op.f('ix_update_runs_error_reason'), table_name='update_runs')
    op.drop_index(op.f('ix_update_runs_status'), table_name='update_runs')
    op.drop_index(op.f('ix_update_runs_adapter'), table_name='update_runs')
    op.drop_index(op.f('ix_update_runs_host_name'), table_name='update_runs')
    op.drop_index(op.f('ix_update_runs_organization_id'), table_name='update_runs')
    op.drop_table('update_runs')
