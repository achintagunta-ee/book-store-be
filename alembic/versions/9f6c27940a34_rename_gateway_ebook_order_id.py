"""rename gateway ebook order id

Revision ID: 9f6c27940a34
Revises: 83ab27ac5356
Create Date: 2026-01-20 14:53:15.861348

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9f6c27940a34'
down_revision: Union[str, Sequence[str], None] = '83ab27ac5356'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column(
        "ebookpurchase",
        sa.Column("gateway_order_id", sa.String(), nullable=True) )

def downgrade():
    op.drop_column("ebookpurchase", "gateway_order_id")

