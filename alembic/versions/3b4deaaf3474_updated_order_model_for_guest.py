"""updated order model for guest

Revision ID: 3b4deaaf3474
Revises: 83179daa0e5c
Create Date: 2026-01-13 17:51:01.989277

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '3b4deaaf3474'
down_revision: Union[str, Sequence[str], None] = '83179daa0e5c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Add guest address columns to order table
    op.add_column('order', sa.Column('guest_address_line1', sa.String(length=500), nullable=True))
    op.add_column('order', sa.Column('guest_address_line2', sa.String(length=500), nullable=True))
    op.add_column('order', sa.Column('guest_city', sa.String(length=100), nullable=True))
    op.add_column('order', sa.Column('guest_state', sa.String(length=100), nullable=True))
    op.add_column('order', sa.Column('guest_pincode', sa.String(length=10), nullable=True))
    op.add_column('order', sa.Column('guest_country', sa.String(length=100), nullable=True))


def downgrade():
    # Remove guest address columns from order table
    op.drop_column('order', 'guest_country')
    op.drop_column('order', 'guest_pincode')
    op.drop_column('order', 'guest_state')
    op.drop_column('order', 'guest_city')
    op.add_column('order', 'guest_address_line2')
    op.drop_column('order', 'guest_address_line1')