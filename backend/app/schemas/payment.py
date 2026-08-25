"""支付、退款与结算相关 Schema 定义"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class PaymentCreateRequest(BaseModel):
    """发起支付请求"""

    model_config = ConfigDict(extra="forbid")
    idempotency_key: str = Field(..., min_length=8, max_length=80)


class PaymentCallbackRequest(BaseModel):
    """支付回调请求"""

    model_config = ConfigDict(extra="forbid")
    payment_no: str
    provider_transaction_id: str
    amount: Decimal
    currency: str
    status: str
    signature: str


class MockPaymentConfirmRequest(BaseModel):
    """模拟支付确认请求"""

    model_config = ConfigDict(extra="forbid")
    provider_transaction_id: str | None = None


class PaymentResponse(BaseModel):
    """支付记录响应"""

    id: int
    payment_no: str
    order_id: int
    customer_id: int
    purpose: str
    amount: Decimal
    currency: str
    status: str
    provider: str
    provider_transaction_id: str | None = None
    expires_at: datetime
    paid_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RefundResponse(BaseModel):
    """退款记录响应"""

    id: int
    refund_no: str
    order_id: int
    payment_id: int | None = None
    customer_id: int
    amount: Decimal
    currency: str
    status: str
    reason_code: str
    reason: str | None = None
    responsibility_party: str
    breach_fee: Decimal
    platform_compensation: Decimal
    requested_by: int | None = None
    provider_refund_id: str | None = None
    requested_at: datetime
    completed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class SettlementResponse(BaseModel):
    """结算记录响应"""

    id: int
    settlement_no: str
    order_id: int
    photographer_id: int
    gross_amount: Decimal
    platform_fee_amount: Decimal
    net_amount: Decimal
    currency: str
    status: str
    frozen_reason: str | None = None
    settled_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrderFinancialSummaryResponse(BaseModel):
    """订单财务汇总响应"""

    order_id: int
    payment_status: str
    payment_due_at: datetime | None = None
    final_price: Decimal | None = None
    escrow_amount: Decimal
    refunded_amount: Decimal
    settled_amount: Decimal
    payments: list[PaymentResponse] = Field(default_factory=list)
    refunds: list[RefundResponse] = Field(default_factory=list)
    settlement: SettlementResponse | None = None
