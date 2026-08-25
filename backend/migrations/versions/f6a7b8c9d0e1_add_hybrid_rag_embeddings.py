"""add hybrid rag resource embeddings

Revision ID: f6a7b8c9d0e1
Revises: e1f2a3b4c5d6
Create Date: 2026-07-22 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "f6a7b8c9d0e1"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgresql = bind.dialect.name == "postgresql"
    if is_postgresql:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    with op.batch_alter_table("agent_retrieval_logs") as batch_op:
        batch_op.add_column(sa.Column("ranking_diagnostics", sa.JSON(), nullable=True))

    op.create_table(
        "ai_resource_embeddings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("embedding_model", sa.String(length=255), nullable=False),
        sa.Column("embedding_version", sa.String(length=64), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("embedding_json", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("embedded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["ai_resource_documents.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_resource_embeddings_id", "ai_resource_embeddings", ["id"])
    op.create_index("ix_ai_resource_embeddings_document_id", "ai_resource_embeddings", ["document_id"])
    op.create_index("ix_ai_resource_embeddings_content_hash", "ai_resource_embeddings", ["content_hash"])
    op.create_index(
        "uq_ai_resource_embeddings_document_model_version",
        "ai_resource_embeddings",
        ["document_id", "embedding_model", "embedding_version"],
        unique=True,
    )

    if is_postgresql:
        op.execute(
            "ALTER TABLE ai_resource_embeddings "
            "ADD COLUMN embedding_vector vector(1536)"
        )
        op.execute(
            "CREATE INDEX ix_ai_resource_embeddings_vector_hnsw "
            "ON ai_resource_embeddings USING hnsw "
            "(embedding_vector vector_cosine_ops)"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_ai_resource_embeddings_vector_hnsw")
    op.drop_index(
        "uq_ai_resource_embeddings_document_model_version",
        table_name="ai_resource_embeddings",
    )
    op.drop_index("ix_ai_resource_embeddings_content_hash", table_name="ai_resource_embeddings")
    op.drop_index("ix_ai_resource_embeddings_document_id", table_name="ai_resource_embeddings")
    op.drop_index("ix_ai_resource_embeddings_id", table_name="ai_resource_embeddings")
    op.drop_table("ai_resource_embeddings")
    with op.batch_alter_table("agent_retrieval_logs") as batch_op:
        batch_op.drop_column("ranking_diagnostics")
