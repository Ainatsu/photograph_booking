"""add order automation metadata and reliable notification outbox

Revision ID: e0f1a2b3c4d5
Revises: d9e0f1a2b3c4
Create Date: 2026-07-15 18:20:00.000000
"""

from datetime import timedelta
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e0f1a2b3c4d5"
down_revision: Union[str, Sequence[str], None] = "d9e0f1a2b3c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ORDER_COLUMNS = {
    "action_required_by": sa.Column("action_required_by", sa.String(20), nullable=True),
    "action_deadline_at": sa.Column("action_deadline_at", sa.DateTime(), nullable=True),
    "next_action_code": sa.Column("next_action_code", sa.String(40), nullable=True),
    "auto_action_code": sa.Column("auto_action_code", sa.String(40), nullable=True),
    "last_reminded_at": sa.Column("last_reminded_at", sa.DateTime(), nullable=True),
    "reminder_count": sa.Column("reminder_count", sa.Integer(), nullable=False, server_default="0"),
    "overdue_at": sa.Column("overdue_at", sa.DateTime(), nullable=True),
}


def _ensure_index(table_name: str, name: str, columns: list[str], unique: bool = False) -> None:
    bind = op.get_bind()
    existing = {item["name"] for item in sa.inspect(bind).get_indexes(table_name)}
    if name not in existing:
        op.create_index(name, table_name, columns, unique=unique)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {item["name"] for item in inspector.get_columns("orders")}
    missing = [column for name, column in ORDER_COLUMNS.items() if name not in existing_columns]
    if missing:
        with op.batch_alter_table("orders") as batch_op:
            for column in missing:
                batch_op.add_column(column)

    for name in ["action_required_by", "action_deadline_at", "next_action_code", "overdue_at"]:
        _ensure_index("orders", f"ix_orders_{name}", [name])

    tables = set(sa.inspect(bind).get_table_names())
    if "outbox_events" not in tables:
        op.create_table(
            "outbox_events",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("event_key", sa.String(120), nullable=False),
            sa.Column("aggregate_type", sa.String(40), nullable=False),
            sa.Column("aggregate_id", sa.String(64), nullable=False),
            sa.Column("event_type", sa.String(60), nullable=False),
            sa.Column("recipient_ids", sa.JSON(), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("next_attempt_at", sa.DateTime(), nullable=True),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("processed_at", sa.DateTime(), nullable=True),
        )
    for name, columns, unique in [
        ("ix_outbox_events_event_key", ["event_key"], True),
        ("ix_outbox_events_aggregate_type", ["aggregate_type"], False),
        ("ix_outbox_events_aggregate_id", ["aggregate_id"], False),
        ("ix_outbox_events_event_type", ["event_type"], False),
        ("ix_outbox_events_status", ["status"], False),
        ("ix_outbox_events_next_attempt_at", ["next_attempt_at"], False),
    ]:
        _ensure_index("outbox_events", name, columns, unique)

    tables = set(sa.inspect(bind).get_table_names())
    if "order_notifications" not in tables:
        op.create_table(
            "order_notifications",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("outbox_event_id", sa.Integer(), sa.ForeignKey("outbox_events.id"), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=True),
            sa.Column("notification_type", sa.String(60), nullable=False),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("action_url", sa.String(500), nullable=True),
            sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("read_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("outbox_event_id", "user_id", name="uq_order_notifications_outbox_user"),
        )
    for name, columns in [
        ("ix_order_notifications_outbox_event_id", ["outbox_event_id"]),
        ("ix_order_notifications_user_id", ["user_id"]),
        ("ix_order_notifications_order_id", ["order_id"]),
        ("ix_order_notifications_notification_type", ["notification_type"]),
        ("ix_order_notifications_is_read", ["is_read"]),
    ]:
        _ensure_index("order_notifications", name, columns)

    _backfill_action_metadata(bind)


def _backfill_action_metadata(bind) -> None:
    orders = sa.table(
        "orders",
        sa.column("id", sa.Integer()),
        sa.column("status", sa.String()),
        sa.column("created_at", sa.DateTime()),
        sa.column("appointment_time", sa.DateTime()),
        sa.column("delivery_due_at", sa.DateTime()),
        sa.column("payment_due_at", sa.DateTime()),
        sa.column("acceptance_deadline_at", sa.DateTime()),
        sa.column("payment_status", sa.String()),
        sa.column("after_sales_status", sa.String()),
        sa.column("action_required_by", sa.String()),
        sa.column("action_deadline_at", sa.DateTime()),
        sa.column("next_action_code", sa.String()),
        sa.column("auto_action_code", sa.String()),
    )
    for row in bind.execute(sa.select(orders)).mappings():
        status_value = str(row.get("status") or "").lower()
        values = {
            "action_required_by": None,
            "action_deadline_at": None,
            "next_action_code": None,
            "auto_action_code": None,
        }
        if row.get("after_sales_status") == "dispute_open":
            values.update(action_required_by="admin", next_action_code="resolve_dispute")
        elif status_value.endswith("pending") and "payment" not in status_value:
            created_at = row.get("created_at")
            values.update(
                action_required_by="photographer",
                action_deadline_at=created_at + timedelta(hours=24) if created_at else None,
                next_action_code="confirm_booking",
                auto_action_code="cancel_unconfirmed",
            )
        elif "awaiting" in status_value and "payment" in status_value:
            values.update(
                action_required_by="customer",
                action_deadline_at=row.get("payment_due_at"),
                next_action_code="pay_order",
                auto_action_code="expire_payment",
            )
        elif status_value.endswith("confirmed"):
            appointment_time = row.get("appointment_time")
            is_deposit_balance_due = row.get("payment_status") == "deposit_paid"
            values.update(
                action_required_by="customer" if is_deposit_balance_due else "photographer",
                action_deadline_at=(
                    appointment_time - timedelta(hours=24)
                    if is_deposit_balance_due and appointment_time
                    else appointment_time
                ),
                next_action_code="pay_balance" if is_deposit_balance_due else "start_service",
            )
        elif "in_progress" in status_value:
            values.update(
                action_required_by="photographer",
                action_deadline_at=row.get("delivery_due_at"),
                next_action_code="submit_delivery",
                auto_action_code="mark_delivery_overdue",
            )
        elif status_value.endswith("delivered"):
            values.update(
                action_required_by="photographer" if row.get("after_sales_status") == "revision_requested" else "customer",
                action_deadline_at=None if row.get("after_sales_status") == "revision_requested" else row.get("acceptance_deadline_at"),
                next_action_code="respond_or_redeliver_revision" if row.get("after_sales_status") == "revision_requested" else "accept_or_after_sales",
                auto_action_code=None if row.get("after_sales_status") == "revision_requested" else "auto_accept_delivery",
            )
        bind.execute(orders.update().where(orders.c.id == row["id"]).values(**values))


def downgrade() -> None:
    op.drop_table("order_notifications")
    op.drop_table("outbox_events")
    with op.batch_alter_table("orders") as batch_op:
        for name in ["overdue_at", "next_action_code", "action_deadline_at", "action_required_by"]:
            batch_op.drop_index(f"ix_orders_{name}")
        for name in reversed(list(ORDER_COLUMNS)):
            batch_op.drop_column(name)
