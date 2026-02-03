"""add table_id to user_session and orders

Revision ID: add_table_id_20251111_01
Revises: 339cf6f41713
Create Date: 2025-11-11 12:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "add_table_id_20251111_01"
down_revision: Union[str, Sequence[str], None] = "339cf6f41713"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """新增 table_id 欄位到 user_session 和 orders 表，用於多人共享桌號點餐功能"""

    # 新增 table_id 到 user_session 表
    op.add_column(
        "user_session",
        sa.Column("table_id", sa.String(50), nullable=True, comment="桌號標籤 (例如: A1, B2)"),
    )

    # 新增 table_id 到 orders 表
    op.add_column(
        "orders",
        sa.Column("table_id", sa.String(50), nullable=True, comment="桌號標籤 (從 session 複製)"),
    )

    # 建立索引以加速依桌號查詢訂單
    op.create_index(
        "ix_orders_table_id",
        "orders",
        ["table_id"],
        unique=False,
    )


def downgrade() -> None:
    """移除 table_id 欄位"""

    # 移除索引
    op.drop_index("ix_orders_table_id", table_name="orders")

    # 移除欄位
    op.drop_column("orders", "table_id")
    op.drop_column("user_session", "table_id")
