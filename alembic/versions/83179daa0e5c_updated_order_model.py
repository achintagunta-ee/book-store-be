"""updated order model

Revision ID: 83179daa0e5c
Revises: fa1dac94d28d
Create Date: 2026-01-13 16:13:06.266259

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '83179daa0e5c'
down_revision: Union[str, Sequence[str], None] = 'fa1dac94d28d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.alter_column(
        "order",
        "user_id",
        existing_type=sa.Integer(),
        nullable=True
    )

def downgrade():
    op.alter_column(
        "order",
        "user_id",
        existing_type=sa.Integer(),
        nullable=False
    )
