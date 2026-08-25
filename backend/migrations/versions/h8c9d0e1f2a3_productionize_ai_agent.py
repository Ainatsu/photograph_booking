"""productionize ai agent

Revision ID: h8c9d0e1f2a3
Revises: g7b8c9d0e1f2
Create Date: 2026-07-22 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "h8c9d0e1f2a3"
down_revision = "g7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_index_jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("job_key", sa.String(length=160), nullable=False),
        sa.Column("reason", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("force", sa.Integer(), nullable=False),
        sa.Column("index_version", sa.String(length=64), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for name, columns, unique in (
        ("ix_ai_index_jobs_owner_user_id", ["owner_user_id"], False),
        ("ix_ai_index_jobs_job_key", ["job_key"], True),
        ("ix_ai_index_jobs_status", ["status"], False),
        ("ix_ai_index_jobs_next_attempt_at", ["next_attempt_at"], False),
        ("ix_ai_index_jobs_status_next_attempt", ["status", "next_attempt_at"], False),
    ):
        op.create_index(name, "ai_index_jobs", columns, unique=unique)

    op.create_table(
        "agent_traces",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("user_message_id", sa.Integer(), nullable=False),
        sa.Column("assistant_message_id", sa.Integer(), nullable=True),
        sa.Column("intent", sa.String(length=80), nullable=True),
        sa.Column("route", sa.String(length=80), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("prompt_version", sa.String(length=64), nullable=False),
        sa.Column("orchestrator_version", sa.String(length=64), nullable=False),
        sa.Column("index_version", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=True),
        sa.Column("model", sa.String(length=160), nullable=True),
        sa.Column("fallback_used", sa.Integer(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("retrieval_latency_ms", sa.Integer(), nullable=True),
        sa.Column("total_latency_ms", sa.Integer(), nullable=False),
        sa.Column("referenced_resource_ids", sa.JSON(), nullable=True),
        sa.Column("quality_flags", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["assistant_message_id"], ["ai_messages.id"]),
        sa.ForeignKeyConstraint(["conversation_id"], ["ai_conversations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["user_message_id"], ["ai_messages.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for name, columns in (
        ("ix_agent_traces_user_id", ["user_id"]),
        ("ix_agent_traces_conversation_id", ["conversation_id"]),
        ("ix_agent_traces_user_message_id", ["user_message_id"]),
        ("ix_agent_traces_assistant_message_id", ["assistant_message_id"]),
        ("ix_agent_traces_intent", ["intent"]),
        ("ix_agent_traces_status", ["status"]),
        ("ix_agent_traces_created_status", ["created_at", "status"]),
        ("ix_agent_traces_intent_created", ["intent", "created_at"]),
    ):
        op.create_index(name, "agent_traces", columns)


def downgrade() -> None:
    for name in (
        "ix_agent_traces_intent_created", "ix_agent_traces_created_status", "ix_agent_traces_status",
        "ix_agent_traces_intent", "ix_agent_traces_assistant_message_id", "ix_agent_traces_user_message_id",
        "ix_agent_traces_conversation_id", "ix_agent_traces_user_id",
    ):
        op.drop_index(name, table_name="agent_traces")
    op.drop_table("agent_traces")
    for name in (
        "ix_ai_index_jobs_status_next_attempt", "ix_ai_index_jobs_next_attempt_at", "ix_ai_index_jobs_status",
        "ix_ai_index_jobs_job_key", "ix_ai_index_jobs_owner_user_id",
    ):
        op.drop_index(name, table_name="ai_index_jobs")
    op.drop_table("ai_index_jobs")
