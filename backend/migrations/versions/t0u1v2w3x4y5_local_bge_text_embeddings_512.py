"""switch text embeddings to local BGE 512-dimensional vectors

Revision ID: t0u1v2w3x4y5
Revises: s9t0u1v2w3x4
"""

from alembic import op


revision = "t0u1v2w3x4y5"
down_revision = "s9t0u1v2w3x4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute("DROP INDEX IF EXISTS ix_ai_resource_embeddings_vector_hnsw")
    op.execute("UPDATE ai_resource_embeddings SET embedding_vector = NULL")
    op.execute(
        "ALTER TABLE ai_resource_embeddings "
        "ALTER COLUMN embedding_vector TYPE vector(512) USING NULL::vector(512)"
    )
    op.execute(
        "CREATE INDEX ix_ai_resource_embeddings_vector_hnsw "
        "ON ai_resource_embeddings USING hnsw (embedding_vector vector_cosine_ops)"
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute("DROP INDEX IF EXISTS ix_ai_resource_embeddings_vector_hnsw")
    op.execute("UPDATE ai_resource_embeddings SET embedding_vector = NULL")
    op.execute(
        "ALTER TABLE ai_resource_embeddings "
        "ALTER COLUMN embedding_vector TYPE vector(1536) USING NULL::vector(1536)"
    )
    op.execute(
        "CREATE INDEX ix_ai_resource_embeddings_vector_hnsw "
        "ON ai_resource_embeddings USING hnsw (embedding_vector vector_cosine_ops)"
    )
