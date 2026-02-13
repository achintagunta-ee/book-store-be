"""add order events table

Revision ID: defefadacd9f
Revises: eaa2f0210691
Create Date: 2026-02-13 16:19:14.274748

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'defefadacd9f'
down_revision: Union[str, Sequence[str], None] = 'eaa2f0210691'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.create_table(
        "order_event",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("order.id"), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("meta", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False, server_default="system"),
    )

    # indexes for fast timeline queries
    op.create_index("ix_order_event_order_id", "order_event", ["order_id"])
    op.create_index("ix_order_event_event_type", "order_event", ["event_type"])


def downgrade():
    op.drop_index("ix_order_event_event_type", table_name="order_event")
    op.drop_index("ix_order_event_order_id", table_name="order_event")
    op.drop_table("order_event")