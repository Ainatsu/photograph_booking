"""add durable agent task sessions and resource snapshots

Revision ID: n4e5f6a7b8c9
Revises: m3c4d5e6f7a8
"""

from alembic import op
import sqlalchemy as sa


revision = "n4e5f6a7b8c9"
down_revision = "m3c4d5e6f7a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_task_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("task_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("slots", sa.JSON(), nullable=False),
        sa.Column("form", sa.JSON(), nullable=False),
        sa.Column("selected_resource", sa.JSON(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_active_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["conversation_id"], ["ai_conversations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_task_sessions_conversation_id", "agent_task_sessions", ["conversation_id"])
    op.create_index("ix_agent_task_sessions_user_id", "agent_task_sessions", ["user_id"])
    op.create_index("ix_agent_task_sessions_task_type", "agent_task_sessions", ["task_type"])
    op.create_index("ix_agent_task_sessions_status", "agent_task_sessions", ["status"])
    op.create_index("ix_agent_task_sessions_conversation_active", "agent_task_sessions", ["conversation_id", "status"])
    op.create_index("ix_agent_task_sessions_user_last_active", "agent_task_sessions", ["user_id", "last_active_at"])

    op.create_table(
        "agent_task_resources",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.String(length=128), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("source_tool", sa.String(length=128), nullable=True),
        sa.Column("is_selected", sa.Integer(), nullable=False),
        sa.Column("is_excluded", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["agent_task_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_task_resources_task_id", "agent_task_resources", ["task_id"])
    op.create_index("ix_agent_task_resources_resource_id", "agent_task_resources", ["resource_id"])
    op.create_index("ix_agent_task_resources_task_position", "agent_task_resources", ["task_id", "position"])

    op.create_table(
        "agent_task_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("message_id", sa.Integer(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["agent_task_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["message_id"], ["ai_messages.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_task_events_task_id", "agent_task_events", ["task_id"])
    op.create_index("ix_agent_task_events_event_type", "agent_task_events", ["event_type"])
    op.create_index("ix_agent_task_events_message_id", "agent_task_events", ["message_id"])
    op.create_index("ix_agent_task_events_task_created", "agent_task_events", ["task_id", "created_at"])


def downgrade() -> None:
    op.drop_table("agent_task_events")
    op.drop_table("agent_task_resources")
    op.drop_table("agent_task_sessions")
