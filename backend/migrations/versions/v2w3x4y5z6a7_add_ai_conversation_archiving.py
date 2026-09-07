"""add ai conversation archiving

Revision ID: v2w3x4y5z6a7
Revises: u1v2w3x4y5z6
"""

from alembic import op
import sqlalchemy as sa


revision = "v2w3x4y5z6a7"
down_revision = "u1v2w3x4y5z6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("ai_conversations") as batch_op:
        batch_op.add_column(sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_index("ix_ai_conversations_archived_at", ["archived_at"], unique=False)
        batch_op.create_index(
            "ix_ai_conversations_user_archived_updated",
            ["user_id", "archived_at", "updated_at"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("ai_conversations") as batch_op:
        batch_op.drop_index("ix_ai_conversations_user_archived_updated")
        batch_op.drop_index("ix_ai_conversations_archived_at")
        batch_op.drop_column("archived_at")
