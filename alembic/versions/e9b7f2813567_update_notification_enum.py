"""update notification enum

Revision ID: e9b7f2813567
Revises: 1bf8a5b41199
Create Date: 2026-02-07 15:59:57.752424

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e9b7f2813567'
down_revision: Union[str, Sequence[str], None] = '1bf8a5b41199'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Add missing enum values
    op.execute("ALTER TYPE notificationstatus ADD VALUE IF NOT EXISTS 'read'")
    op.execute("ALTER TYPE notificationstatus ADD VALUE IF NOT EXISTS 'cleared'")


def downgrade():
    # PostgreSQL cannot drop enum values directly
    # recreate enum without read/cleared

    op.execute("ALTER TYPE notificationstatus RENAME TO notificationstatus_old")

    op.execute("""
        CREATE TYPE notificationstatus AS ENUM ('sent', 'failed');
    """)

    op.execute("""
        ALTER TABLE notification
        ALTER COLUMN status
        TYPE notificationstatus
        USING status::text::notificationstatus;
    """)

    op.execute("DROP TYPE notificationstatus_old")