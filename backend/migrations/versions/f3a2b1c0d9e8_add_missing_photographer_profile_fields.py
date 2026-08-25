"""add missing photographer profile fields

Revision ID: f3a2b1c0d9e8
Revises: 7c1a9b2d4e6f
Create Date: 2026-07-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f3a2b1c0d9e8"
down_revision: Union[str, Sequence[str], None] = "7c1a9b2d4e6f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _existing_columns(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name)}


def _column_nullable(table_name: str, column_name: str) -> bool | None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for column in inspector.get_columns(table_name):
        if column["name"] == column_name:
            return bool(column["nullable"])
    return None


def upgrade() -> None:
    columns = _existing_columns("photographer_profiles")

    with op.batch_alter_table("photographer_profiles") as batch_op:
        if "cover_image_url" not in columns:
            batch_op.add_column(sa.Column("cover_image_url", sa.String(length=500), nullable=True))
        if "advance_notice" not in columns:
            batch_op.add_column(sa.Column("advance_notice", sa.Integer(), nullable=True))
        if "max_daily_bookings" not in columns:
            batch_op.add_column(sa.Column("max_daily_bookings", sa.Integer(), nullable=True))

    if _column_nullable("favorites", "favorite_type"):
        op.execute("UPDATE favorites SET favorite_type = 'work' WHERE favorite_type IS NULL")
        with op.batch_alter_table("favorites") as batch_op:
            batch_op.alter_column("favorite_type", existing_type=sa.String(length=16), nullable=False)


def downgrade() -> None:
    if _column_nullable("favorites", "favorite_type") is False:
        with op.batch_alter_table("favorites") as batch_op:
            batch_op.alter_column("favorite_type", existing_type=sa.String(length=16), nullable=True)

    columns = _existing_columns("photographer_profiles")

    with op.batch_alter_table("photographer_profiles") as batch_op:
        if "max_daily_bookings" in columns:
            batch_op.drop_column("max_daily_bookings")
        if "advance_notice" in columns:
            batch_op.drop_column("advance_notice")
        if "cover_image_url" in columns:
            batch_op.drop_column("cover_image_url")
