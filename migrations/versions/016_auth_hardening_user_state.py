"""add auth hardening user state

Revision ID: 016_auth_hardening_user_state
Revises: 015_tenant_controls
Create Date: 2026-04-02
"""

from alembic import op
import sqlalchemy as sa


revision = '016_auth_hardening_user_state'
down_revision = '015_tenant_controls'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('failed_login_attempts', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('locked_until', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('last_login_at', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('auth_token_version', sa.Integer(), nullable=False, server_default='1'))
    op.create_index(op.f('ix_users_locked_until'), 'users', ['locked_until'], unique=False)
    op.create_index(op.f('ix_users_last_login_at'), 'users', ['last_login_at'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_users_last_login_at'), table_name='users')
    op.drop_index(op.f('ix_users_locked_until'), table_name='users')
    op.drop_column('users', 'auth_token_version')
    op.drop_column('users', 'last_login_at')
    op.drop_column('users', 'locked_until')
    op.drop_column('users', 'failed_login_attempts')
