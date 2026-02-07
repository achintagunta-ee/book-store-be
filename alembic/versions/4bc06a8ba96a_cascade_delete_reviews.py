"""cascade delete reviews

Revision ID: 4bc06a8ba96a
Revises: 654609c4bcc9
Create Date: 2026-02-06 15:24:20.755315

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '4bc06a8ba96a'
down_revision: Union[str, Sequence[str], None] = '654609c4bcc9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Remove old FK
    op.drop_constraint('review_book_id_fkey', 'review', type_='foreignkey')

    # Add CASCADE FK
    op.create_foreign_key(
        'review_book_id_fkey',
        'review',
        'book',
        ['book_id'],
        ['id'],
        ondelete='CASCADE'
    )


def downgrade() -> None:
    # Remove cascade FK
    op.drop_constraint('review_book_id_fkey', 'review', type_='foreignkey')

    # Restore normal FK
    op.create_foreign_key(
        'review_book_id_fkey',
        'review',
        'book',
        ['book_id'],
        ['id']
    )