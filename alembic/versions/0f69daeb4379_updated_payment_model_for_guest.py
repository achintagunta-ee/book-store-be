"""updated payment model for guest

Revision ID: 0f69daeb4379
Revises: 3b4deaaf3474
Create Date: 2026-01-13 19:09:51.337809

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0f69daeb4379'
down_revision: Union[str, Sequence[str], None] = '3b4deaaf3474'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None



def upgrade() -> None:
    """Upgrade schema."""

    # ------------------------------------------------------------------
    # 1️⃣ Ensure user_id is nullable (guest payments)
    # ------------------------------------------------------------------
    op.alter_column(
        "payment",
        "user_id",
        existing_type=sa.Integer(),
        nullable=True
    )

    # ------------------------------------------------------------------
    # 2️⃣ Razorpay / Gateway metadata
    # ------------------------------------------------------------------
    op.add_column(
        "payment",
        sa.Column("gateway_order_id", sa.String(), nullable=True)
    )

    op.add_column(
        "payment",
        sa.Column("gateway_signature", sa.String(), nullable=True)
    )

    op.add_column(
        "payment",
        sa.Column("gateway_response", sa.JSON(), nullable=True)
    )

    op.add_column(
        "payment",
        sa.Column(
            "currency",
            sa.String(length=3),
            server_default="INR",
            nullable=False
        )
    )

    op.add_column(
        "payment",
        sa.Column("failure_reason", sa.String(), nullable=True)
    )

    # ------------------------------------------------------------------
    # 3️⃣ Strengthen constraints
    # ------------------------------------------------------------------

    # txn_id must be unique (already true, but enforced here)
    op.create_unique_constraint(
        "uq_payment_txn_id",
        "payment",
        ["txn_id"]
    )

    # Prevent multiple payments for same order & method
    op.create_unique_constraint(
        "uq_payment_order_method",
        "payment",
        ["order_id", "method"]
    )


def downgrade() -> None:
    """Downgrade schema."""

    # ------------------------------------------------------------------
    # Remove constraints
    # ------------------------------------------------------------------
    op.drop_constraint("uq_payment_order_method", "payment", type_="unique")
    op.drop_constraint("uq_payment_txn_id", "payment", type_="unique")

    # ------------------------------------------------------------------
    # Remove Razorpay metadata columns
    # ------------------------------------------------------------------
    op.drop_column("payment", "failure_reason")
    op.drop_column("payment", "currency")
    op.drop_column("payment", "gateway_response")
    op.drop_column("payment", "gateway_signature")
    op.drop_column("payment", "gateway_order_id")

    # ------------------------------------------------------------------
    # Revert user_id (ONLY if you ever rollback)
    # ------------------------------------------------------------------
    op.alter_column(
        "payment",
        "user_id",
        existing_type=sa.Integer(),
        nullable=False
    )