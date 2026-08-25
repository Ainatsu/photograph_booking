"""订单自动化：动作元数据刷新、超时关闭与提醒任务。"""

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.models.order import Order, OrderStatus
from backend.app.models.order_reschedule import OrderRescheduleStatus


ACTIVE_ORDER_STATUSES = {
    OrderStatus.PENDING,
    OrderStatus.AWAITING_PAYMENT,
    OrderStatus.CONFIRMED,
    OrderStatus.IN_PROGRESS,
    OrderStatus.DELIVERED,
}


def _now() -> datetime:
    """返回不带时区的当前 UTC 时间。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _naive(value: datetime | None) -> datetime | None:
    """将带时区时间转为 UTC 无时区时间。"""
    if value is None:
        return None
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _created_deadline(order: Order) -> datetime:
    """计算订单创建的确认截止时间。"""
    created_at = _naive(order.created_at) or _now()
    return created_at + timedelta(hours=max(1, settings.ORDER_CONFIRMATION_HOURS))


def _active_reschedule(order: Order):
    """返回订单当前待处理的改期请求。"""
    for request in order.reschedule_requests or []:
        status_value = getattr(request.status, "value", request.status)
        if status_value == OrderRescheduleStatus.PENDING.value:
            return request
    return None


def refresh_order_action_metadata(db: Session, order: Order) -> Order:
    """按订单状态刷新待办角色、截止时间与自动动作。"""
    role = None
    deadline = None
    action_code = None
    auto_action = None

    if order.after_sales_status == "dispute_open":
        role = "admin"
        action_code = "resolve_dispute"
    else:
        reschedule = _active_reschedule(order)
        if reschedule:
            role = "photographer" if reschedule.requested_by == order.customer_id else "customer"
            deadline = _naive(reschedule.expires_at)
            action_code = "respond_reschedule"
            auto_action = "expire_reschedule"
        elif order.status == OrderStatus.PENDING:
            role = "photographer"
            deadline = _created_deadline(order)
            action_code = "confirm_booking"
            auto_action = "cancel_unconfirmed"
        elif order.status == OrderStatus.AWAITING_PAYMENT:
            role = "customer"
            deadline = _naive(order.payment_due_at)
            action_code = "pay_order"
            auto_action = "expire_payment"
        elif order.status == OrderStatus.CONFIRMED:
            if order.payment_status == "deposit_paid":
                role = "customer"
                deadline = _naive(order.appointment_time) - timedelta(hours=24)
                action_code = "pay_balance"
            else:
                role = "photographer"
                deadline = _naive(order.appointment_time)
                action_code = "start_service"
        elif order.status == OrderStatus.IN_PROGRESS:
            role = "photographer"
            deadline = _naive(order.delivery_due_at)
            action_code = "submit_delivery"
            auto_action = "mark_delivery_overdue"
        elif order.status == OrderStatus.DELIVERED:
            if order.after_sales_status == "revision_requested":
                active_revision = next(
                    (
                        item for item in order.revision_requests or []
                        if getattr(item.status, "value", item.status) == "requested"
                    ),
                    None,
                )
                role = "photographer"
                deadline = _naive(
                    active_revision.expected_redelivery_at or active_revision.response_due_at
                ) if active_revision else None
                action_code = "respond_or_redeliver_revision"
            else:
                role = "customer"
                deadline = _naive(order.acceptance_deadline_at)
                action_code = "accept_or_after_sales"
                auto_action = "auto_accept_delivery"

    changed = (
        order.action_required_by != role
        or order.action_deadline_at != deadline
        or order.next_action_code != action_code
    )
    order.action_required_by = role
    order.action_deadline_at = deadline
    order.next_action_code = action_code
    order.auto_action_code = auto_action
    if changed:
        order.last_reminded_at = None
        order.reminder_count = 0
        order.overdue_at = None
    db.flush()
    return order


def expire_unconfirmed_orders(db: Session, commit: bool = True) -> list[int]:
    """自动关闭超过确认期限的待确认订单，返回 ID 列表。"""
    from backend.app.services.order_service import record_order_event

    now = _now()
    orders = db.query(Order).filter(Order.status == OrderStatus.PENDING).all()
    expired_ids = []
    for order in orders:
        deadline = _naive(order.action_deadline_at) or _created_deadline(order)
        if deadline > now:
            continue
        order.status = OrderStatus.CANCELLED
        order.cancelled_by = "system"
        order.cancellation_reason = "摄影师未在确认期限内响应，预约已自动关闭"
        order.overdue_at = now
        order.action_required_by = None
        order.action_deadline_at = None
        order.next_action_code = None
        order.auto_action_code = None
        record_order_event(
            db,
            order.id,
            None,
            "system",
            "order_confirmation_expired",
            OrderStatus.CANCELLED,
            "摄影师确认超时，订单已自动关闭；客户可重新选择档期。",
        )
        expired_ids.append(order.id)
    if commit and expired_ids:
        db.commit()
    return expired_ids


def _reminder_window(action_code: str | None) -> timedelta | None:
    """返回各动作码对应的提醒时间窗。"""
    return {
        "confirm_booking": timedelta(hours=12),
        "pay_order": timedelta(minutes=10),
        "pay_balance": timedelta(hours=24),
        "submit_delivery": timedelta(hours=24),
        "accept_or_after_sales": timedelta(hours=48),
        "respond_or_redeliver_revision": timedelta(hours=24),
        "respond_reschedule": timedelta(hours=12),
    }.get(action_code)


def _reminder_note(order: Order) -> str:
    """生成订单提醒文案（含截止时间）。"""
    deadline = _naive(order.action_deadline_at)
    deadline_text = deadline.strftime("%Y-%m-%d %H:%M") if deadline else "尽快"
    labels = {
        "confirm_booking": "请确认或拒绝预约",
        "pay_order": "请完成订单支付，否则档期将释放",
        "pay_balance": "请完成尾款支付",
        "submit_delivery": "请按约定提交交付",
        "accept_or_after_sales": "请验收、申请修改或发起争议",
        "respond_or_redeliver_revision": "请响应返修并按排期重新交付",
        "respond_reschedule": "请处理改期申请",
    }
    return f"{labels.get(order.next_action_code, '订单需要处理')}，处理截止时间：{deadline_text}。"


def process_order_reminders(db: Session, commit: bool = True) -> list[int]:
    """对临期订单发送提醒并记录事件，返回已提醒订单 ID。"""
    from backend.app.services.order_service import record_order_event

    now = _now()
    reminded_ids = []
    orders = db.query(Order).filter(Order.status.in_(ACTIVE_ORDER_STATUSES)).all()
    for order in orders:
        refresh_order_action_metadata(db, order)
        deadline = _naive(order.action_deadline_at)
        if not deadline:
            continue
        remaining = deadline - now
        if remaining.total_seconds() <= 0:
            if order.overdue_at is None:
                order.overdue_at = now
                if order.next_action_code == "submit_delivery":
                    record_order_event(
                        db,
                        order.id,
                        None,
                        "system",
                        "delivery_overdue",
                        order.status,
                        "已超过合同交付时间，客户可联系摄影师或发起争议。",
                    )
            continue
        window = _reminder_window(order.next_action_code)
        if not window or remaining > window:
            continue
        last_reminded = _naive(order.last_reminded_at)
        if last_reminded and now - last_reminded < timedelta(hours=12):
            continue
        record_order_event(
            db,
            order.id,
            None,
            "system",
            "order_reminder_sent",
            order.status,
            _reminder_note(order),
        )
        order.last_reminded_at = now
        order.reminder_count = int(order.reminder_count or 0) + 1
        reminded_ids.append(order.id)
    if commit and (reminded_ids or orders):
        db.commit()
    return reminded_ids


def run_order_automation_once(db: Session) -> dict:
    """执行一轮订单自动化（超时关闭 + 提醒）。"""
    expired_confirmation_ids = expire_unconfirmed_orders(db, commit=False)
    reminded_ids = process_order_reminders(db, commit=False)
    db.commit()
    return {
        "expired_confirmation_ids": expired_confirmation_ids,
        "reminded_order_ids": reminded_ids,
    }


async def run_order_automation_worker(poll_interval_seconds: int | None = None) -> None:
    """后台轮询循环执行订单自动化任务。"""
    import asyncio
    from backend.app.core.database import SessionLocal
    from backend.app.services.order_service import get_latest_order_event, push_order_event_update

    interval = max(10, poll_interval_seconds or settings.ORDER_AUTOMATION_POLL_SECONDS)
    while True:
        db = SessionLocal()
        try:
            result = run_order_automation_once(db)
            order_ids = sorted(set(result["expired_confirmation_ids"] + result["reminded_order_ids"]))
            for order_id in order_ids:
                await push_order_event_update(get_latest_order_event(db, order_id))
        except asyncio.CancelledError:
            db.rollback()
            raise
        except Exception:
            db.rollback()
        finally:
            db.close()
        await asyncio.sleep(interval)
