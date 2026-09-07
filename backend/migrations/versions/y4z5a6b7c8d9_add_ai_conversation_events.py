"""add durable conversation event stream

Revision ID: y4z5a6b7c8d9
Revises: x4y5z6a7b8c9
"""

from alembic import op
import sqlalchemy as sa

revision = "y4z5a6b7c8d9"
down_revision = "x4y5z6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_conversation_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("ai_conversations.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("task_id", sa.String(length=36), nullable=True),
        sa.Column("turn_id", sa.String(length=36), nullable=True),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("event_id", name="uq_ai_conversation_events_event_id"),
        sa.UniqueConstraint("conversation_id", "sequence", name="uq_ai_conversation_event_sequence"),
    )
    op.create_index("ix_ai_conversation_events_event_id", "ai_conversation_events", ["event_id"], unique=True)
    op.create_index("ix_ai_conversation_events_conversation_id", "ai_conversation_events", ["conversation_id"])
    op.create_index("ix_ai_conversation_events_user_id", "ai_conversation_events", ["user_id"])
    op.create_index("ix_ai_conversation_events_task_id", "ai_conversation_events", ["task_id"])
    op.create_index("ix_ai_conversation_events_turn_id", "ai_conversation_events", ["turn_id"])
    op.create_index("ix_ai_conversation_events_type", "ai_conversation_events", ["type"])
    op.create_index("ix_ai_conversation_events_conversation_sequence", "ai_conversation_events", ["conversation_id", "sequence"])


def downgrade() -> None:
    op.drop_table("ai_conversation_events")
