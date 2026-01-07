"""Add shipped_at, delivered_at, tracking_id, tracking_url to order table

Revision ID: 0c21d60c6f52
Revises: 497c3e9cd6f0
Create Date: 2026-01-06 14:12:42.369292

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0c21d60c6f52'
down_revision: Union[str, Sequence[str], None] = '497c3e9cd6f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Check if column exists before adding
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('order')]
    
    if 'delivered_at' not in columns:
        op.add_column('order', sa.Column('delivered_at', sa.DateTime(), nullable=True))
    else:
        print("✓ Column delivered_at already exists, skipping...")

def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('order', 'delivered_at')