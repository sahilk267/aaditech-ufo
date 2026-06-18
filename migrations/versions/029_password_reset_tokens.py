"""Add password reset token fields to users table.

Revision ID: 029
Revises: 028_agent_rollouts
Create Date: 2026-06-18
"""

from alembic import op
import sqlalchemy as sa

revision = '029'
down_revision = '028_agent_rollouts'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('password_reset_token', sa.String(255), nullable=True))
        batch_op.add_column(sa.Column('password_reset_expires_at', sa.DateTime(), nullable=True))

    op.create_index(
        'ix_users_password_reset_token',
        'users',
        ['password_reset_token'],
        unique=False,
    )


def downgrade():
    op.drop_index('ix_users_password_reset_token', table_name='users')
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('password_reset_expires_at')
        batch_op.drop_column('password_reset_token')
