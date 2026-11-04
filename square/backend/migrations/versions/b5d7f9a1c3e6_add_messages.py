"""add the Messages module tables (W14-R9)

Revision ID: b5d7f9a1c3e6
Revises: a3c5e7b9d1f2
Create Date: 2026-10-14 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b5d7f9a1c3e6'
down_revision = 'a3c5e7b9d1f2'
branch_labels = None
depends_on = None


def upgrade():
    now = sa.func.now()
    op.create_table(
        'messages',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('kind', sa.String(length=10), nullable=False),
        sa.Column('channel', sa.String(length=10), nullable=False, server_default='email'),
        sa.Column('subject', sa.String(length=200), nullable=False),
        sa.Column('body_html', sa.Text(), nullable=False, server_default=''),
        sa.Column('audience', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('source', sa.String(length=30), nullable=False, server_default='manual'),
        sa.Column('recipients_total', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('sent_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('failed_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('skipped_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('scheduled_for', sa.DateTime(timezone=True), nullable=True),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('sent_by_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=now),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=now),
    )
    op.create_index('ix_messages_status', 'messages', ['status'])
    op.create_table(
        'message_recipients',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('message_id', sa.Integer(), sa.ForeignKey('messages.id', ondelete='CASCADE'), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False, server_default=''),
        sa.Column('context', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(length=10), nullable=False, server_default='queued'),
    )
    op.create_index('ix_message_recipients_message_id', 'message_recipients', ['message_id'])
    op.create_index('ix_message_recipients_email', 'message_recipients', ['email'])
    op.create_index('ix_message_recipients_status', 'message_recipients', ['status'])
    op.create_table(
        'message_suppressions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=now),
    )
    op.create_index('ix_message_suppressions_email', 'message_suppressions', ['email'], unique=True)
    op.create_table(
        'message_rules',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('trigger', sa.String(length=30), nullable=False),
        sa.Column('offset_days', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('send_hour', sa.Integer(), nullable=False, server_default='9'),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('subject', sa.String(length=200), nullable=False),
        sa.Column('body_html', sa.Text(), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=now),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=now),
    )
    op.create_table(
        'message_rule_runs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('rule_id', sa.Integer(), sa.ForeignKey('message_rules.id', ondelete='CASCADE'), nullable=False),
        sa.Column('target_key', sa.String(length=60), nullable=False),
        sa.Column('message_id', sa.Integer(), sa.ForeignKey('messages.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=now),
        sa.UniqueConstraint('rule_id', 'target_key'),
    )
    op.create_index('ix_message_rule_runs_rule_id', 'message_rule_runs', ['rule_id'])


def downgrade():
    op.drop_table('message_rule_runs')
    op.drop_table('message_rules')
    op.drop_table('message_suppressions')
    op.drop_table('message_recipients')
    op.drop_table('messages')
