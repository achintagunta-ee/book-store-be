"""add gateway_order_id to ebookpurchase

Revision ID: e06f382711a1
Revises: 9f6c27940a34
Create Date: 2026-01-20 15:15:50.621863

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e06f382711a1'
down_revision: Union[str, Sequence[str], None] = '9f6c27940a34'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'ebookpurchase',
        sa.Column('gateway_order_id', sa.String(), nullable=True)
    )



def downgrade() -> None:
    op.drop_column('ebookpurchase', 'gateway_order_id')

