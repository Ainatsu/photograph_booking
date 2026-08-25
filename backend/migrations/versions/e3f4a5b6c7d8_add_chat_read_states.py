"""add chat read states

Revision ID: e3f4a5b6c7d8
Revises: a1b2c3d4e5f6
Create Date: 2026-06-16 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e3f4a5b6c7d8"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chat_read_states",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("contact_user_id", sa.Integer(), nullable=False),
        sa.Column("order_events_read_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["contact_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_chat_read_states_id"), "chat_read_states", ["id"], unique=False)
    op.create_index(op.f("ix_chat_read_states_user_id"), "chat_read_states", ["user_id"], unique=False)
    op.create_index(op.f("ix_chat_read_states_contact_user_id"), "chat_read_states", ["contact_user_id"], unique=False)
    op.create_index(
        "ux_chat_read_states_user_contact",
        "chat_read_states",
        ["user_id", "contact_user_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ux_chat_read_states_user_contact", table_name="chat_read_states")
    op.drop_index(op.f("ix_chat_read_states_contact_user_id"), table_name="chat_read_states")
    op.drop_index(op.f("ix_chat_read_states_user_id"), table_name="chat_read_states")
    op.drop_index(op.f("ix_chat_read_states_id"), table_name="chat_read_states")
    op.drop_table("chat_read_states")
