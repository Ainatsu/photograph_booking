"""add agent episodic and user memory tables

Revision ID: o5f6a7b8c9d0
Revises: n4e5f6a7b8c9
"""

from alembic import op
import sqlalchemy as sa


revision = "o5f6a7b8c9d0"
down_revision = "n4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_memory_episodes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("task_type", sa.String(length=64), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("structured_summary", sa.JSON(), nullable=False),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["conversation_id"], ["ai_conversations.id"]),
        sa.ForeignKeyConstraint(["task_id"], ["agent_task_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id"),
    )
    op.create_index("ix_agent_memory_episodes_user_id", "agent_memory_episodes", ["user_id"])
    op.create_index("ix_agent_memory_episodes_conversation_id", "agent_memory_episodes", ["conversation_id"])
    op.create_index("ix_agent_memory_episodes_task_id", "agent_memory_episodes", ["task_id"])
    op.create_index("ix_agent_memory_episodes_task_type", "agent_memory_episodes", ["task_type"])

    op.create_table(
        "agent_user_memories",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("memory_type", sa.String(length=64), nullable=False),
        sa.Column("memory_key", sa.String(length=255), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("evidence_count", sa.Integer(), nullable=False),
        sa.Column("source_task_ids", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("first_observed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_observed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "memory_type", "memory_key", name="uq_agent_user_memory_key"),
    )
    op.create_index("ix_agent_user_memories_user_id", "agent_user_memories", ["user_id"])
    op.create_index("ix_agent_user_memories_memory_type", "agent_user_memories", ["memory_type"])
    op.create_index("ix_agent_user_memories_status", "agent_user_memories", ["status"])
    op.create_index("ix_agent_user_memories_user_status", "agent_user_memories", ["user_id", "status"])


def downgrade() -> None:
    op.drop_table("agent_user_memories")
    op.drop_table("agent_memory_episodes")
