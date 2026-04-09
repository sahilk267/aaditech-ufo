"""add incident operator fields

Revision ID: 013_incident_operator_fields
Revises: 012_tenant_settings
Create Date: 2026-03-31
"""

from alembic import op
import sqlalchemy as sa


revision = '013_incident_operator_fields'
down_revision = '012_tenant_settings'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('incident_records', sa.Column('assigned_to_user_id', sa.Integer(), nullable=True))
    op.add_column('incident_records', sa.Column('acknowledged_at', sa.DateTime(), nullable=True))
    op.add_column('incident_records', sa.Column('resolution_summary', sa.String(length=1000), nullable=True))
    op.create_index(op.f('ix_incident_records_assigned_to_user_id'), 'incident_records', ['assigned_to_user_id'], unique=False)
    if op.get_bind().dialect.name != 'sqlite':
        op.create_foreign_key(
            'fk_incident_records_assigned_to_user_id_users',
            'incident_records',
            'users',
            ['assigned_to_user_id'],
            ['id'],
        )


def downgrade():
    if op.get_bind().dialect.name != 'sqlite':
        op.drop_constraint('fk_incident_records_assigned_to_user_id_users', 'incident_records', type_='foreignkey')
    op.drop_index(op.f('ix_incident_records_assigned_to_user_id'), table_name='incident_records')
    op.drop_column('incident_records', 'resolution_summary')
    op.drop_column('incident_records', 'acknowledged_at')
    op.drop_column('incident_records', 'assigned_to_user_id')
