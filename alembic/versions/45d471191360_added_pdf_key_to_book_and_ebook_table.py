"""added pdf_key to book and ebook table

Revision ID: 45d471191360
Revises: 24012c3dc284
Create Date: 2026-01-09 14:57:04.079003

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '45d471191360'
down_revision: Union[str, Sequence[str], None] = '24012c3dc284'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade():
    op.add_column(
        "book",
        sa.Column("pdf_key", sa.String(), nullable=True)
    )

def downgrade():
    op.drop_column("book", "pdf_key")
