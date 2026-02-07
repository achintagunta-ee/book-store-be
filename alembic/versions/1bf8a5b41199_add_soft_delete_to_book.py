"""add soft delete to book

Revision ID: 1bf8a5b41199
Revises: 04e0d8fc93a8
Create Date: 2026-02-07 10:36:43.613647

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '1bf8a5b41199'
down_revision: Union[str, Sequence[str], None] = '04e0d8fc93a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Add column with default False
    op.add_column(
        "book",
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false()
        )
    )

    # remove server default after creation (optional best practice)
    op.alter_column("book", "is_deleted", server_default=None)


def downgrade():
    op.drop_column("book", "is_deleted")