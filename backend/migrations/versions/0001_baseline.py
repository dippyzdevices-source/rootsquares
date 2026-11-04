"""baseline

Revision ID: 0001
Revises:
Create Date: 2026-10-09 22:22:27.442927
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('audit_log',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('actor_user_id', sa.Uuid(), nullable=True),
    sa.Column('org_id', sa.Uuid(), nullable=True),
    sa.Column('action', sa.String(length=80), nullable=False),
    sa.Column('entity', sa.String(length=40), nullable=False),
    sa.Column('entity_id', sa.String(length=80), nullable=False),
    sa.Column('request_id', sa.String(length=64), nullable=True),
    sa.Column('data', sa.JSON(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_log_action'), 'audit_log', ['action'], unique=False)
    op.create_index(op.f('ix_audit_log_at'), 'audit_log', ['at'], unique=False)
    op.create_table('organizations',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('users',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('email', sa.String(length=320), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=True),
    sa.Column('auth_user_id', sa.String(length=255), nullable=True),
    sa.Column('auth_provider', sa.String(length=20), nullable=True),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('is_platform_admin', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('auth_user_id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_table('auth_sessions',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('refresh_jti', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_auth_sessions_user_id'), 'auth_sessions', ['user_id'], unique=False)
    op.create_table('memberships',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('org_id', sa.Uuid(), nullable=False),
    sa.Column('role', sa.Enum('owner', name='membership_role'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'org_id')
    )
    op.create_index(op.f('ix_memberships_org_id'), 'memberships', ['org_id'], unique=False)
    op.create_index(op.f('ix_memberships_user_id'), 'memberships', ['user_id'], unique=False)
    op.create_table('squares',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('org_id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('slug', sa.String(length=40), nullable=False),
    sa.Column('theme_id', sa.String(length=60), nullable=False),
    sa.Column('status', sa.Enum('provisioning', 'ready', 'failed', name='square_status'), nullable=False),
    sa.Column('domain', sa.String(length=255), nullable=False),
    sa.Column('db_connection', sa.Text(), nullable=True),
    sa.Column('neon_project_id', sa.String(length=100), nullable=True),
    sa.Column('provider_project_ref', sa.String(length=100), nullable=True),
    sa.Column('provider', sa.String(length=20), nullable=True),
    sa.Column('google_login', sa.String(length=20), nullable=True),
    sa.Column('provider_secrets', sa.Text(), nullable=True),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('suspended_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_squares_org_id'), 'squares', ['org_id'], unique=False)
    op.create_index(op.f('ix_squares_slug'), 'squares', ['slug'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_squares_slug'), table_name='squares')
    op.drop_index(op.f('ix_squares_org_id'), table_name='squares')
    op.drop_table('squares')
    op.drop_index(op.f('ix_memberships_user_id'), table_name='memberships')
    op.drop_index(op.f('ix_memberships_org_id'), table_name='memberships')
    op.drop_table('memberships')
    op.drop_index(op.f('ix_auth_sessions_user_id'), table_name='auth_sessions')
    op.drop_table('auth_sessions')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
    op.drop_table('organizations')
    op.drop_index(op.f('ix_audit_log_at'), table_name='audit_log')
    op.drop_index(op.f('ix_audit_log_action'), table_name='audit_log')
    op.drop_table('audit_log')
    sa.Enum(name='square_status').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='membership_role').drop(op.get_bind(), checkfirst=True)
