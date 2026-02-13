"""add archive flags to books

Revision ID: eaa2f0210691
Revises: 0325e6a6518f
Create Date: 2026-02-12 17:07:01.458745

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'eaa2f0210691'
down_revision: Union[str, Sequence[str], None] = '0325e6a6518f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade():
    op.add_column(
        "book",
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default="false")
    )

    op.create_index(
        "ix_book_is_archived",
        "book",
        ["is_archived"]
    )

    


def downgrade():
    op.drop_index("ix_book_is_archived", table_name="book")
    op.drop_column("book", "is_archived")