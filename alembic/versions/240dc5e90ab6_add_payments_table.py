"""add payments table

Revision ID: 240dc5e90ab6
Revises: c095268c86e6
Create Date: 2025-12-16 12:39:36.194149

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '240dc5e90ab6'
down_revision: Union[str, Sequence[str], None] = 'c095268c86e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
