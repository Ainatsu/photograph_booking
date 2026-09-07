"""add retained context compression records

Revision ID: z5a6b7c8d9e0
Revises: y4z5a6b7c8d9
"""

from alembic import op
import sqlalchemy as sa

revision = "z5a6b7c8d9e0"
down_revision = "y4z5a6b7c8d9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_conversation_compressions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("ai_conversations.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("summary_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("compression_reason", sa.String(length=128), nullable=False),
        sa.Column("source_start_message_id", sa.Integer(), nullable=True),
        sa.Column("source_end_message_id", sa.Integer(), nullable=True),
        sa.Column("source_message_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("retained_facts", sa.JSON(), nullable=False),
        sa.Column("retained_task_ids", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("conversation_id", "summary_version", name="uq_ai_conversation_compression_version"),
    )
    op.create_index("ix_ai_conversation_compressions_conversation_id", "ai_conversation_compressions", ["conversation_id"])
    op.create_index("ix_ai_conversation_compressions_user_id", "ai_conversation_compressions", ["user_id"])
    op.create_index("ix_ai_conversation_compressions_conversation_created", "ai_conversation_compressions", ["conversation_id", "created_at"])


def downgrade() -> None:
    op.drop_table("ai_conversation_compressions")
