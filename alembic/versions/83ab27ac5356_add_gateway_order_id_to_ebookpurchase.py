"""add gateway_order_id to ebookpurchase

Revision ID: 83ab27ac5356
Revises: e0c033cf97e7
Create Date: 2026-01-20 14:48:38.901404

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '83ab27ac5356'
down_revision: Union[str, Sequence[str], None] = 'e0c033cf97e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column(
        "ebookpurchase",
        sa.Column("gateway_order_id", sa.String(), nullable=True)
    )
    op.create_index(
        "ix_ebookpurchase_gateway_order_id",
        "ebookpurchase",
        ["gateway_order_id"]
    )

def downgrade():
    op.drop_index("ix_ebookpurchase_gateway_order_id", table_name="ebookpurchase")
    op.drop_column("ebookpurchase", "gateway_order_id")

