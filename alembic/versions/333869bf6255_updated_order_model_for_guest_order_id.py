"""updated order model for guest_order_id

Revision ID: 333869bf6255
Revises: 0f69daeb4379
Create Date: 2026-01-15 09:35:06.253927

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '333869bf6255'
down_revision: Union[str, Sequence[str], None] = '0f69daeb4379'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ✅ ADD Razorpay / Gateway fields to Order table ONLY

    op.add_column(
        "order",
        sa.Column("gateway_order_id", sa.String(length=255), nullable=True),
    )

    op.add_column(
        "order",
        sa.Column("gateway_payment_id", sa.String(length=255), nullable=True),
    )

    op.add_column(
        "order",
        sa.Column("gateway_signature", sa.String(length=255), nullable=True),
    )

    # Optional but recommended index
    op.create_index(
        "ix_order_gateway_order_id",
        "order",
        ["gateway_order_id"],
        unique=False,
    )


def downgrade() -> None:
    # Reverse ONLY what we added

    op.drop_index("ix_order_gateway_order_id", table_name="order")

    op.drop_column("order", "gateway_signature")
    op.drop_column("order", "gateway_payment_id")
    op.drop_column("order", "gateway_order_id")