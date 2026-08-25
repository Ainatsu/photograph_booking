"""normalize structured order contracts and enforce CNY

Revision ID: a6b7c8d9e0f1
Revises: f5a6b7c8d9e0
Create Date: 2026-07-15 00:30:00.000000

"""
import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a6b7c8d9e0f1"
down_revision: Union[str, Sequence[str], None] = "f5a6b7c8d9e0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _legacy_snapshot(row) -> dict:
    appointment_time = row["appointment_time"]
    return {
        "version": 1,
        "source": {"type": "legacy", "id": None, "application_id": None},
        "currency": "CNY",
        "title": row["package_snapshot"],
        "pricing": {"package_price": None, "final_price": None, "currency": "CNY"},
        "schedule": {
            "appointment_time": appointment_time.isoformat() if appointment_time else None,
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


def _normalize_contracts(bind) -> None:
    orders = sa.table(
        "orders",
        sa.column("id", sa.Integer()),
        sa.column("package_snapshot", sa.String()),
        sa.column("package_name", sa.String()),
        sa.column("appointment_time", sa.DateTime()),
        sa.column("duration_minutes", sa.Integer()),
        sa.column("notes", sa.Text()),
        sa.column("source_type", sa.String()),
        sa.column("currency", sa.String()),
        sa.column("commercial_license", sa.Boolean()),
        sa.column("payment_mode", sa.String()),
        sa.column("fulfillment_mode", sa.String()),
        sa.column("contract_snapshot", sa.JSON()),
    )
    rows = bind.execute(sa.select(orders)).mappings().all()
    for row in rows:
        snapshot = row["contract_snapshot"]
        if isinstance(snapshot, str):
            try:
                snapshot = json.loads(snapshot)
            except json.JSONDecodeError:
                snapshot = None
        if not isinstance(snapshot, dict):
            snapshot = _legacy_snapshot(row)
        else:
            snapshot = dict(snapshot)
            source = dict(snapshot.get("source") or {})
            source["type"] = source.get("type") or row["source_type"] or "legacy"
            source.setdefault("id", None)
            source.setdefault("application_id", None)
            snapshot["source"] = source
            snapshot["currency"] = "CNY"

            pricing = dict(snapshot.get("pricing") or {})
            pricing["currency"] = "CNY"
            pricing.setdefault("package_price", None)
            pricing.setdefault("final_price", None)
            snapshot["pricing"] = pricing
            snapshot.setdefault("deliverables", {})
            snapshot.setdefault(
                "license",
                {"commercial_license": False, "copyright_terms": None},
            )
            snapshot.setdefault("policies", {"cancellation": None, "reschedule": None})
            snapshot.setdefault("payment_mode", row["payment_mode"] or "full")
            snapshot.setdefault(
                "fulfillment_mode",
                row["fulfillment_mode"] or "single_delivery",
            )

        source_type = (snapshot.get("source") or {}).get("type") or "legacy"
        values = {
            "source_type": source_type,
            "currency": "CNY",
            "commercial_license": bool(
                (snapshot.get("license") or {}).get("commercial_license", False)
            ),
            "payment_mode": snapshot.get("payment_mode") or "full",
            "fulfillment_mode": snapshot.get("fulfillment_mode") or "single_delivery",
            "contract_snapshot": snapshot,
        }
        if source_type == "legacy" and not row["package_name"]:
            values["package_name"] = row["package_snapshot"]
        bind.execute(
            orders.update().where(orders.c.id == row["id"]).values(**values)
        )


def upgrade() -> None:
    bind = op.get_bind()
    _normalize_contracts(bind)
    with op.batch_alter_table("orders") as batch_op:
        batch_op.create_check_constraint("ck_orders_currency_cny", "currency = 'CNY'")


def downgrade() -> None:
    with op.batch_alter_table("orders") as batch_op:
        batch_op.drop_constraint("ck_orders_currency_cny", type_="check")
