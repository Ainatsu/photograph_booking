"""switch image embeddings to native 768-dimensional vectors

Revision ID: m3c4d5e6f7a8
Revises: l2b3c4d5e6f7
Create Date: 2026-08-20 00:00:00.000000
"""

from alembic import op


revision = "m3c4d5e6f7a8"
down_revision = "l2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute("DROP INDEX IF EXISTS ix_ai_resource_image_embeddings_vector_hnsw")
    # 旧向量来自 visual_descriptor 文本，不属于原生图片向量空间，不能保留或转换。
    op.execute("UPDATE ai_resource_image_embeddings SET embedding_vector = NULL")
    op.execute(
        "ALTER TABLE ai_resource_image_embeddings "
        "ALTER COLUMN embedding_vector TYPE vector(768) USING NULL::vector(768)"
    )
    op.execute(
        "CREATE INDEX ix_ai_resource_image_embeddings_vector_hnsw "
        "ON ai_resource_image_embeddings USING hnsw (embedding_vector vector_cosine_ops)"
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute("DROP INDEX IF EXISTS ix_ai_resource_image_embeddings_vector_hnsw")
    op.execute("UPDATE ai_resource_image_embeddings SET embedding_vector = NULL")
    op.execute(
        "ALTER TABLE ai_resource_image_embeddings "
        "ALTER COLUMN embedding_vector TYPE vector(1536) USING NULL::vector(1536)"
    )
    op.execute(
        "CREATE INDEX ix_ai_resource_image_embeddings_vector_hnsw "
        "ON ai_resource_image_embeddings USING hnsw (embedding_vector vector_cosine_ops)"
    )
