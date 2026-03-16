"""Initial migration - Create SystemData table

Revision ID: 001_initial
Revises: 
Create Date: 2026-03-16 21:57:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Create initial database schema"""
    op.create_table(
        'system_data',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('serial_number', sa.String(length=255), nullable=False),
        sa.Column('hostname', sa.String(length=255), nullable=False),
        sa.Column('model_number', sa.String(length=255), nullable=True),
        sa.Column('ip_address', sa.String(length=20), nullable=True),
        sa.Column('local_ip', sa.String(length=20), nullable=True),
        sa.Column('public_ip', sa.String(length=20), nullable=True),
        sa.Column('system_info', sa.JSON(), nullable=True),
        sa.Column('cpu_usage', sa.Float(), nullable=True),
        sa.Column('cpu_per_core', sa.JSON(), nullable=True),
        sa.Column('cpu_frequency', sa.JSON(), nullable=True),
        sa.Column('cpu_info', sa.String(length=255), nullable=True),
        sa.Column('cpu_cores', sa.Integer(), nullable=True),
        sa.Column('cpu_threads', sa.Integer(), nullable=True),
        sa.Column('ram_usage', sa.Float(), nullable=True),
        sa.Column('ram_info', sa.JSON(), nullable=True),
        sa.Column('disk_info', sa.JSON(), nullable=True),
        sa.Column('storage_usage', sa.Float(), nullable=True),
        sa.Column('software_benchmark', sa.Float(), nullable=True),
        sa.Column('hardware_benchmark', sa.Float(), nullable=True),
        sa.Column('overall_benchmark', sa.Float(), nullable=True),
        sa.Column('benchmark_results', sa.JSON(), nullable=True),
        sa.Column('performance_metrics', sa.JSON(), nullable=True),
        sa.Column('last_update', sa.DateTime(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('current_user', sa.String(length=255), nullable=True),
        sa.Column('deleted', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for better query performance
    op.create_index(op.f('ix_system_data_serial_number'), 'system_data', ['serial_number'], unique=False)
    op.create_index(op.f('ix_system_data_last_update'), 'system_data', ['last_update'], unique=False)


def downgrade():
    """Rollback initial schema"""
    op.drop_index(op.f('ix_system_data_last_update'), table_name='system_data')
    op.drop_index(op.f('ix_system_data_serial_number'), table_name='system_data')
    op.drop_table('system_data')
