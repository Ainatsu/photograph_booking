"""add append-only agent task form revisions

Revision ID: x4y5z6a7b8c9
Revises: w3x4y5z6a7b8
"""

from alembic import op
import sqlalchemy as sa


revision = "x4y5z6a7b8c9"
down_revision = "w3x4y5z6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_task_form_revisions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("operations", sa.JSON(), nullable=False),
        sa.Column("resulting_form", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_message_id", sa.Integer(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("created_by", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["ai_conversations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["source_message_id"], ["ai_messages.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id", "revision", name="uq_agent_task_form_revision"),
        sa.UniqueConstraint("task_id", "idempotency_key", name="uq_agent_task_form_idempotency"),
    )
    op.create_index("ix_agent_task_form_revisions_task_id", "agent_task_form_revisions", ["task_id"], unique=False)
    op.create_index("ix_agent_task_form_revisions_conversation_id", "agent_task_form_revisions", ["conversation_id"], unique=False)
    op.create_index("ix_agent_task_form_revisions_user_id", "agent_task_form_revisions", ["user_id"], unique=False)
    op.create_index("ix_agent_task_form_revisions_source_message_id", "agent_task_form_revisions", ["source_message_id"], unique=False)
    op.create_index("ix_agent_task_form_revisions_idempotency_key", "agent_task_form_revisions", ["idempotency_key"], unique=False)
    op.create_index("ix_agent_task_form_revisions_task_created", "agent_task_form_revisions", ["task_id", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_agent_task_form_revisions_task_created", table_name="agent_task_form_revisions")
    op.drop_index("ix_agent_task_form_revisions_idempotency_key", table_name="agent_task_form_revisions")
    op.drop_index("ix_agent_task_form_revisions_source_message_id", table_name="agent_task_form_revisions")
    op.drop_index("ix_agent_task_form_revisions_user_id", table_name="agent_task_form_revisions")
    op.drop_index("ix_agent_task_form_revisions_conversation_id", table_name="agent_task_form_revisions")
    op.drop_index("ix_agent_task_form_revisions_task_id", table_name="agent_task_form_revisions")
    op.drop_table("agent_task_form_revisions")
