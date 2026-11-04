"""rename users.supabase_user_id to auth_user_id, add auth_provider

Revision ID: eb75e962841f
Revises: b53a6a0a6ddf
Create Date: 2026-09-23 14:33:12.143157

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'eb75e962841f'
down_revision = 'b53a6a0a6ddf'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_supabase_user_id'))
        batch_op.alter_column(
            'supabase_user_id', new_column_name='auth_user_id',
            existing_type=sa.String(length=64), existing_nullable=False,
        )
        batch_op.add_column(
            sa.Column('auth_provider', sa.String(length=20), nullable=False, server_default='supabase')
        )
        batch_op.create_index(batch_op.f('ix_users_auth_user_id'), ['auth_user_id'], unique=True)

    # Drop the server_default now that every existing row is backfilled — new rows set
    # it explicitly going forward (see app/auth/service.py's resolve_user_from_token).
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('auth_provider', server_default=None)


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_auth_user_id'))
        batch_op.drop_column('auth_provider')
        batch_op.alter_column(
            'auth_user_id', new_column_name='supabase_user_id',
            existing_type=sa.String(length=64), existing_nullable=False,
        )
        batch_op.create_index(batch_op.f('ix_users_supabase_user_id'), ['supabase_user_id'], unique=True)
