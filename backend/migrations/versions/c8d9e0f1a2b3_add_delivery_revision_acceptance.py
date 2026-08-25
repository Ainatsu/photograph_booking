"""add versioned delivery, revision and acceptance workflow

Revision ID: c8d9e0f1a2b3
Revises: b7c8d9e0f1a2
Create Date: 2026-07-15 02:00:00.000000
"""

from datetime import datetime, timedelta
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c8d9e0f1a2b3"
down_revision: Union[str, Sequence[str], None] = "b7c8d9e0f1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    required_order_columns = {
        "acceptance_deadline_at",
        "completed_at",
        "completion_type",
        "revision_used_count",
    }
    existing_order_columns = {item["name"] for item in inspector.get_columns("orders")}
    required_tables = {"order_deliveries", "order_delivery_files", "order_revision_requests"}
    existing_tables = set(inspector.get_table_names())
    if required_order_columns.issubset(existing_order_columns) and required_tables.issubset(existing_tables):
        required_indexes = {
            "orders": [("ix_orders_acceptance_deadline_at", ["acceptance_deadline_at"], False)],
            "order_deliveries": [
                ("ix_order_deliveries_order_id", ["order_id"], False),
                ("ix_order_deliveries_status", ["status"], False),
                ("ix_order_deliveries_idempotency_key", ["idempotency_key"], True),
            ],
            "order_delivery_files": [
                ("ix_order_delivery_files_delivery_id", ["delivery_id"], False),
                ("ix_order_delivery_files_checksum", ["checksum"], False),
            ],
            "order_revision_requests": [
                ("ix_order_revision_requests_order_id", ["order_id"], False),
                ("ix_order_revision_requests_delivery_id", ["delivery_id"], False),
                ("ix_order_revision_requests_status", ["status"], False),
                ("ix_order_revision_requests_idempotency_key", ["idempotency_key"], True),
            ],
        }
        for table_name, definitions in required_indexes.items():
            existing_indexes = {item["name"] for item in sa.inspect(bind).get_indexes(table_name)}
            for index_name, columns, unique in definitions:
                if index_name not in existing_indexes:
                    op.create_index(index_name, table_name, columns, unique=unique)
        _backfill_legacy_deliveries(bind)
        return
    if bind.dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.execute("ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'COMPLETED'")

    with op.batch_alter_table("orders") as batch_op:
        batch_op.add_column(sa.Column("acceptance_deadline_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("completed_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("completion_type", sa.String(24), nullable=True))
        batch_op.add_column(sa.Column("revision_used_count", sa.Integer(), nullable=False, server_default="0"))
        batch_op.create_index("ix_orders_acceptance_deadline_at", ["acceptance_deadline_at"])

    op.create_table(
        "order_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("submitted_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("file_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(24), nullable=False, server_default="submitted"),
        sa.Column("idempotency_key", sa.String(80), nullable=False),
        sa.Column("acceptance_deadline_at", sa.DateTime(), nullable=True),
        sa.Column("accepted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("order_id", "version", name="uq_order_deliveries_order_version"),
    )
    op.create_index("ix_order_deliveries_order_id", "order_deliveries", ["order_id"])
    op.create_index("ix_order_deliveries_status", "order_deliveries", ["status"])
    op.create_index("ix_order_deliveries_idempotency_key", "order_deliveries", ["idempotency_key"], unique=True)

    op.create_table(
        "order_delivery_files",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("delivery_id", sa.Integer(), sa.ForeignKey("order_deliveries.id"), nullable=False),
        sa.Column("file_url", sa.Text(), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_type", sa.String(120), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("checksum", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_order_delivery_files_delivery_id", "order_delivery_files", ["delivery_id"])
    op.create_index("ix_order_delivery_files_checksum", "order_delivery_files", ["checksum"])

    op.create_table(
        "order_revision_requests",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("delivery_id", sa.Integer(), sa.ForeignKey("order_deliveries.id"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("requested_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=False),
        sa.Column("reference_files", sa.JSON(), nullable=True),
        sa.Column("counts_as_free", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("status", sa.String(24), nullable=False, server_default="requested"),
        sa.Column("idempotency_key", sa.String(80), nullable=False),
        sa.Column("response_due_at", sa.DateTime(), nullable=False),
        sa.Column("expected_redelivery_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("order_id", "sequence", name="uq_order_revision_requests_order_sequence"),
    )
    op.create_index("ix_order_revision_requests_order_id", "order_revision_requests", ["order_id"])
    op.create_index("ix_order_revision_requests_delivery_id", "order_revision_requests", ["delivery_id"])
    op.create_index("ix_order_revision_requests_status", "order_revision_requests", ["status"])
    op.create_index("ix_order_revision_requests_idempotency_key", "order_revision_requests", ["idempotency_key"], unique=True)

    orders = sa.table(
        "orders",
        sa.column("id", sa.Integer()),
        sa.column("photographer_id", sa.Integer()),
        sa.column("status", sa.String()),
        sa.column("delivery", sa.JSON()),
        sa.column("acceptance_deadline_at", sa.DateTime()),
    )
    deliveries = sa.table(
        "order_deliveries",
        sa.column("id", sa.Integer()),
        sa.column("order_id", sa.Integer()),
        sa.column("version", sa.Integer()),
        sa.column("submitted_by", sa.Integer()),
        sa.column("description", sa.Text()),
        sa.column("file_count", sa.Integer()),
        sa.column("status", sa.String()),
        sa.column("idempotency_key", sa.String()),
        sa.column("acceptance_deadline_at", sa.DateTime()),
    )
    delivery_files = sa.table(
        "order_delivery_files",
        sa.column("delivery_id", sa.Integer()),
        sa.column("file_url", sa.Text()),
        sa.column("file_name", sa.String()),
        sa.column("file_type", sa.String()),
    )
    deadline = datetime.utcnow() + timedelta(days=5)
    for row in bind.execute(sa.select(orders)).mappings():
        payload = row.get("delivery") or {}
        images = payload.get("images") if isinstance(payload, dict) else None
        if not images:
            continue
        delivery_deadline = deadline if row.get("status") == "DELIVERED" else None
        result = bind.execute(
            deliveries.insert().values(
                order_id=row["id"],
                version=1,
                submitted_by=row["photographer_id"],
                description=payload.get("description"),
                file_count=len(images),
                status="submitted" if row.get("status") == "DELIVERED" else "accepted",
                idempotency_key=f"legacy-delivery:{row['id']}",
                acceptance_deadline_at=delivery_deadline,
            )
        )
        delivery_id = bind.execute(
            sa.select(deliveries.c.id).where(deliveries.c.idempotency_key == f"legacy-delivery:{row['id']}")
        ).scalar_one()
        for index, url in enumerate(images, start=1):
            bind.execute(
                delivery_files.insert().values(
                    delivery_id=delivery_id,
                    file_url=url,
                    file_name=f"legacy-{index}",
                    file_type="image/unknown",
                )
            )
        if delivery_deadline:
            bind.execute(
                orders.update().where(orders.c.id == row["id"]).values(acceptance_deadline_at=delivery_deadline)
            )


def downgrade() -> None:
    op.drop_table("order_revision_requests")
    op.drop_table("order_delivery_files")
    op.drop_table("order_deliveries")
    with op.batch_alter_table("orders") as batch_op:
        batch_op.drop_index("ix_orders_acceptance_deadline_at")
        batch_op.drop_column("revision_used_count")
        batch_op.drop_column("completion_type")
        batch_op.drop_column("completed_at")
        batch_op.drop_column("acceptance_deadline_at")


def _backfill_legacy_deliveries(bind) -> None:
    orders = sa.table(
        "orders",
        sa.column("id", sa.Integer()),
        sa.column("photographer_id", sa.Integer()),
        sa.column("status", sa.String()),
        sa.column("delivery", sa.JSON()),
        sa.column("acceptance_deadline_at", sa.DateTime()),
    )
    deliveries = sa.table(
        "order_deliveries",
        sa.column("id", sa.Integer()),
        sa.column("order_id", sa.Integer()),
        sa.column("version", sa.Integer()),
        sa.column("submitted_by", sa.Integer()),
        sa.column("description", sa.Text()),
        sa.column("file_count", sa.Integer()),
        sa.column("status", sa.String()),
        sa.column("idempotency_key", sa.String()),
        sa.column("acceptance_deadline_at", sa.DateTime()),
    )
    delivery_files = sa.table(
        "order_delivery_files",
        sa.column("delivery_id", sa.Integer()),
        sa.column("file_url", sa.Text()),
        sa.column("file_name", sa.String()),
        sa.column("file_type", sa.String()),
    )
    existing_order_ids = set(bind.execute(sa.select(deliveries.c.order_id)).scalars())
    deadline = datetime.utcnow() + timedelta(days=5)
    for row in bind.execute(sa.select(orders)).mappings():
        if row["id"] in existing_order_ids:
            continue
        payload = row.get("delivery") or {}
        images = payload.get("images") if isinstance(payload, dict) else None
        if not images:
            continue
        is_delivered = str(row.get("status") or "").upper() == "DELIVERED"
        delivery_deadline = deadline if is_delivered else None
        result = bind.execute(
            deliveries.insert().values(
                order_id=row["id"],
                version=1,
                submitted_by=row["photographer_id"],
                description=payload.get("description"),
                file_count=len(images),
                status="submitted" if is_delivered else "accepted",
                idempotency_key=f"legacy-delivery:{row['id']}",
                acceptance_deadline_at=delivery_deadline,
            )
        )
        delivery_id = bind.execute(
            sa.select(deliveries.c.id).where(deliveries.c.idempotency_key == f"legacy-delivery:{row['id']}")
        ).scalar_one()
        for index, url in enumerate(images, start=1):
            bind.execute(
                delivery_files.insert().values(
                    delivery_id=delivery_id,
                    file_url=url,
                    file_name=f"legacy-{index}",
                    file_type="image/unknown",
                )
            )
        if delivery_deadline:
            bind.execute(
                orders.update().where(orders.c.id == row["id"]).values(acceptance_deadline_at=delivery_deadline)
            )
