"""add payments table

Revision ID: 5492a0cb6858
Revises: 240dc5e90ab6
Create Date: 2025-12-16 12:46:31.682800

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5492a0cb6858'
down_revision: Union[str, Sequence[str], None] = '240dc5e90ab6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
