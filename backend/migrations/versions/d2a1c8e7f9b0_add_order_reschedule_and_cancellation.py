"""add order reschedule and cancellation fields

Revision ID: d2a1c8e7f9b0
Revises: c9e1a2b3d4f6
Create Date: 2026-06-15 17:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d2a1c8e7f9b0"
down_revision: Union[str, Sequence[str], None] = "c9e1a2b3d4f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("reschedule_requested_time", sa.DateTime(), nullable=True))
    op.add_column("orders", sa.Column("reschedule_reason", sa.Text(), nullable=True))
    op.add_column("orders", sa.Column("cancellation_reason", sa.Text(), nullable=True))
    op.add_column("orders", sa.Column("cancelled_by", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "cancelled_by")
    op.drop_column("orders", "cancellation_reason")
    op.drop_column("orders", "reschedule_reason")
    op.drop_column("orders", "reschedule_requested_time")
