"""add per-thread approval and tool permission policies

Revision ID: d7e8f9a0b1c2
Revises: b6c7d8e9f0a2
"""
from alembic import op
import sqlalchemy as sa

revision = "d7e8f9a0b1c2"
down_revision = "b6c7d8e9f0a2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("ai_conversations") as batch_op:
        batch_op.add_column(sa.Column("approval_policy", sa.String(32), nullable=False, server_default="confirm_write"))
        batch_op.add_column(sa.Column("tool_permission_profile", sa.String(32), nullable=False, server_default="normal"))
        batch_op.add_column(sa.Column("confirmation_mode", sa.String(32), nullable=False, server_default="inline"))


def downgrade() -> None:
    with op.batch_alter_table("ai_conversations") as batch_op:
        batch_op.drop_column("confirmation_mode")
        batch_op.drop_column("tool_permission_profile")
        batch_op.drop_column("approval_policy")
