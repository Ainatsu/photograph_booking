"""add_likes_table

Revision ID: ee961a21ecbb
Revises: a8484c4e0636
Create Date: 2026-06-09 16:07:12.118085

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'ee961a21ecbb'
down_revision: Union[str, Sequence[str], None] = 'a8484c4e0636'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "likes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("target_type", sa.String(20), nullable=False),
        sa.Column("target_id", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "target_type", "target_id", name="uq_like_user_target"),
    )
    op.create_index(op.f("ix_likes_id"), "likes", ["id"])
    op.create_index(op.f("ix_likes_user_id"), "likes", ["user_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_likes_user_id"), table_name="likes")
    op.drop_index(op.f("ix_likes_id"), table_name="likes")
    op.drop_table("likes")
