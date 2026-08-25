"""add multimodal image embeddings

Revision ID: g7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-07-22 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "g7b8c9d0e1f2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgresql = bind.dialect.name == "postgresql"
    if is_postgresql:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "ai_resource_image_embeddings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("image_url", sa.String(length=1000), nullable=False),
        sa.Column("image_hash", sa.String(length=64), nullable=False),
        sa.Column("visual_descriptor", sa.Text(), nullable=False),
        sa.Column("embedding_model", sa.String(length=255), nullable=False),
        sa.Column("embedding_version", sa.String(length=64), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("embedding_json", sa.JSON(), nullable=False),
        sa.Column("embedded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["ai_resource_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_resource_image_embeddings_id", "ai_resource_image_embeddings", ["id"])
    op.create_index("ix_ai_resource_image_embeddings_document_id", "ai_resource_image_embeddings", ["document_id"])
    op.create_index("ix_ai_resource_image_embeddings_image_hash", "ai_resource_image_embeddings", ["image_hash"])
    op.create_index(
        "uq_ai_resource_image_embeddings_document_url_model_version",
        "ai_resource_image_embeddings",
        ["document_id", "image_url", "embedding_model", "embedding_version"],
        unique=True,
    )
    if is_postgresql:
        op.execute("ALTER TABLE ai_resource_image_embeddings ADD COLUMN embedding_vector vector(1536)")
        op.execute(
            "CREATE INDEX ix_ai_resource_image_embeddings_vector_hnsw "
            "ON ai_resource_image_embeddings USING hnsw (embedding_vector vector_cosine_ops)"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_ai_resource_image_embeddings_vector_hnsw")
    op.drop_index(
        "uq_ai_resource_image_embeddings_document_url_model_version",
        table_name="ai_resource_image_embeddings",
    )
    op.drop_index("ix_ai_resource_image_embeddings_image_hash", table_name="ai_resource_image_embeddings")
    op.drop_index("ix_ai_resource_image_embeddings_document_id", table_name="ai_resource_image_embeddings")
    op.drop_index("ix_ai_resource_image_embeddings_id", table_name="ai_resource_image_embeddings")
    op.drop_table("ai_resource_image_embeddings")
