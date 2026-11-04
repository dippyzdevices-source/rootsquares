"""add news_images table

Revision ID: effbb83eff55
Revises: 082d5035d12d
Create Date: 2026-09-28 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'effbb83eff55'
down_revision = '082d5035d12d'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('news_images',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('news_id', sa.Integer(), nullable=False),
    sa.Column('storage_key', sa.String(length=500), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['news_id'], ['news.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('news_images', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_news_images_news_id'), ['news_id'], unique=False)


def downgrade():
    with op.batch_alter_table('news_images', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_news_images_news_id'))

    op.drop_table('news_images')
