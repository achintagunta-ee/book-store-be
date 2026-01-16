"""phone_number to address model

Revision ID: e0c033cf97e7
Revises: 333869bf6255
Create Date: 2026-01-16 15:51:02.656148

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e0c033cf97e7'
down_revision: Union[str, Sequence[str], None] = '333869bf6255'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # 1️⃣ Add column as nullable
    op.add_column(
        'address',
        sa.Column('phone_number', sa.VARCHAR(), nullable=True)
    )

    # 2️⃣ Backfill existing rows
    op.execute(
        "UPDATE address SET phone_number = '0000000000' WHERE phone_number IS NULL"
    )

    # 3️⃣ Enforce NOT NULL
    op.alter_column(
        'address',
        'phone_number',
        nullable=False
    )

