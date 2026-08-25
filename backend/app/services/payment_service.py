"""阶段 C：支付、退款、担保和结算领域服务。

默认 provider 是内置 mock provider，但所有回调仍经过与真实支付网关相同的
金额、币种、签名、流水号和幂等校验，后续可替换 provider 而不改订单流程。
"""

import hashlib
import hmac
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from backend.app.core.config import settings
from backend.app.models.order import Order, OrderStatus
from backend.app.models.payment import Payment, PaymentStatus, Refund, Settlement, SettlementStatus
from backend.app.models.order_event import OrderEvent
from backend.app.schemas.payment import PaymentCallbackRequest


CURRENCY_CNY = "CNY"
MONEY_QUANTUM = Decimal("0.01")


def _now() -> datetime:
    """返回去除时区信息的当前 UTC 时间。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _money(value) -> Decimal:
    """将数值规范化为保留两位小数的金额。"""
    if value is None:
        return Decimal("0.00")
    return Decimal(str(value)).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def _new_no(prefix: str) -> str:
    """生成带指定前缀的唯一流水号。"""
    return f"{prefix}-{uuid.uuid4().hex[:24].upper()}"


def _record_financial_event(db: Session, order: Order, event_type: str, note: str, status_value=None) -> None:
    """为订单记录一条财务相关的事件流水。"""
    from backend.app.services.order_service import record_order_event
    record_order_event(
        db,
        order.id,
        None,
        "system",
        event_type,
        status_value or (order.status.value if hasattr(order.status, "value") else str(order.status)),
        note,
    )


def _captured_amount(db: Session, order_id: int) -> Decimal:
    """统计订单已成功捕获的支付金额合计。"""
    captured = db.query(func.coalesce(func.sum(Payment.amount), 0)).filter(
        Payment.order_id == order_id,
        Payment.status.in_([
            PaymentStatus.SUCCEEDED.value,
            PaymentStatus.PARTIALLY_REFUNDED.value,
            PaymentStatus.REFUNDED.value,
        ]),
    ).scalar()
    return _money(captured)


def _refunded_amount(db: Session, order_id: int) -> Decimal:
    """统计订单已成功退款金额合计。"""
    refunded = db.query(func.coalesce(func.sum(Refund.amount), 0)).filter(
        Refund.order_id == order_id,
        Refund.status == "succeeded",
    ).scalar()
    return _money(refunded)


def _settled_gross_amount(db: Session, order_id: int) -> Decimal:
    """统计订单已结算的毛收入金额合计。"""
    settled = db.query(func.coalesce(func.sum(Settlement.gross_amount), 0)).filter(
        Settlement.order_id == order_id,
        Settlement.status == SettlementStatus.SETTLED.value,
    ).scalar()
    return _money(settled)


def available_escrow_amount(db: Session, order: Order) -> Decimal:
    """计算订单当前可用的担保余额（捕获减去退款与结算）。"""
    return max(
        Decimal("0.00"),
        _captured_amount(db, order.id)
        - _refunded_amount(db, order.id)
        - _settled_gross_amount(db, order.id),
    )


def ensure_order_not_settled(db: Session, order: Order) -> None:
    """校验订单尚未结算，已结算则抛出 409 异常。"""
    settled = db.query(Settlement.id).filter(
        Settlement.order_id == order.id,
        Settlement.status == SettlementStatus.SETTLED.value,
    ).first()
    if settled:
        raise HTTPException(status_code=409, detail="订单资金已结算，不能直接取消退款")


def required_order_amount(order: Order) -> Decimal:
    """返回订单需支付的人民币成交金额，金额无效时抛异常。"""
    amount = _money(order.final_price)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="该订单没有可支付的人民币成交金额")
    return amount


def deposit_amount(order: Order) -> Decimal:
    """按定金比例计算订单应付定金金额。"""
    rate = _money(order.deposit_rate or settings.DEFAULT_DEPOSIT_RATE)
    if rate <= 0 or rate > 1:
        rate = _money(settings.DEFAULT_DEPOSIT_RATE)
    return (required_order_amount(order) * rate).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def payment_signature(payment_no: str, provider_transaction_id: str, amount, currency: str, payment_status: str) -> str:
    """使用回调密钥对支付关键信息计算 HMAC 签名。"""
    canonical = f"{payment_no}|{provider_transaction_id}|{_money(amount):.2f}|{currency}|{payment_status}"
    return hmac.new(
        settings.PAYMENT_CALLBACK_SECRET.encode("utf-8"),
        canonical.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _verify_callback_signature(data: PaymentCallbackRequest) -> None:
    """校验支付回调签名，不匹配时抛出 400 异常。"""
    expected = payment_signature(
        data.payment_no,
        data.provider_transaction_id,
        data.amount,
        data.currency,
        data.status,
    )
    if not hmac.compare_digest(expected, data.signature):
        raise HTTPException(status_code=400, detail="支付回调签名无效")


def expire_payment_orders(db: Session, commit: bool = True) -> list[int]:
    """将超时未支付的支付单标记过期，并取消相关订单。"""
    now = _now()
    expired_order_ids: set[int] = set()
    expired_payments = db.query(Payment).filter(
        Payment.status == PaymentStatus.PENDING.value,
        Payment.expires_at <= now,
    ).all()
    changed_orders = []
    for payment in expired_payments:
        payment.status = PaymentStatus.EXPIRED.value
        payment.failure_reason = "支付超时"
        order = payment.order
        if (
            order
            and payment.purpose in {"full", "deposit"}
            and order.status == OrderStatus.AWAITING_PAYMENT
            and _captured_amount(db, order.id) <= 0
        ):
            order.status = OrderStatus.CANCELLED
            order.payment_status = "payment_failed"
            order.cancellation_reason = "支付超时，档期已释放"
            order.cancelled_by = "system"
            order.payment_due_at = None
            from backend.app.services.automation_service import refresh_order_action_metadata
            refresh_order_action_metadata(db, order)
            _record_financial_event(db, order, "payment_expired", "支付超时，订单已取消并释放档期", "cancelled")
            changed_orders.append(order)
            expired_order_ids.add(order.id)

    overdue_orders = db.query(Order).filter(
        Order.status == OrderStatus.AWAITING_PAYMENT,
        Order.payment_due_at.isnot(None),
        Order.payment_due_at <= now,
    ).all()
    for order in overdue_orders:
        order.status = OrderStatus.CANCELLED
        order.payment_status = "payment_failed"
        order.cancellation_reason = "支付超时，档期已释放"
        order.cancelled_by = "system"
        order.payment_due_at = None
        from backend.app.services.automation_service import refresh_order_action_metadata
        refresh_order_action_metadata(db, order)
        _record_financial_event(db, order, "payment_expired", "支付超时，订单已取消并释放档期", "cancelled")
        expired_order_ids.add(order.id)

    if commit and (expired_payments or changed_orders or overdue_orders):
        db.commit()
    return sorted(expired_order_ids)


def create_payment(db: Session, order: Order, customer_id: int, idempotency_key: str) -> Payment:
    """为订单创建支付单，支持幂等与定金/尾款/全额模式。"""
    expire_payment_orders(db)
    if order.customer_id != customer_id:
        raise HTTPException(status_code=403, detail="只能为自己的订单付款")

    existing_key = db.query(Payment).filter(Payment.idempotency_key == idempotency_key).first()
    if existing_key:
        if existing_key.order_id != order.id:
            raise HTTPException(status_code=409, detail="幂等键已用于其他订单")
        return existing_key

    captured = available_escrow_amount(db, order)
    if order.payment_mode == "deposit_balance" and captured <= 0:
        purpose = "deposit"
        amount = deposit_amount(order)
    elif order.payment_mode == "deposit_balance":
        purpose = "balance"
        amount = max(Decimal("0.00"), required_order_amount(order) - captured)
    else:
        purpose = "full"
        amount = max(Decimal("0.00"), required_order_amount(order) - captured)

    allowed_statuses = {OrderStatus.AWAITING_PAYMENT}
    if purpose == "balance":
        allowed_statuses.add(OrderStatus.CONFIRMED)
    if order.status not in allowed_statuses:
        raise HTTPException(status_code=400, detail="当前订单状态不可创建支付单")
    if amount <= 0:
        raise HTTPException(status_code=400, detail="该订单已完成支付")

    pending = db.query(Payment).filter(
        Payment.order_id == order.id,
        Payment.purpose == purpose,
        Payment.status == PaymentStatus.PENDING.value,
    ).order_by(Payment.id.desc()).first()
    if pending:
        return pending

    expires_at = order.payment_due_at or (_now() + timedelta(minutes=settings.PAYMENT_WINDOW_MINUTES))
    payment = Payment(
        payment_no=_new_no("PAY"),
        order_id=order.id,
        customer_id=customer_id,
        purpose=purpose,
        amount=amount,
        currency=CURRENCY_CNY,
        status=PaymentStatus.PENDING.value,
        provider=settings.PAYMENT_PROVIDER,
        idempotency_key=idempotency_key,
        expires_at=expires_at,
    )
    db.add(payment)
    db.flush()
    db.refresh(payment)
    return payment


def process_payment_callback(db: Session, data: PaymentCallbackRequest) -> Payment:
    """处理支付网关回调，校验后更新支付单与订单状态。"""
    _verify_callback_signature(data)
    if data.currency != CURRENCY_CNY:
        raise HTTPException(status_code=400, detail="仅支持人民币 CNY")
    if data.status not in {"succeeded", "failed"}:
        raise HTTPException(status_code=400, detail="不支持的支付回调状态")

    payment = db.query(Payment).options(joinedload(Payment.order)).filter(
        Payment.payment_no == data.payment_no
    ).first()
    if not payment:
        raise HTTPException(status_code=404, detail="支付单不存在")
    if payment.currency != data.currency or _money(payment.amount) != _money(data.amount):
        raise HTTPException(status_code=400, detail="支付金额或币种与支付单不一致")
    if payment.status == PaymentStatus.SUCCEEDED.value:
        if payment.provider_transaction_id == data.provider_transaction_id:
            return payment
        raise HTTPException(status_code=409, detail="支付单已使用其他流水号完成")
    duplicate_transaction = db.query(Payment).filter(
        Payment.provider_transaction_id == data.provider_transaction_id,
        Payment.id != payment.id,
    ).first()
    if duplicate_transaction:
        raise HTTPException(status_code=409, detail="第三方流水号已处理")

    payment.provider_transaction_id = data.provider_transaction_id
    payment.callback_payload = data.model_dump(mode="json")
    if data.status == "failed":
        payment.status = PaymentStatus.FAILED.value
        payment.failure_reason = "支付失败"
        payment.order.payment_status = "payment_failed"
        _record_financial_event(db, payment.order, "payment_failed", "支付失败，可在支付期限内重新发起")
        db.commit()
        db.refresh(payment)
        return payment

    if payment.expires_at <= _now():
        payment.status = PaymentStatus.EXPIRED.value
        payment.failure_reason = "支付单已过期"
        db.commit()
        raise HTTPException(status_code=409, detail="支付单已过期，请重新发起支付")

    order = payment.order
    if payment.purpose in {"full", "deposit"} and order.status != OrderStatus.AWAITING_PAYMENT:
        raise HTTPException(status_code=409, detail="订单已离开待支付状态")
    if payment.purpose == "balance" and order.status != OrderStatus.CONFIRMED:
        raise HTTPException(status_code=409, detail="当前订单不可支付尾款")

    if payment.purpose in {"full", "deposit"}:
        from backend.app.services.order_service import _ensure_photographer_available
        _ensure_photographer_available(
            db,
            order.photographer_id,
            order.appointment_time,
            order.duration_minutes,
            exclude_order_id=order.id,
        )

    escrow_before = available_escrow_amount(db, order)
    payment.status = PaymentStatus.SUCCEEDED.value
    payment.paid_at = _now()
    total_captured = escrow_before + _money(payment.amount)
    order.escrow_amount = total_captured
    total_required = required_order_amount(order)
    if total_captured >= total_required:
        order.payment_status = "paid_in_escrow"
    else:
        order.payment_status = "deposit_paid"
    if payment.purpose in {"full", "deposit"}:
        order.status = OrderStatus.CONFIRMED
        order.payment_due_at = None
    from backend.app.services.automation_service import refresh_order_action_metadata
    refresh_order_action_metadata(db, order)
    _record_financial_event(
        db,
        order,
        "payment_succeeded",
        f"支付成功：{payment.purpose} ¥{_money(payment.amount):.2f}",
        order.status.value,
    )
    db.commit()
    db.refresh(payment)
    return payment


def mock_confirm_payment(db: Session, payment: Payment, provider_transaction_id: str | None = None) -> Payment:
    """模拟支付网关确认支付并走完整回调流程。"""
    transaction_id = provider_transaction_id or _new_no("MOCKTX")
    data = PaymentCallbackRequest(
        payment_no=payment.payment_no,
        provider_transaction_id=transaction_id,
        amount=_money(payment.amount),
        currency=CURRENCY_CNY,
        status="succeeded",
        signature=payment_signature(payment.payment_no, transaction_id, payment.amount, CURRENCY_CNY, "succeeded"),
    )
    return process_payment_callback(db, data)


def calculate_cancellation_refund(db: Session, order: Order, responsibility_party: str) -> tuple[Decimal, Decimal]:
    """按责任方与距预约时间计算取消订单的退款金额和比例。"""
    available = available_escrow_amount(db, order)
    if available <= 0:
        return Decimal("0.00"), Decimal("0.00")
    if responsibility_party in {"photographer", "admin", "system"}:
        return available, Decimal("1.00")
    if order.status in {OrderStatus.PENDING, OrderStatus.AWAITING_PAYMENT}:
        return available, Decimal("1.00")
    hours_to_appointment = (order.appointment_time - _now()).total_seconds() / 3600
    if hours_to_appointment > 72:
        return (available * Decimal("0.90")).quantize(MONEY_QUANTUM), Decimal("0.90")
    if hours_to_appointment >= 24:
        return (available * Decimal("0.50")).quantize(MONEY_QUANTUM), Decimal("0.50")
    if order.payment_mode == "deposit_balance":
        non_refundable_deposit = deposit_amount(order)
        return max(Decimal("0.00"), available - non_refundable_deposit), Decimal("0.00")
    return Decimal("0.00"), Decimal("0.00")


def refund_cancelled_order(
    db: Session,
    order: Order,
    responsibility_party: str,
    reason: str,
    requested_by: int | None = None,
) -> Refund | None:
    """为已取消订单创建退款记录并更新订单担保余额。"""
    idempotency_key = f"cancel-order:{order.id}:{responsibility_party}"
    existing = db.query(Refund).filter(Refund.idempotency_key == idempotency_key).first()
    if existing:
        return existing
    available_before = available_escrow_amount(db, order)
    amount, refund_rate = calculate_cancellation_refund(db, order, responsibility_party)
    if amount <= 0:
        return None
    refunded_before = _refunded_amount(db, order.id)
    payment = db.query(Payment).filter(
        Payment.order_id == order.id,
        Payment.status.in_([PaymentStatus.SUCCEEDED.value, PaymentStatus.PARTIALLY_REFUNDED.value]),
    ).order_by(Payment.id.asc()).first()
    refund = Refund(
        refund_no=_new_no("REF"),
        order_id=order.id,
        payment_id=payment.id if payment else None,
        customer_id=order.customer_id,
        amount=amount,
        currency=CURRENCY_CNY,
        status="succeeded",
        reason_code="order_cancelled",
        reason=reason,
        responsibility_party=responsibility_party,
        breach_fee=max(Decimal("0.00"), available_escrow_amount(db, order) - amount),
        requested_by=requested_by,
        provider_refund_id=_new_no("MOCKREF"),
        idempotency_key=idempotency_key,
        completed_at=_now(),
    )
    db.add(refund)
    db.flush()
    order.refunded_amount = refunded_before + amount
    order.escrow_amount = max(Decimal("0.00"), available_before - amount)
    order.payment_status = "refunded" if order.escrow_amount <= 0 else "partially_refunded"
    if payment:
        payment.status = "refunded" if order.escrow_amount <= 0 else "partially_refunded"
    _record_financial_event(db, order, "refund_succeeded", f"已退款 ¥{amount:.2f}（退款比例 {refund_rate * 100:.0f}%）")
    return refund


def refund_dispute_order(
    db: Session,
    order: Order,
    dispute_id: int,
    amount,
    approved_by: int,
    reason: str,
) -> Refund:
    """执行管理员争议仲裁退款；金额仅能来自尚未结算的人民币担保余额。"""
    ensure_order_not_settled(db, order)
    normalized_amount = _money(amount)
    available_before = available_escrow_amount(db, order)
    if normalized_amount <= 0:
        raise HTTPException(status_code=400, detail="争议退款金额必须大于 0 元")
    if normalized_amount > available_before:
        raise HTTPException(
            status_code=409,
            detail=f"退款金额超过当前可退担保余额 ¥{available_before:.2f}",
        )

    idempotency_key = f"dispute-resolution:{dispute_id}"
    existing = db.query(Refund).filter(Refund.idempotency_key == idempotency_key).first()
    if existing:
        if _money(existing.amount) != normalized_amount:
            raise HTTPException(status_code=409, detail="该争议已经按其他金额执行退款")
        return existing

    payment = db.query(Payment).filter(
        Payment.order_id == order.id,
        Payment.status.in_([
            PaymentStatus.SUCCEEDED.value,
            PaymentStatus.PARTIALLY_REFUNDED.value,
        ]),
    ).order_by(Payment.id.asc()).first()
    refund = Refund(
        refund_no=_new_no("REF"),
        order_id=order.id,
        payment_id=payment.id if payment else None,
        customer_id=order.customer_id,
        amount=normalized_amount,
        currency=CURRENCY_CNY,
        status="succeeded",
        reason_code="dispute_resolution",
        reason=reason,
        responsibility_party="platform_arbitration",
        breach_fee=Decimal("0.00"),
        platform_compensation=Decimal("0.00"),
        requested_by=None,
        approved_by=approved_by,
        provider_refund_id=_new_no("MOCKREF"),
        idempotency_key=idempotency_key,
        adjustment_note=f"争议 #{dispute_id} 管理员仲裁退款",
        completed_at=_now(),
    )
    db.add(refund)
    db.flush()

    refunded_after = _refunded_amount(db, order.id)
    remaining = max(Decimal("0.00"), available_before - normalized_amount)
    order.refunded_amount = refunded_after
    order.escrow_amount = remaining
    order.payment_status = "refunded" if remaining <= 0 else "partially_refunded"
    for item in db.query(Payment).filter(
        Payment.order_id == order.id,
        Payment.status.in_([
            PaymentStatus.SUCCEEDED.value,
            PaymentStatus.PARTIALLY_REFUNDED.value,
        ]),
    ).all():
        item.status = (
            PaymentStatus.REFUNDED.value
            if remaining <= 0
            else PaymentStatus.PARTIALLY_REFUNDED.value
        )
    _record_financial_event(
        db,
        order,
        "dispute_refund_succeeded",
        f"平台仲裁退款 ¥{normalized_amount:.2f}（争议 #{dispute_id}）",
    )
    return refund


def settle_order(db: Session, order: Order) -> Settlement:
    """结算订单担保资金，扣除平台服务费后生成结算单。"""
    if order.after_sales_status != "none":
        raise HTTPException(status_code=409, detail="售后处理中，暂不可结算")
    existing = db.query(Settlement).filter(Settlement.order_id == order.id).first()
    if existing:
        return existing
    gross = available_escrow_amount(db, order)
    if gross <= 0:
        raise HTTPException(status_code=409, detail="订单尚无可结算的担保资金")
    fee = (gross * Decimal(str(settings.PLATFORM_FEE_RATE))).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
    settlement = Settlement(
        settlement_no=_new_no("SET"),
        order_id=order.id,
        photographer_id=order.photographer_id,
        gross_amount=gross,
        platform_fee_amount=fee,
        net_amount=gross - fee,
        currency=CURRENCY_CNY,
        status=SettlementStatus.SETTLED.value,
        idempotency_key=f"settle-order:{order.id}",
        settled_at=_now(),
    )
    db.add(settlement)
    db.flush()
    order.settled_amount = gross - fee
    order.escrow_amount = Decimal("0.00")
    order.payment_status = "settled"
    _record_financial_event(db, order, "settlement_succeeded", f"已结算 ¥{gross - fee:.2f}（平台服务费 ¥{fee:.2f}）")
    return settlement


def get_order_financial_summary(db: Session, order: Order) -> dict:
    """汇总订单的支付、退款、结算等财务信息。"""
    expire_payment_orders(db)
    db.refresh(order)
    return {
        "order_id": order.id,
        "payment_status": order.payment_status,
        "payment_due_at": order.payment_due_at,
        "final_price": order.final_price,
        "escrow_amount": order.escrow_amount or Decimal("0.00"),
        "refunded_amount": order.refunded_amount or Decimal("0.00"),
        "settled_amount": order.settled_amount or Decimal("0.00"),
        "payments": db.query(Payment).filter(Payment.order_id == order.id).order_by(Payment.id.asc()).all(),
        "refunds": db.query(Refund).filter(Refund.order_id == order.id).order_by(Refund.id.asc()).all(),
        "settlement": db.query(Settlement).filter(Settlement.order_id == order.id).first(),
    }


def list_financial_records(db: Session, kind: str, skip: int = 0, limit: int = 50):
    """分页列出指定类型的财务记录（支付/退款/结算）。"""
    model = {"payments": Payment, "refunds": Refund, "settlements": Settlement}.get(kind)
    if model is None:
        raise HTTPException(status_code=400, detail="未知财务记录类型")
    return db.query(model).order_by(model.id.desc()).offset(skip).limit(limit).all()
