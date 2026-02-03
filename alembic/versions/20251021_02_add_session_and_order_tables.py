"""add session and order tables

Revision ID: add_session_and_order_20251021
Revises: add_category_sort_order_20251018
Create Date: 2025-10-21 10:45:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "add_session_and_order_20251021"
down_revision: Union[str, Sequence[str], None] = "add_category_sort_order_20251018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_session",
        sa.Column("session_id", sa.String(length=36), primary_key=True),
        sa.Column("data", sa.JSON(), nullable=True, comment="Session 任意資料 (含購物車)"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "orders",
        sa.Column("order_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "session_id",
            sa.String(length=36),
            sa.ForeignKey("user_session.session_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'pending'"), comment="訂單狀態"),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=False, comment="訂單總金額"),
        sa.Column("note", sa.Text(), nullable=True, comment="訂單備註"),
        sa.Column("contact_name", sa.Text(), nullable=True, comment="聯絡人姓名"),
        sa.Column("contact_phone", sa.Text(), nullable=True, comment="聯絡人電話"),
        sa.Column("cart_snapshot", sa.JSON(), nullable=True, comment="下單時購物車快照"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_orders_session_id", "orders", ["session_id"])

    op.create_table(
        "order_item",
        sa.Column("order_item_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "order_id",
            sa.BigInteger(),
            sa.ForeignKey("orders.order_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("dish_id", sa.BigInteger(), nullable=True, comment="菜色ID"),
        sa.Column("name", sa.Text(), nullable=False, comment="菜色名稱快照"),
        sa.Column("size_label", sa.Text(), nullable=True, comment="份量/尺寸標籤"),
        sa.Column("note", sa.Text(), nullable=True, comment="客製備註"),
        sa.Column("quantity", sa.Integer(), nullable=False, comment="數量"),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False, comment="單價"),
        sa.Column("line_total", sa.Numeric(12, 2), nullable=False, comment="明細小計"),
        sa.Column("extra_data", sa.JSON(), nullable=True, comment="額外資訊"),
    )
    op.create_index("ix_order_item_order_id", "order_item", ["order_id"])


def downgrade() -> None:
    op.drop_index("ix_order_item_order_id", table_name="order_item")
    op.drop_table("order_item")
    op.drop_index("ix_orders_session_id", table_name="orders")
    op.drop_table("orders")
    op.drop_table("user_session")
