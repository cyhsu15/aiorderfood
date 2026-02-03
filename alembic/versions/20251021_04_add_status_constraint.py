"""add status constraint to orders

Revision ID: add_status_check_20251021_04
Revises: add_version_20251021_03
Create Date: 2025-10-21 16:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "add_status_check_20251021_04"
down_revision: Union[str, Sequence[str], None] = "add_version_20251021_03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add CHECK constraint to ensure only valid status values
    op.create_check_constraint(
        "orders_status_check",
        "orders",
        "status IN ('pending', 'confirmed', 'preparing', 'completed', 'cancelled', 'preorder')"
    )


def downgrade() -> None:
    op.drop_constraint("orders_status_check", "orders", type_="check")
