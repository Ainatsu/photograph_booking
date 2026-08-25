"""engineer agent phase one contracts and observability

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-07-22 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "e1f2a3b4c5d6"
down_revision = "d0e1f2a3b4c5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("agent_action_logs") as batch_op:
        batch_op.add_column(sa.Column("tool_schema_version", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("risk_level", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("confirmation_policy", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("confirmation_count", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("idempotency_key", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("duration_ms", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("error_code", sa.String(length=128), nullable=True))
        batch_op.create_index("ix_agent_action_logs_idempotency_key", ["idempotency_key"], unique=True)

    op.create_table(
        "agent_retrieval_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("message_id", sa.Integer(), nullable=False),
        sa.Column("intent", sa.JSON(), nullable=True),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("criteria", sa.JSON(), nullable=True),
        sa.Column("requested_resource_types", sa.JSON(), nullable=True),
        sa.Column("document_counts", sa.JSON(), nullable=True),
        sa.Column("candidate_counts", sa.JSON(), nullable=True),
        sa.Column("result_counts", sa.JSON(), nullable=True),
        sa.Column("referenced_resource_ids", sa.JSON(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="success"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["conversation_id"], ["ai_conversations.id"]),
        sa.ForeignKeyConstraint(["message_id"], ["ai_messages.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_retrieval_logs_id", "agent_retrieval_logs", ["id"])
    op.create_index("ix_agent_retrieval_logs_user_id", "agent_retrieval_logs", ["user_id"])
    op.create_index("ix_agent_retrieval_logs_conversation_id", "agent_retrieval_logs", ["conversation_id"])
    op.create_index("ix_agent_retrieval_logs_message_id", "agent_retrieval_logs", ["message_id"])
    op.create_index("ix_agent_retrieval_logs_status", "agent_retrieval_logs", ["status"])
    op.create_index(
        "ix_agent_retrieval_logs_conversation_created",
        "agent_retrieval_logs",
        ["conversation_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_agent_retrieval_logs_conversation_created", table_name="agent_retrieval_logs")
    op.drop_index("ix_agent_retrieval_logs_status", table_name="agent_retrieval_logs")
    op.drop_index("ix_agent_retrieval_logs_message_id", table_name="agent_retrieval_logs")
    op.drop_index("ix_agent_retrieval_logs_conversation_id", table_name="agent_retrieval_logs")
    op.drop_index("ix_agent_retrieval_logs_user_id", table_name="agent_retrieval_logs")
    op.drop_index("ix_agent_retrieval_logs_id", table_name="agent_retrieval_logs")
    op.drop_table("agent_retrieval_logs")

    with op.batch_alter_table("agent_action_logs") as batch_op:
        batch_op.drop_index("ix_agent_action_logs_idempotency_key")
        batch_op.drop_column("error_code")
        batch_op.drop_column("duration_ms")
        batch_op.drop_column("idempotency_key")
        batch_op.drop_column("confirmation_count")
        batch_op.drop_column("confirmation_policy")
        batch_op.drop_column("risk_level")
        batch_op.drop_column("tool_schema_version")
