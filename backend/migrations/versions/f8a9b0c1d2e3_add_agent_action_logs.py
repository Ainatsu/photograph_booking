"""add agent action logs

Revision ID: f8a9b0c1d2e3
Revises: ad4f6e7a8b90
Create Date: 2026-06-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f8a9b0c1d2e3"
down_revision: Union[str, Sequence[str], None] = "ad4f6e7a8b90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_action_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("message_id", sa.Integer(), nullable=True),
        sa.Column("tool_name", sa.String(length=128), nullable=False),
        sa.Column("tool_input", sa.JSON(), nullable=True),
        sa.Column("tool_result", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["conversation_id"], ["ai_conversations.id"]),
        sa.ForeignKeyConstraint(["message_id"], ["ai_messages.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agent_action_logs_id"), "agent_action_logs", ["id"], unique=False)
    op.create_index(op.f("ix_agent_action_logs_user_id"), "agent_action_logs", ["user_id"], unique=False)
    op.create_index(op.f("ix_agent_action_logs_conversation_id"), "agent_action_logs", ["conversation_id"], unique=False)
    op.create_index(op.f("ix_agent_action_logs_message_id"), "agent_action_logs", ["message_id"], unique=False)
    op.create_index(op.f("ix_agent_action_logs_tool_name"), "agent_action_logs", ["tool_name"], unique=False)
    op.create_index(op.f("ix_agent_action_logs_status"), "agent_action_logs", ["status"], unique=False)
    op.create_index(
        "ix_agent_action_logs_conversation_created",
        "agent_action_logs",
        ["conversation_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_agent_action_logs_conversation_created", table_name="agent_action_logs")
    op.drop_index(op.f("ix_agent_action_logs_status"), table_name="agent_action_logs")
    op.drop_index(op.f("ix_agent_action_logs_tool_name"), table_name="agent_action_logs")
    op.drop_index(op.f("ix_agent_action_logs_message_id"), table_name="agent_action_logs")
    op.drop_index(op.f("ix_agent_action_logs_conversation_id"), table_name="agent_action_logs")
    op.drop_index(op.f("ix_agent_action_logs_user_id"), table_name="agent_action_logs")
    op.drop_index(op.f("ix_agent_action_logs_id"), table_name="agent_action_logs")
    op.drop_table("agent_action_logs")
