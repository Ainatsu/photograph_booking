"""add structured order contracts with CNY pricing

Revision ID: f5a6b7c8d9e0
Revises: e4f5a6b7c8d9
Create Date: 2026-07-15 00:00:00.000000

"""
import json
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f5a6b7c8d9e0"
down_revision: Union[str, Sequence[str], None] = "e4f5a6b7c8d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ORDER_COLUMNS = [
    sa.Column("source_type", sa.String(length=20), nullable=False, server_default="legacy"),
    sa.Column("source_id", sa.String(length=64), nullable=True),
    sa.Column("source_application_id", sa.Integer(), nullable=True),
    sa.Column("package_id", sa.String(length=64), nullable=True),
    sa.Column("package_name", sa.String(length=200), nullable=True),
    sa.Column("package_description", sa.Text(), nullable=True),
    sa.Column("package_price", sa.Numeric(12, 2), nullable=True),
    sa.Column("final_price", sa.Numeric(12, 2), nullable=True),
    sa.Column("currency", sa.String(length=3), nullable=False, server_default="CNY"),
    sa.Column("service_location", sa.String(length=255), nullable=True),
    sa.Column("delivery_due_at", sa.DateTime(), nullable=True),
    sa.Column("original_image_count", sa.Integer(), nullable=True),
    sa.Column("retouched_image_count", sa.Integer(), nullable=True),
    sa.Column("delivery_formats", sa.JSON(), nullable=True),
    sa.Column("included_revision_count", sa.Integer(), nullable=True),
    sa.Column("commercial_license", sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.Column("copyright_terms", sa.Text(), nullable=True),
    sa.Column("cancellation_policy_snapshot", sa.JSON(), nullable=True),
    sa.Column("reschedule_policy_snapshot", sa.JSON(), nullable=True),
    sa.Column("deliverables", sa.JSON(), nullable=True),
    sa.Column("payment_mode", sa.String(length=24), nullable=False, server_default="full"),
    sa.Column("fulfillment_mode", sa.String(length=24), nullable=False, server_default="single_delivery"),
    sa.Column("contract_snapshot", sa.JSON(), nullable=True),
]


def _backfill_package_ids(bind) -> None:
    profiles = sa.table(
        "photographer_profiles",
        sa.column("id", sa.Integer()),
        sa.column("packages", sa.JSON()),
    )
    rows = bind.execute(sa.select(profiles.c.id, profiles.c.packages)).mappings().all()
    for row in rows:
        packages = row["packages"]
        if isinstance(packages, str):
            try:
                packages = json.loads(packages)
            except json.JSONDecodeError:
                continue
        if not isinstance(packages, list):
            continue
        changed = False
        normalized = []
        for package in packages:
            if not isinstance(package, dict):
                normalized.append(package)
                continue
            package = dict(package)
            if not package.get("id"):
                package["id"] = uuid.uuid4().hex
                changed = True
            if "is_active" not in package:
                package["is_active"] = True
                changed = True
            normalized.append(package)
        if changed:
            bind.execute(
                profiles.update().where(profiles.c.id == row["id"]).values(packages=normalized)
            )


def _backfill_legacy_contracts(bind) -> None:
    orders = sa.table(
        "orders",
        sa.column("id", sa.Integer()),
        sa.column("package_snapshot", sa.String()),
        sa.column("appointment_time", sa.DateTime()),
        sa.column("duration_minutes", sa.Integer()),
        sa.column("notes", sa.Text()),
        sa.column("source_type", sa.String()),
        sa.column("package_name", sa.String()),
        sa.column("currency", sa.String()),
        sa.column("commercial_license", sa.Boolean()),
        sa.column("payment_mode", sa.String()),
        sa.column("fulfillment_mode", sa.String()),
        sa.column("contract_snapshot", sa.JSON()),
    )
    rows = bind.execute(
        sa.select(
            orders.c.id,
            orders.c.package_snapshot,
            orders.c.appointment_time,
            orders.c.duration_minutes,
            orders.c.notes,
        )
    ).mappings().all()
    for row in rows:
        snapshot = {
            "version": 1,
            "source": {"type": "legacy", "id": None, "application_id": None},
            "currency": "CNY",
            "title": row["package_snapshot"],
            "pricing": {"package_price": None, "final_price": None, "currency": "CNY"},
            "schedule": {
                "appointment_time": row["appointment_time"].isoformat() if row["appointment_time"] else None,
                "duration_minutes": row["duration_minutes"],
                "service_location": None,
                "delivery_due_at": None,
            },
            "deliverables": {},
            "license": {"commercial_license": False, "copyright_terms": None},
            "policies": {"cancellation": None, "reschedule": None},
            "payment_mode": "full",
            "fulfillment_mode": "single_delivery",
            "customer_notes": row["notes"],
            "legacy": True,
        }
        bind.execute(
            orders.update().where(orders.c.id == row["id"]).values(
                source_type="legacy",
                package_name=row["package_snapshot"],
                currency="CNY",
                commercial_license=False,
                payment_mode="full",
                fulfillment_mode="single_delivery",
                contract_snapshot=snapshot,
            )
        )


def upgrade() -> None:
    with op.batch_alter_table("orders") as batch_op:
        for column in ORDER_COLUMNS:
            batch_op.add_column(column)
        batch_op.create_index("ix_orders_source_type", ["source_type"])
        batch_op.create_index("ix_orders_source_id", ["source_id"])
        batch_op.create_index("ix_orders_source_application_id", ["source_application_id"])
        batch_op.create_index("ix_orders_package_id", ["package_id"])

    bind = op.get_bind()
    _backfill_package_ids(bind)
    _backfill_legacy_contracts(bind)


def downgrade() -> None:
    with op.batch_alter_table("orders") as batch_op:
        batch_op.drop_index("ix_orders_package_id")
        batch_op.drop_index("ix_orders_source_application_id")
        batch_op.drop_index("ix_orders_source_id")
        batch_op.drop_index("ix_orders_source_type")
        for column in reversed(ORDER_COLUMNS):
            batch_op.drop_column(column.name)
