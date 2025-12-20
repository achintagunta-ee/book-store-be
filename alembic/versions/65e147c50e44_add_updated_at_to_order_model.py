"""add updated_at to Order Model

Revision ID: 65e147c50e44
Revises: 18173a865686
Create Date: 2025-12-20 12:45:59.629487

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '65e147c50e44'
down_revision: Union[str, Sequence[str], None] = '18173a865686'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import func

def upgrade():
    # Step 1: add column as nullable with default
    op.add_column(
        "order",
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=True,
            server_default=func.now()
        )
    )

    # Step 2: backfill existing rows
    op.execute('UPDATE "order" SET updated_at = NOW()')

    # Step 3: enforce NOT NULL
    op.alter_column(
        "order",
        "updated_at",
        nullable=False
    )

def downgrade():
    op.drop_column("order", "updated_at")
