"""add snapshot fields to notifications

Revision ID: a1bd0da8662d
Revises: defefadacd9f
Create Date: 2026-02-18 15:38:08.394730

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a1bd0da8662d'
down_revision: Union[str, Sequence[str], None] = 'defefadacd9f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column("notification", sa.Column("user_first_name", sa.String(), nullable=True))
    op.add_column("notification", sa.Column("user_last_name", sa.String(), nullable=True))
    op.add_column("notification", sa.Column("user_email", sa.String(), nullable=True))
    op.add_column("notification", sa.Column("user_username", sa.String(), nullable=True))


def downgrade():
    op.drop_column("notification", "user_first_name")
    op.drop_column("notification", "user_last_name")
    op.drop_column("notification", "user_email")
    op.drop_column("notification", "user_username")