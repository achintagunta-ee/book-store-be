"""add book images

Revision ID: 8b0ea94d2c39
Revises: 623a7270dc3a
Create Date: 2026-02-05 12:09:24.823232

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '8b0ea94d2c39'
down_revision: Union[str, Sequence[str], None] = '623a7270dc3a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "book_image",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "book_id",
            sa.Integer(),
            sa.ForeignKey("book.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("image_url", sa.String(length=500), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # index for faster lookup
    op.create_index(
        "ix_book_image_book_id",
        "book_image",
        ["book_id"],
    )
   


def downgrade() -> None:
    op.drop_index("ix_book_image_book_id", table_name="book_image")
    op.drop_table("book_image")
