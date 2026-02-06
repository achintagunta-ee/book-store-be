"""remove tax column

Revision ID: 654609c4bcc9
Revises: 8b0ea94d2c39
Create Date: 2026-02-06 14:26:54.080097

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '654609c4bcc9'
down_revision: Union[str, Sequence[str], None] = '8b0ea94d2c39'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # remove tax columns
    op.drop_column('order', 'tax')
    op.drop_column('ordersummary', 'tax')

    # remove ebook subscription system
    op.drop_table('ebooksubscription')
    op.drop_table('subscriptionplan')


def downgrade():
    # restore subscriptionplan
    op.create_table(
        'subscriptionplan',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('duration_days', sa.Integer(), nullable=False),
        sa.Column('max_books', sa.Integer(), nullable=True),
    )

    # restore ebooksubscription
    op.create_table(
        'ebooksubscription',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id')),
        sa.Column('plan_id', sa.Integer(), sa.ForeignKey('subscriptionplan.id')),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
    )

    # restore tax
    op.add_column('order', sa.Column('tax', sa.Float(), nullable=True))
    op.add_column('ordersummary', sa.Column('tax', sa.Float(), nullable=True))
