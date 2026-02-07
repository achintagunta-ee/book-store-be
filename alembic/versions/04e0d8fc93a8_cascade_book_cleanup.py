"""cascade book cleanup

Revision ID: 04e0d8fc93a8
Revises: 4bc06a8ba96a
Create Date: 2026-02-06 15:42:23.808714

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '04e0d8fc93a8'
down_revision: Union[str, Sequence[str], None] = '4bc06a8ba96a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():

    # ---------- WISHLIST ----------
    op.drop_constraint("wishlist_book_id_fkey", "wishlist", type_="foreignkey")

    op.create_foreign_key(
        "wishlist_book_id_fkey",
        "wishlist",
        "book",
        ["book_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # ---------- CART ----------
    op.drop_constraint("cartitem_book_id_fkey", "cartitem", type_="foreignkey")

    op.create_foreign_key(
        "cartitem_book_id_fkey",
        "cartitem",
        "book",
        ["book_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade():

    op.drop_constraint("wishlist_book_id_fkey", "wishlist", type_="foreignkey")
    op.create_foreign_key(
        "wishlist_book_id_fkey",
        "wishlist",
        "book",
        ["book_id"],
        ["id"],
    )

    op.drop_constraint("cartitem_book_id_fkey", "cartitem", type_="foreignkey")
    op.create_foreign_key(
        "cartitem_book_id_fkey",
        "cartitem",
        "book",
        ["book_id"],
        ["id"],
    )