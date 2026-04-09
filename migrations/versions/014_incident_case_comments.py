"""add incident case comments

Revision ID: 014_incident_case_comments
Revises: 013_incident_operator_fields
Create Date: 2026-04-01
"""

from alembic import op
import sqlalchemy as sa


revision = '014_incident_case_comments'
down_revision = '013_incident_operator_fields'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'incident_case_comments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('incident_id', sa.Integer(), nullable=False),
        sa.Column('author_user_id', sa.Integer(), nullable=True),
        sa.Column('comment_type', sa.String(length=32), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['author_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['incident_id'], ['incident_records.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_incident_case_comments_organization_id'), 'incident_case_comments', ['organization_id'], unique=False)
    op.create_index(op.f('ix_incident_case_comments_incident_id'), 'incident_case_comments', ['incident_id'], unique=False)
    op.create_index(op.f('ix_incident_case_comments_author_user_id'), 'incident_case_comments', ['author_user_id'], unique=False)
    op.create_index(op.f('ix_incident_case_comments_comment_type'), 'incident_case_comments', ['comment_type'], unique=False)
    op.create_index(op.f('ix_incident_case_comments_created_at'), 'incident_case_comments', ['created_at'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_incident_case_comments_created_at'), table_name='incident_case_comments')
    op.drop_index(op.f('ix_incident_case_comments_comment_type'), table_name='incident_case_comments')
    op.drop_index(op.f('ix_incident_case_comments_author_user_id'), table_name='incident_case_comments')
    op.drop_index(op.f('ix_incident_case_comments_incident_id'), table_name='incident_case_comments')
    op.drop_index(op.f('ix_incident_case_comments_organization_id'), table_name='incident_case_comments')
    op.drop_table('incident_case_comments')
