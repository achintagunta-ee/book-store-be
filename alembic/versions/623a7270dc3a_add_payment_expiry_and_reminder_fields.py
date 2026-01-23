"""Add payment expiry and reminder fields

Revision ID: 623a7270dc3a
Revises: e06f382711a1
Create Date: 2026-01-23 14:14:16.433037

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '623a7270dc3a'
down_revision: Union[str, Sequence[str], None] = 'e06f382711a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # ---- Orders Table ----
    op.add_column(
        "order",
        sa.Column("payment_expires_at", sa.DateTime(), nullable=True)
    )
    op.add_column(
        "order",
        sa.Column("reminder_24h_sent", sa.Boolean(), nullable=False, server_default="false")
    )
    op.add_column(
        "order",
        sa.Column("reminder_final_sent", sa.Boolean(), nullable=False, server_default="false")
    )

    # ---- Ebook Purchases Table ----
    op.add_column(
        "ebookpurchase",
        sa.Column("purchase_expires_at", sa.DateTime(), nullable=True)
    )
    op.add_column(
        "ebookpurchase",
        sa.Column("reminder_24h_sent", sa.Boolean(), nullable=False, server_default="false")
    )
    op.add_column(
        "ebookpurchase",
        sa.Column("reminder_final_sent", sa.Boolean(), nullable=False, server_default="false")
    )


def downgrade():
    # ---- Orders Table ----
    op.drop_column("order", "payment_expires_at")
    op.drop_column("order", "reminder_24h_sent")
    op.drop_column("order", "reminder_final_sent")

    # ---- Ebook Purchases Table ----
    op.drop_column("ebookpurchase", "purchase_expires_at")
    op.drop_column("ebookpurchase", "reminder_24h_sent")
    op.drop_column("ebookpurchase", "reminder_final_sent")