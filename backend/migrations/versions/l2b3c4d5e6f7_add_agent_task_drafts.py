"""add persistent agent task drafts

Revision ID: l2b3c4d5e6f7
Revises: k1f2a3b4c5d6
"""

from alembic import op
import sqlalchemy as sa


revision = "l2b3c4d5e6f7"
down_revision = "k1f2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_task_drafts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("task_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("target", sa.JSON(), nullable=False),
        sa.Column("fields", sa.JSON(), nullable=False),
        sa.Column("field_sources", sa.JSON(), nullable=False),
        sa.Column("media_assets", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["conversation_id"], ["ai_conversations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_task_drafts_conversation_id", "agent_task_drafts", ["conversation_id"])
    op.create_index("ix_agent_task_drafts_user_id", "agent_task_drafts", ["user_id"])
    op.create_index("ix_agent_task_drafts_task_type", "agent_task_drafts", ["task_type"])
    op.create_index("ix_agent_task_drafts_status", "agent_task_drafts", ["status"])
    op.create_index("ix_agent_task_drafts_conversation_status", "agent_task_drafts", ["conversation_id", "status"])
    op.create_index("ix_agent_task_drafts_user_conversation", "agent_task_drafts", ["user_id", "conversation_id"])
    op.create_index(
        "uq_agent_task_drafts_active_conversation",
        "agent_task_drafts",
        ["conversation_id"],
        unique=True,
        sqlite_where=sa.text("status IN ('collecting', 'editing_page', 'submitting')"),
        postgresql_where=sa.text("status IN ('collecting', 'editing_page', 'submitting')"),
    )


def downgrade() -> None:
    op.drop_index("uq_agent_task_drafts_active_conversation", table_name="agent_task_drafts")
    op.drop_index("ix_agent_task_drafts_user_conversation", table_name="agent_task_drafts")
    op.drop_index("ix_agent_task_drafts_conversation_status", table_name="agent_task_drafts")
    op.drop_index("ix_agent_task_drafts_status", table_name="agent_task_drafts")
    op.drop_index("ix_agent_task_drafts_task_type", table_name="agent_task_drafts")
    op.drop_index("ix_agent_task_drafts_user_id", table_name="agent_task_drafts")
    op.drop_index("ix_agent_task_drafts_conversation_id", table_name="agent_task_drafts")
    op.drop_table("agent_task_drafts")
