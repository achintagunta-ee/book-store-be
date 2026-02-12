"""add fk constraint book.category

Revision ID: 0325e6a6518f
Revises: e9b7f2813567
Create Date: 2026-02-12 10:58:17.958127

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0325e6a6518f'
down_revision: Union[str, Sequence[str], None] = 'e9b7f2813567'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Fix orphan category references first
    op.execute("""
        UPDATE book
        SET category_id = 1
        WHERE category_id NOT IN (SELECT id FROM category);
    """)

    # Now install the foreign key
    op.create_foreign_key(
        "fk_book_category",
        "book",
        "category",
        ["category_id"],
        ["id"],
        ondelete="RESTRICT"
    )


def downgrade():
    op.drop_constraint(
        "fk_book_category",
        "book",
        type_="foreignkey"
    )
