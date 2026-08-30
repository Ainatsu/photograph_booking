"""add private inspirations

Revision ID: p6g7h8i9j0k1
Revises: o5f6a7b8c9d0
"""

from alembic import op
import sqlalchemy as sa


revision = "p6g7h8i9j0k1"
down_revision = "o5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "inspirations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("summary", sa.String(length=300), nullable=True),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("cover_url", sa.String(length=500), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("location_name", sa.String(length=120), nullable=True),
        sa.Column("location_address", sa.String(length=255), nullable=True),
        sa.Column("latitude", sa.Numeric(precision=10, scale=7), nullable=True),
        sa.Column("longitude", sa.Numeric(precision=10, scale=7), nullable=True),
        sa.Column("place_id", sa.String(length=160), nullable=True),
        sa.Column("provider", sa.String(length=30), nullable=True),
        sa.Column("coordinate_system", sa.String(length=20), nullable=True),
        sa.Column("location_precision", sa.String(length=20), nullable=True),
        sa.Column("status", sa.Enum("DRAFT", "SAVED", "ARCHIVED", name="inspirationstatus"), nullable=False),
        sa.Column("visibility", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_inspirations_owner_id", "inspirations", ["owner_id"])
    op.create_index("ix_inspirations_status", "inspirations", ["status"])
    op.create_index("ix_inspirations_owner_status", "inspirations", ["owner_id", "status"])
    op.create_index("ix_inspirations_owner_updated", "inspirations", ["owner_id", "updated_at"])


def downgrade() -> None:
    op.drop_index("ix_inspirations_owner_updated", table_name="inspirations")
    op.drop_index("ix_inspirations_owner_status", table_name="inspirations")
    op.drop_index("ix_inspirations_status", table_name="inspirations")
    op.drop_index("ix_inspirations_owner_id", table_name="inspirations")
    op.drop_table("inspirations")
