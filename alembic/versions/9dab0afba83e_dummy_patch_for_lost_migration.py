"""Dummy patch for lost migration

Revision ID: 9dab0afba83e
Revises: 21d761ab0a3a
Create Date: 2025-12-12 15:46:50.527623

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9dab0afba83e'
down_revision: Union[str, Sequence[str], None] = '21d761ab0a3a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
