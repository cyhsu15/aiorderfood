"""add dish_detail table

Revision ID: a1b2c3d4e5f6
Revises: e691d383068d
Create Date: 2025-10-17 06:30:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'e691d383068d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'dish_detail',
        sa.Column('dish_id', sa.BigInteger(), sa.ForeignKey('dish.dish_id', ondelete='CASCADE'), primary_key=True),
        sa.Column('image_url', sa.Text(), nullable=True, comment='圖片URL'),
        sa.Column('description', sa.Text(), nullable=True, comment='詳細描述'),
        sa.Column('tags', sa.Text(), nullable=True, comment='餐點標籤'),
    )


def downgrade() -> None:
    op.drop_table('dish_detail')

