"""add log sources and entries

Revision ID: 009_log_sources_and_entries
Revises: 008_alert_silences_and_scheduled_jobs
Create Date: 2026-03-31 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '009_log_sources_and_entries'
down_revision = '008_alert_silences_and_scheduled_jobs'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'log_sources',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('adapter', sa.String(length=32), nullable=False),
        sa.Column('last_ingested_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'name', name='uq_log_sources_org_name'),
    )
    op.create_index(op.f('ix_log_sources_last_ingested_at'), 'log_sources', ['last_ingested_at'], unique=False)
    op.create_index(op.f('ix_log_sources_organization_id'), 'log_sources', ['organization_id'], unique=False)

    op.create_table(
        'log_entries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('log_source_id', sa.Integer(), nullable=True),
        sa.Column('source_name', sa.String(length=128), nullable=False),
        sa.Column('adapter', sa.String(length=32), nullable=False),
        sa.Column('capture_kind', sa.String(length=32), nullable=False),
        sa.Column('observed_at', sa.DateTime(), nullable=True),
        sa.Column('severity', sa.String(length=20), nullable=True),
        sa.Column('event_id', sa.String(length=64), nullable=True),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('raw_entry', sa.Text(), nullable=False),
        sa.Column('entry_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['log_source_id'], ['log_sources.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_log_entries_capture_kind'), 'log_entries', ['capture_kind'], unique=False)
    op.create_index(op.f('ix_log_entries_created_at'), 'log_entries', ['created_at'], unique=False)
    op.create_index(op.f('ix_log_entries_event_id'), 'log_entries', ['event_id'], unique=False)
    op.create_index(op.f('ix_log_entries_log_source_id'), 'log_entries', ['log_source_id'], unique=False)
    op.create_index(op.f('ix_log_entries_observed_at'), 'log_entries', ['observed_at'], unique=False)
    op.create_index(op.f('ix_log_entries_organization_id'), 'log_entries', ['organization_id'], unique=False)
    op.create_index(op.f('ix_log_entries_severity'), 'log_entries', ['severity'], unique=False)
    op.create_index(op.f('ix_log_entries_source_name'), 'log_entries', ['source_name'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_log_entries_source_name'), table_name='log_entries')
    op.drop_index(op.f('ix_log_entries_severity'), table_name='log_entries')
    op.drop_index(op.f('ix_log_entries_organization_id'), table_name='log_entries')
    op.drop_index(op.f('ix_log_entries_observed_at'), table_name='log_entries')
    op.drop_index(op.f('ix_log_entries_log_source_id'), table_name='log_entries')
    op.drop_index(op.f('ix_log_entries_event_id'), table_name='log_entries')
    op.drop_index(op.f('ix_log_entries_created_at'), table_name='log_entries')
    op.drop_index(op.f('ix_log_entries_capture_kind'), table_name='log_entries')
    op.drop_table('log_entries')

    op.drop_index(op.f('ix_log_sources_organization_id'), table_name='log_sources')
    op.drop_index(op.f('ix_log_sources_last_ingested_at'), table_name='log_sources')
    op.drop_table('log_sources')
