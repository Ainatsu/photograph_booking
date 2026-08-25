"""add order rejection reason

Revision ID: c9e1a2b3d4f6
Revises: b7d2f4a9c8e3
Create Date: 2026-06-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c9e1a2b3d4f6"
down_revision: Union[str, Sequence[str], None] = "b7d2f4a9c8e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("rejection_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "rejection_reason")
