"""add reliability runs

Revision ID: 019_reliability_runs
Revises: 018_logs_investigation_productization
Create Date: 2026-04-08
"""

from alembic import op
import sqlalchemy as sa


revision = '019_reliability_runs'
down_revision = '018_logs_investigation_productization'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'reliability_runs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('diagnostic_type', sa.String(length=64), nullable=False),
        sa.Column('host_name', sa.String(length=255), nullable=False),
        sa.Column('dump_name', sa.String(length=255), nullable=True),
        sa.Column('adapter', sa.String(length=32), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('error_reason', sa.String(length=64), nullable=True),
        sa.Column('request_payload', sa.JSON(), nullable=False),
        sa.Column('result_payload', sa.JSON(), nullable=True),
        sa.Column('summary', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_reliability_runs_organization_id'), 'reliability_runs', ['organization_id'], unique=False)
    op.create_index(op.f('ix_reliability_runs_diagnostic_type'), 'reliability_runs', ['diagnostic_type'], unique=False)
    op.create_index(op.f('ix_reliability_runs_host_name'), 'reliability_runs', ['host_name'], unique=False)
    op.create_index(op.f('ix_reliability_runs_dump_name'), 'reliability_runs', ['dump_name'], unique=False)
    op.create_index(op.f('ix_reliability_runs_adapter'), 'reliability_runs', ['adapter'], unique=False)
    op.create_index(op.f('ix_reliability_runs_status'), 'reliability_runs', ['status'], unique=False)
    op.create_index(op.f('ix_reliability_runs_error_reason'), 'reliability_runs', ['error_reason'], unique=False)
    op.create_index(op.f('ix_reliability_runs_created_at'), 'reliability_runs', ['created_at'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_reliability_runs_created_at'), table_name='reliability_runs')
    op.drop_index(op.f('ix_reliability_runs_error_reason'), table_name='reliability_runs')
    op.drop_index(op.f('ix_reliability_runs_status'), table_name='reliability_runs')
    op.drop_index(op.f('ix_reliability_runs_adapter'), table_name='reliability_runs')
    op.drop_index(op.f('ix_reliability_runs_dump_name'), table_name='reliability_runs')
    op.drop_index(op.f('ix_reliability_runs_host_name'), table_name='reliability_runs')
    op.drop_index(op.f('ix_reliability_runs_diagnostic_type'), table_name='reliability_runs')
    op.drop_index(op.f('ix_reliability_runs_organization_id'), table_name='reliability_runs')
    op.drop_table('reliability_runs')
