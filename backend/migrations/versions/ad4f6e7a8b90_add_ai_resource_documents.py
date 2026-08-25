"""add ai resource documents

Revision ID: ad4f6e7a8b90
Revises: ea9cde8cf847
Create Date: 2026-06-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "ad4f6e7a8b90"
down_revision: Union[str, Sequence[str], None] = "ea9cde8cf847"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_resource_documents",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("resource_type", sa.String(length=32), nullable=False),
        sa.Column("resource_id", sa.String(length=128), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("search_text", sa.Text(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("city", sa.String(length=255), nullable=True),
        sa.Column("price_min", sa.Float(), nullable=True),
        sa.Column("price_max", sa.Float(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ai_resource_documents_id"), "ai_resource_documents", ["id"], unique=False)
    op.create_index(
        op.f("ix_ai_resource_documents_owner_user_id"),
        "ai_resource_documents",
        ["owner_user_id"],
        unique=False,
    )
    op.create_index(
        "uq_ai_resource_documents_type_resource",
        "ai_resource_documents",
        ["resource_type", "resource_id"],
        unique=True,
    )
    op.create_index(
        "ix_ai_resource_documents_type_city",
        "ai_resource_documents",
        ["resource_type", "city"],
        unique=False,
    )
    op.create_index(
        "ix_ai_resource_documents_type_price",
        "ai_resource_documents",
        ["resource_type", "price_min", "price_max"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_ai_resource_documents_type_price", table_name="ai_resource_documents")
    op.drop_index("ix_ai_resource_documents_type_city", table_name="ai_resource_documents")
    op.drop_index("uq_ai_resource_documents_type_resource", table_name="ai_resource_documents")
    op.drop_index(op.f("ix_ai_resource_documents_owner_user_id"), table_name="ai_resource_documents")
    op.drop_index(op.f("ix_ai_resource_documents_id"), table_name="ai_resource_documents")
    op.drop_table("ai_resource_documents")
