"""add order events table

Revision ID: b7d2f4a9c8e3
Revises: f4b9c2d8a6e1
Create Date: 2026-06-14 13:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7d2f4a9c8e3"
down_revision: Union[str, Sequence[str], None] = "f4b9c2d8a6e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "order_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("actor_role", sa.String(length=20), nullable=True),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_order_events_id"), "order_events", ["id"], unique=False)
    op.create_index(op.f("ix_order_events_order_id"), "order_events", ["order_id"], unique=False)
    op.create_index(op.f("ix_order_events_actor_id"), "order_events", ["actor_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_order_events_actor_id"), table_name="order_events")
    op.drop_index(op.f("ix_order_events_order_id"), table_name="order_events")
    op.drop_index(op.f("ix_order_events_id"), table_name="order_events")
    op.drop_table("order_events")
