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
    with op.batch_alter_table("ai_conversations") as batch_op:
        batch_op.add_column(sa.Column("status", sa.String(length=32), nullable=False, server_default="active"))
        batch_op.add_column(sa.Column("last_message_preview", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("summary", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("source", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("active_task_id", sa.String(length=36), nullable=True))
        batch_op.create_index("ix_ai_conversations_status", ["status"], unique=False)
        batch_op.create_index("ix_ai_conversations_last_message_at", ["last_message_at"], unique=False)
        batch_op.create_index("ix_ai_conversations_active_task_id", ["active_task_id"], unique=False)
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
