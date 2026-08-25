"""add photographer availability exceptions

Revision ID: ab12cd34ef56
Revises: f8a9b0c1d2e3
Create Date: 2026-06-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "ab12cd34ef56"
down_revision: Union[str, Sequence[str], None] = "f8a9b0c1d2e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("photographer_profiles", sa.Column("availability_exceptions", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("photographer_profiles", "availability_exceptions")
