"""add thread metadata to ai conversations

Revision ID: w3x4y5z6a7b8
Revises: v2w3x4y5z6a7
"""

from alembic import op
import sqlalchemy as sa


revision = "w3x4y5z6a7b8"
down_revision = "v2w3x4y5z6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite batch_alter_table uses this fixed temporary name. If a previous
    # migration was interrupted after creating it, the next retry must remove
    # the incomplete copy before Alembic can recreate it.
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        bind.exec_driver_sql("DROP TABLE IF EXISTS _alembic_tmp_ai_conversations")

    with op.batch_alter_table("ai_conversations") as batch_op:
        # Add this column as nullable first. SQLite's batch copy does not
        # apply a newly-added server default to rows selected from the old
        # table, so a NOT NULL column would fail on existing conversations.
        batch_op.add_column(sa.Column("status", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("last_message_preview", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("summary", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("source", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("active_task_id", sa.String(length=36), nullable=True))
        batch_op.create_index("ix_ai_conversations_status", ["status"], unique=False)
        batch_op.create_index("ix_ai_conversations_last_message_at", ["last_message_at"], unique=False)
        batch_op.create_index("ix_ai_conversations_active_task_id", ["active_task_id"], unique=False)

    op.execute("UPDATE ai_conversations SET status = 'active' WHERE status IS NULL")
    with op.batch_alter_table("ai_conversations") as batch_op:
        batch_op.alter_column("status", nullable=False, server_default="active")
        batch_op.alter_column("status", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("ai_conversations") as batch_op:
        batch_op.drop_index("ix_ai_conversations_active_task_id")
        batch_op.drop_index("ix_ai_conversations_last_message_at")
        batch_op.drop_index("ix_ai_conversations_status")
        batch_op.drop_column("active_task_id")
        batch_op.drop_column("source")
        batch_op.drop_column("summary")
        batch_op.drop_column("last_message_at")
        batch_op.drop_column("last_message_preview")
        batch_op.drop_column("status")
