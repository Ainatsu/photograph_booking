"""支付与担保相关 API 路由。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_active_user
from backend.app.core.database import get_db
from backend.app.models.payment import Payment
from backend.app.models.user import User
from backend.app.schemas.payment import (
    MockPaymentConfirmRequest,
    OrderFinancialSummaryResponse,
    PaymentCallbackRequest,
    PaymentCreateRequest,
    PaymentResponse,
)
from backend.app.services.order_service import (
    get_latest_order_event,
    get_order_by_id,
    push_order_event_update,
)
from backend.app.services.payment_service import (
    create_payment,
    get_order_financial_summary,
    mock_confirm_payment,
    process_payment_callback,
)


router = APIRouter(prefix="/payments", tags=["支付与担保"])


@router.post("/orders/{order_id}", response_model=PaymentResponse, status_code=201)
def create_order_payment(
    order_id: int,
    data: PaymentCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """为订单创建支付单并返回支付信息。"""
    order = get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    payment = create_payment(db, order, current_user.id, data.idempotency_key)
    db.commit()
    db.refresh(payment)
    return payment


@router.post("/{payment_id}/mock-confirm", response_model=PaymentResponse)
async def confirm_mock_payment(
    payment_id: int,
    data: MockPaymentConfirmRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """确认模拟支付，更新支付单状态并推送订单事件。"""
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="支付单不存在")
    if payment.customer_id != current_user.id:
        raise HTTPException(status_code=403, detail="只能支付自己的订单")
    payment = mock_confirm_payment(db, payment, data.provider_transaction_id)
    await push_order_event_update(get_latest_order_event(db, payment.order_id))
    return payment


@router.post("/callbacks/mock", response_model=PaymentResponse)
async def mock_payment_callback(data: PaymentCallbackRequest, db: Session = Depends(get_db)):
    """处理模拟支付回调并推送最新订单事件。"""
    payment = process_payment_callback(db, data)
    await push_order_event_update(get_latest_order_event(db, payment.order_id))
    return payment


@router.get("/orders/{order_id}", response_model=OrderFinancialSummaryResponse)
def get_financial_summary(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """获取订单的财务汇总数据（仅订单相关方可查看）。"""
    order = get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if current_user.id not in {order.customer_id, order.photographer_id} and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="无权查看该订单财务记录")
    return get_order_financial_summary(db, order)
