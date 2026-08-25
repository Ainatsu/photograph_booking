"""add disputes, evidence and admin audit logs

Revision ID: d9e0f1a2b3c4
Revises: c8d9e0f1a2b3
Create Date: 2026-07-15 17:20:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d9e0f1a2b3c4"
down_revision: Union[str, Sequence[str], None] = "c8d9e0f1a2b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _ensure_indexes(table_name: str, definitions: list[tuple[str, list[str], bool]]) -> None:
    bind = op.get_bind()
    existing = {item["name"] for item in sa.inspect(bind).get_indexes(table_name)}
    for name, columns, unique in definitions:
        if name not in existing:
            op.create_index(name, table_name, columns, unique=unique)


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    if "order_disputes" not in tables:
        op.create_table(
            "order_disputes",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("dispute_no", sa.String(48), nullable=False),
            sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=False),
            sa.Column("opened_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("opened_by_role", sa.String(20), nullable=False),
            sa.Column("reason_code", sa.String(40), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("requested_resolution", sa.String(40), nullable=False),
            sa.Column("status", sa.String(24), nullable=False, server_default="open"),
            sa.Column("assigned_admin_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("resolution", sa.String(40), nullable=True),
            sa.Column("resolution_note", sa.Text(), nullable=True),
            sa.Column("refund_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
            sa.Column("currency", sa.String(3), nullable=False, server_default="CNY"),
            sa.Column("previous_after_sales_status", sa.String(30), nullable=False, server_default="none"),
            sa.Column("acceptance_deadline_snapshot", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("resolved_at", sa.DateTime(), nullable=True),
            sa.CheckConstraint("currency = 'CNY'", name="ck_order_disputes_currency_cny"),
        )
    _ensure_indexes("order_disputes", [
        ("ix_order_disputes_dispute_no", ["dispute_no"], True),
        ("ix_order_disputes_order_id", ["order_id"], False),
        ("ix_order_disputes_opened_by", ["opened_by"], False),
        ("ix_order_disputes_status", ["status"], False),
        ("ix_order_disputes_assigned_admin_id", ["assigned_admin_id"], False),
    ])

    tables = set(sa.inspect(bind).get_table_names())
    if "order_dispute_evidence" not in tables:
        op.create_table(
            "order_dispute_evidence",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("dispute_id", sa.Integer(), sa.ForeignKey("order_disputes.id"), nullable=False),
            sa.Column("submitted_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("submitter_role", sa.String(20), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("file_url", sa.Text(), nullable=True),
            sa.Column("file_name", sa.String(255), nullable=True),
            sa.Column("file_type", sa.String(120), nullable=True),
            sa.Column("file_size", sa.Integer(), nullable=True),
            sa.Column("checksum", sa.String(64), nullable=True),
            sa.Column("reference_type", sa.String(40), nullable=True),
            sa.Column("reference_id", sa.String(64), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
    _ensure_indexes("order_dispute_evidence", [
        ("ix_order_dispute_evidence_dispute_id", ["dispute_id"], False),
        ("ix_order_dispute_evidence_submitted_by", ["submitted_by"], False),
        ("ix_order_dispute_evidence_checksum", ["checksum"], False),
    ])

    tables = set(sa.inspect(bind).get_table_names())
    if "admin_audit_logs" not in tables:
        op.create_table(
            "admin_audit_logs",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("admin_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("action", sa.String(60), nullable=False),
            sa.Column("resource_type", sa.String(40), nullable=False),
            sa.Column("resource_id", sa.String(64), nullable=False),
            sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=True),
            sa.Column("before_data", sa.JSON(), nullable=True),
            sa.Column("after_data", sa.JSON(), nullable=True),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
    _ensure_indexes("admin_audit_logs", [
        ("ix_admin_audit_logs_admin_id", ["admin_id"], False),
        ("ix_admin_audit_logs_action", ["action"], False),
        ("ix_admin_audit_logs_resource_type", ["resource_type"], False),
        ("ix_admin_audit_logs_resource_id", ["resource_id"], False),
        ("ix_admin_audit_logs_order_id", ["order_id"], False),
    ])


def downgrade() -> None:
    op.drop_table("admin_audit_logs")
    op.drop_table("order_dispute_evidence")
    op.drop_table("order_disputes")
