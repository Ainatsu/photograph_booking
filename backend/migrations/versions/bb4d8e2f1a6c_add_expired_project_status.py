"""add expired project status

Revision ID: bb4d8e2f1a6c
Revises: f3a2b1c0d9e8
Create Date: 2026-07-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "bb4d8e2f1a6c"
down_revision: Union[str, Sequence[str], None] = "f3a2b1c0d9e8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.execute("ALTER TYPE projectstatus ADD VALUE IF NOT EXISTS 'EXPIRED'")


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("UPDATE shoot_projects SET status = 'CLOSED' WHERE status = 'EXPIRED'")
