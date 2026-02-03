"""add sort_order to category

Revision ID: add_category_sort_order_20251018
Revises: a1b2c3d4e5f6
Create Date: 2025-10-18 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_category_sort_order_20251018'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('category', sa.Column('sort_order', sa.Integer(), nullable=True, server_default='0', comment='顯示排序'))
    # Optionally drop server_default to leave only ORM default
    op.alter_column('category', 'sort_order', server_default=None)


def downgrade() -> None:
    op.drop_column('category', 'sort_order')

