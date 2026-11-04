"""Grove launch package costs $399 (was $499): update the stored price only when nobody changed it

Revision ID: 0010
Revises: 0009
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE plan_prices SET amount_minor = 39900 WHERE key = 'launch.grove' AND amount_minor = 49900"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE plan_prices SET amount_minor = 49900 WHERE key = 'launch.grove' AND amount_minor = 39900"))
