"""remove delivered_at from order

Revision ID: c124867f63cd
Revises: 0c21d60c6f52
Create Date: 2026-01-06 21:06:52.230938

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c124867f63cd'
down_revision: Union[str, Sequence[str], None] = '0c21d60c6f52'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Check if column exists before dropping
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('order')]
    
    if 'delivered_at' in columns:
        op.drop_column('order', 'delivered_at')

def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('order', sa.Column('delivered_at', sa.DateTime(), nullable=True))
