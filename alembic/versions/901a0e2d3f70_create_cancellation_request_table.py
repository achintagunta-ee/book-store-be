"""create cancellation request table

Revision ID: 901a0e2d3f70
Revises: c124867f63cd
Create Date: 2026-01-08 07:20:34.523607

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '901a0e2d3f70'
down_revision: Union[str, Sequence[str], None] = 'c124867f63cd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table(
        'cancellationrequest',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('order_id', sa.Integer(), sa.ForeignKey('order.id'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('reason', sa.String(), nullable=False),
        sa.Column('additional_notes', sa.String(), nullable=True),
        sa.Column('status', sa.String(), server_default='pending', nullable=False),
        sa.Column('refund_amount', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('refund_method', sa.String(), nullable=True),
        sa.Column('refund_reference', sa.String(), nullable=True),
        sa.Column('admin_notes', sa.String(), nullable=True),
        sa.Column('requested_at', sa.DateTime(), nullable=False),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('processed_by', sa.Integer(), sa.ForeignKey('user.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False)
    )

def downgrade() -> None:
    op.drop_table('cancellationrequest')