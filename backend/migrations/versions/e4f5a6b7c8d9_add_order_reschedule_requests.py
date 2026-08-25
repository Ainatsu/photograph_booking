"""add independent order reschedule requests

Revision ID: e4f5a6b7c8d9
Revises: c2d3e4f5a6b7
Create Date: 2026-07-15 00:00:00.000000

"""
from datetime import datetime, timedelta
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e4f5a6b7c8d9"
down_revision: Union[str, Sequence[str], None] = "c2d3e4f5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    reschedule_status = sa.Enum(
        "PENDING",
        "ACCEPTED",
        "REJECTED",
        "WITHDRAWN",
        "EXPIRED",
        name="orderreschedulestatus",
    )
    op.create_table(
        "order_reschedule_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("requested_by", sa.Integer(), nullable=False),
        sa.Column("original_appointment_time", sa.DateTime(), nullable=False),
        sa.Column("requested_appointment_time", sa.DateTime(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", reschedule_status, nullable=False),
        sa.Column("response_note", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_order_reschedule_requests_id", "order_reschedule_requests", ["id"])
    op.create_index("ix_order_reschedule_requests_order_id", "order_reschedule_requests", ["order_id"])
    op.create_index("ix_order_reschedule_requests_requested_by", "order_reschedule_requests", ["requested_by"])
    op.create_index("ix_order_reschedule_requests_status", "order_reschedule_requests", ["status"])
    op.create_index("ix_order_reschedule_requests_expires_at", "order_reschedule_requests", ["expires_at"])
    op.create_index(
        "uq_order_reschedule_requests_pending_order",
        "order_reschedule_requests",
        ["order_id"],
        unique=True,
        sqlite_where=sa.text("status = 'PENDING'"),
        postgresql_where=sa.text("status = 'PENDING'"),
    )

    orders = sa.table(
        "orders",
        sa.column("id", sa.Integer()),
        sa.column("customer_id", sa.Integer()),
        sa.column("appointment_time", sa.DateTime()),
        sa.column("reschedule_requested_time", sa.DateTime()),
        sa.column("reschedule_reason", sa.Text()),
        sa.column("status", sa.String()),
    )
    requests = sa.table(
        "order_reschedule_requests",
        sa.column("order_id", sa.Integer()),
        sa.column("requested_by", sa.Integer()),
        sa.column("original_appointment_time", sa.DateTime()),
        sa.column("requested_appointment_time", sa.DateTime()),
        sa.column("reason", sa.Text()),
        sa.column("status", sa.String()),
        sa.column("expires_at", sa.DateTime()),
    )
    order_events = sa.table(
        "order_events",
        sa.column("order_id", sa.Integer()),
        sa.column("event_type", sa.String()),
    )
    bind = op.get_bind()
    legacy_rows = bind.execute(
        sa.select(
            orders.c.id,
            orders.c.customer_id,
            orders.c.appointment_time,
            orders.c.reschedule_requested_time,
            orders.c.reschedule_reason,
            orders.c.status,
        ).where(orders.c.reschedule_requested_time.is_not(None))
    ).mappings().all()
    expires_at = datetime.utcnow() + timedelta(hours=24)
    for row in legacy_rows:
        bind.execute(
            requests.insert().values(
                order_id=row["id"],
                requested_by=row["customer_id"],
                original_appointment_time=row["appointment_time"],
                requested_appointment_time=row["reschedule_requested_time"],
                reason=row["reschedule_reason"] or "历史改期申请",
                status="PENDING",
                expires_at=expires_at,
            )
        )
        if row["status"] == "RESCHEDULE_REQUESTED":
            was_confirmed = bind.execute(
                sa.select(sa.func.count())
                .select_from(order_events)
                .where(
                    order_events.c.order_id == row["id"],
                    order_events.c.event_type.in_(["confirmed", "reschedule_confirmed", "reschedule_accepted"]),
                )
            ).scalar()
            bind.execute(
                orders.update().where(orders.c.id == row["id"]).values(
                    status="CONFIRMED" if was_confirmed else "PENDING"
                )
            )


def downgrade() -> None:
    op.drop_index("uq_order_reschedule_requests_pending_order", table_name="order_reschedule_requests")
    op.drop_index("ix_order_reschedule_requests_expires_at", table_name="order_reschedule_requests")
    op.drop_index("ix_order_reschedule_requests_status", table_name="order_reschedule_requests")
    op.drop_index("ix_order_reschedule_requests_requested_by", table_name="order_reschedule_requests")
    op.drop_index("ix_order_reschedule_requests_order_id", table_name="order_reschedule_requests")
    op.drop_index("ix_order_reschedule_requests_id", table_name="order_reschedule_requests")
    op.drop_table("order_reschedule_requests")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        sa.Enum(name="orderreschedulestatus").drop(bind, checkfirst=True)
