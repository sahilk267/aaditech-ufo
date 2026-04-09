"""add user totp factors

Revision ID: 017_user_totp_factors
Revises: 016_auth_hardening_user_state
Create Date: 2026-04-02
"""

from alembic import op
import sqlalchemy as sa


revision = '017_user_totp_factors'
down_revision = '016_auth_hardening_user_state'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'user_totp_factors',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('secret_ciphertext', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('enrolled_at', sa.DateTime(), nullable=False),
        sa.Column('verified_at', sa.DateTime(), nullable=True),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.Column('disabled_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id'),
    )
    op.create_index(op.f('ix_user_totp_factors_user_id'), 'user_totp_factors', ['user_id'], unique=True)
    op.create_index(op.f('ix_user_totp_factors_organization_id'), 'user_totp_factors', ['organization_id'], unique=False)
    op.create_index(op.f('ix_user_totp_factors_status'), 'user_totp_factors', ['status'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_user_totp_factors_status'), table_name='user_totp_factors')
    op.drop_index(op.f('ix_user_totp_factors_organization_id'), table_name='user_totp_factors')
    op.drop_index(op.f('ix_user_totp_factors_user_id'), table_name='user_totp_factors')
    op.drop_table('user_totp_factors')
