"""add photographer applications

Revision ID: c1d2e3f4a5b6
Revises: b9c7d8e9f0a1
Create Date: 2026-06-19 12:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, Sequence[str], None] = "b9c7d8e9f0a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "photographer_applications",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("profile_intro", sa.Text(), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=False),
        sa.Column("equipment", sa.String(length=500), nullable=False),
        sa.Column("styles", sa.JSON(), nullable=True),
        sa.Column("portfolio_refs", sa.JSON(), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("reviewed_by", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index(op.f("ix_photographer_applications_id"), "photographer_applications", ["id"], unique=False)
    op.create_index(op.f("ix_photographer_applications_status"), "photographer_applications", ["status"], unique=False)
    op.create_index(op.f("ix_photographer_applications_user_id"), "photographer_applications", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_photographer_applications_user_id"), table_name="photographer_applications")
    op.drop_index(op.f("ix_photographer_applications_status"), table_name="photographer_applications")
    op.drop_index(op.f("ix_photographer_applications_id"), table_name="photographer_applications")
    op.drop_table("photographer_applications")
