"""add payment, escrow, refund and settlement records

Revision ID: b7c8d9e0f1a2
Revises: a6b7c8d9e0f1
Create Date: 2026-07-15 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7c8d9e0f1a2"
down_revision: Union[str, Sequence[str], None] = "a6b7c8d9e0f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'AWAITING_PAYMENT'")

    with op.batch_alter_table("orders") as batch_op:
        batch_op.add_column(sa.Column("payment_status", sa.String(30), nullable=False, server_default="unpaid"))
        batch_op.add_column(sa.Column("after_sales_status", sa.String(30), nullable=False, server_default="none"))
        batch_op.add_column(sa.Column("payment_due_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("deposit_rate", sa.Numeric(5, 4), nullable=False, server_default="0.3000"))
        batch_op.add_column(sa.Column("escrow_amount", sa.Numeric(12, 2), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("refunded_amount", sa.Numeric(12, 2), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("settled_amount", sa.Numeric(12, 2), nullable=False, server_default="0"))
        batch_op.create_index("ix_orders_payment_status", ["payment_status"])
        batch_op.create_index("ix_orders_after_sales_status", ["after_sales_status"])

    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("payment_no", sa.String(48), nullable=False),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("purpose", sa.String(20), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="CNY"),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("provider", sa.String(24), nullable=False, server_default="mock"),
        sa.Column("provider_transaction_id", sa.String(80), nullable=True),
        sa.Column("idempotency_key", sa.String(80), nullable=False),
        sa.Column("callback_payload", sa.JSON(), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("currency = 'CNY'", name="ck_payments_currency_cny"),
    )
    for name, columns, unique in [
        ("ix_payments_payment_no", ["payment_no"], True),
        ("ix_payments_order_id", ["order_id"], False),
        ("ix_payments_customer_id", ["customer_id"], False),
        ("ix_payments_status", ["status"], False),
        ("ix_payments_provider_transaction_id", ["provider_transaction_id"], True),
        ("ix_payments_idempotency_key", ["idempotency_key"], True),
        ("ix_payments_expires_at", ["expires_at"], False),
    ]:
        op.create_index(name, "payments", columns, unique=unique)

    op.create_table(
        "refunds",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("refund_no", sa.String(48), nullable=False),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("payment_id", sa.Integer(), sa.ForeignKey("payments.id"), nullable=True),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="CNY"),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("reason_code", sa.String(40), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("responsibility_party", sa.String(24), nullable=False),
        sa.Column("breach_fee", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("platform_compensation", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("requested_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("approved_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("provider_refund_id", sa.String(80), nullable=True),
        sa.Column("idempotency_key", sa.String(80), nullable=False),
        sa.Column("adjustment_note", sa.Text(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("currency = 'CNY'", name="ck_refunds_currency_cny"),
    )
    for name, columns, unique in [
        ("ix_refunds_refund_no", ["refund_no"], True),
        ("ix_refunds_order_id", ["order_id"], False),
        ("ix_refunds_payment_id", ["payment_id"], False),
        ("ix_refunds_customer_id", ["customer_id"], False),
        ("ix_refunds_status", ["status"], False),
        ("ix_refunds_idempotency_key", ["idempotency_key"], True),
    ]:
        op.create_index(name, "refunds", columns, unique=unique)
    op.create_index("uq_refunds_provider_refund_id", "refunds", ["provider_refund_id"], unique=True)

    op.create_table(
        "settlements",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("settlement_no", sa.String(48), nullable=False),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("photographer_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("gross_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("platform_fee_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("net_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="CNY"),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("idempotency_key", sa.String(80), nullable=False),
        sa.Column("frozen_reason", sa.Text(), nullable=True),
        sa.Column("settled_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("currency = 'CNY'", name="ck_settlements_currency_cny"),
    )
    op.create_index("ix_settlements_settlement_no", "settlements", ["settlement_no"], unique=True)
    op.create_index("ix_settlements_order_id", "settlements", ["order_id"], unique=True)
    op.create_index("ix_settlements_photographer_id", "settlements", ["photographer_id"])
    op.create_index("ix_settlements_status", "settlements", ["status"])
    op.create_index("ix_settlements_idempotency_key", "settlements", ["idempotency_key"], unique=True)


def downgrade() -> None:
    op.drop_table("settlements")
    op.drop_table("refunds")
    op.drop_table("payments")
    with op.batch_alter_table("orders") as batch_op:
        batch_op.drop_index("ix_orders_after_sales_status")
        batch_op.drop_index("ix_orders_payment_status")
        for column in [
            "settled_amount",
            "refunded_amount",
            "escrow_amount",
            "deposit_rate",
            "payment_due_at",
            "after_sales_status",
            "payment_status",
        ]:
            batch_op.drop_column(column)
