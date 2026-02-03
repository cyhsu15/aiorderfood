"""add version to user_session

Revision ID: add_version_20251021_03
Revises: add_session_and_order_20251021
Create Date: 2025-10-21 14:30:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "add_version_20251021_03"
down_revision: Union[str, Sequence[str], None] = "add_session_and_order_20251021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add version column with default value of 1
    op.add_column(
        "user_session",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1", comment="版本號，用於樂觀鎖定"),
    )


def downgrade() -> None:
    op.drop_column("user_session", "version")
