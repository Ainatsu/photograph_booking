"""订单相关的业务逻辑服务。"""

import enum
from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.orm import joinedload

from backend.app.models.order_event import OrderEvent
from backend.app.models.order import Order, OrderStatus
from backend.app.models.order_reschedule import OrderRescheduleRequest, OrderRescheduleStatus
from backend.app.models.photographer import PhotographerProfile
from backend.app.models.user import User
from backend.app.schemas.order import OrderCreateRequest
from backend.app.services.availability_service import is_interval_bookable_by_profile
from backend.app.services.order_contract_service import (
    CURRENCY_CNY,
    build_legacy_contract_snapshot,
    build_package_contract_snapshot,
    contract_to_order_fields,
)
from backend.app.services.photographer_service import get_package_by_id
from backend.app.services.ws_manager import manager


class OrderAction(str, enum.Enum):
    """订单状态流转动作的枚举定义。"""
    ACCEPT_BOOKING = "accept_booking"
    REJECT_BOOKING = "reject_booking"
    START_SERVICE = "start_service"
    SUBMIT_DELIVERY = "submit_delivery"
    REQUEST_REVISION = "request_revision"
    ACKNOWLEDGE_REVISION = "acknowledge_revision"
    ACCEPT_DELIVERY = "accept_delivery"
    AUTO_ACCEPT_DELIVERY = "auto_accept_delivery"
    SUBMIT_REVIEW = "submit_review"
    CANCEL_ORDER = "cancel_order"
    ADMIN_CANCEL_ORDER = "admin_cancel_order"


def _status_value(status_value: OrderStatus | str) -> str:
    """返回枚举值或字符串形式的状态值。"""
    return status_value.value if isinstance(status_value, OrderStatus) else str(status_value)


INTERNAL_APPOINTMENT_HOUR = 12


def _normalize_appointment(appointment: datetime) -> datetime:
    """将预约时间统一转为无时区 UTC 时间。"""
    if appointment.tzinfo is not None:
        return appointment.astimezone(timezone.utc).replace(tzinfo=None)
    return appointment


def _appointment_for_date(appointment_date: date) -> datetime:
    """将日期转换为内部兼容时间戳，不代表用户选择了具体小时。"""
    if isinstance(appointment_date, datetime):
        return _normalize_appointment(appointment_date)
    return datetime.combine(appointment_date, datetime.min.time()).replace(hour=INTERNAL_APPOINTMENT_HOUR)


def _format_appointment(appointment: datetime) -> str:
    """将预约时间格式化为可读字符串。"""
    return appointment.strftime("%Y-%m-%d %H:%M")


def _validate_note(note: str | None, message: str) -> str:
    """校验备注文本非空，为空时抛出 400。"""
    normalized = (note or "").strip()
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message,
        )
    return normalized


def _order_actor_role(order: Order, actor_id: int) -> str:
    """判断操作人在订单中的身份，否则抛出 403。"""
    if order.customer_id == actor_id:
        return "customer"
    if order.photographer_id == actor_id:
        return "photographer"
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="只能操作与您相关的订单",
    )


def _ensure_order_actor(order: Order, actor_id: int, expected_role: str | None = None) -> str:
    """校验操作人身份并返回其订单角色。"""
    actor_role = _order_actor_role(order, actor_id)
    if expected_role and actor_role != expected_role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="当前订单身份无权执行该操作",
        )
    return actor_role


def _utc_now_naive() -> datetime:
    """返回不带时区信息的当前 UTC 时间。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _ensure_photographer_available(
    db: Session,
    photographer_id: int,
    appointment: datetime,
    duration_minutes: int,
    exclude_order_id: int | None = None,
) -> None:
    """校验摄影师档期及既有订单/改期申请是否冲突。"""
    target_start = _normalize_appointment(appointment)
    target_date = target_start.date()

    profile = db.query(PhotographerProfile).filter(
        PhotographerProfile.user_id == photographer_id
    ).first()
    if profile and not is_interval_bookable_by_profile(profile, target_start, duration_minutes):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="该时段不在摄影师设置的可预约档期内",
        )

    query = db.query(Order).filter(
        Order.photographer_id == photographer_id,
        Order.status.in_([
            OrderStatus.AWAITING_PAYMENT,
            OrderStatus.CONFIRMED,
            OrderStatus.IN_PROGRESS,
        ])
    )
    if exclude_order_id is not None:
        query = query.filter(Order.id != exclude_order_id)

    active_orders = query.all()
    profile = profile or None
    max_daily = max(1, int(getattr(profile, "max_daily_bookings", 5) or 5)) if profile else 5
    same_day_orders = [
        order for order in active_orders
        if _normalize_appointment(order.appointment_time).date() == target_date
    ]
    if len(same_day_orders) >= max_daily:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="该日期预约数量已满，请选择其他日期",
        )

    pending_request_query = (
        db.query(OrderRescheduleRequest)
        .join(Order, Order.id == OrderRescheduleRequest.order_id)
        .filter(
            Order.photographer_id == photographer_id,
            OrderRescheduleRequest.status == OrderRescheduleStatus.PENDING,
            OrderRescheduleRequest.expires_at > _utc_now_naive(),
        )
    )
    if exclude_order_id is not None:
        pending_request_query = pending_request_query.filter(
            OrderRescheduleRequest.order_id != exclude_order_id
        )

    for request in pending_request_query.all():
        request_start = _normalize_appointment(request.requested_appointment_time)
        if request_start.date() == target_date:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="该日期已有待处理的改期申请，请选择其他日期",
            )


def record_order_event(
    db: Session,
    order_id: int,
    actor_id: int | None,
    actor_role: str | None,
    event_type: str,
    status_value: OrderStatus | str,
    note: str | None = None,
) -> OrderEvent:
    """记录一条订单事件并触发相关通知。"""
    event = OrderEvent(
        order_id=order_id,
        actor_id=actor_id,
        actor_role=actor_role,
        event_type=event_type,
        status=_status_value(status_value),
        note=note,
    )
    db.add(event)
    db.flush()
    db.refresh(event)
    from backend.app.services.notification_service import enqueue_order_event
    order = db.query(Order).filter(Order.id == order_id).first()
    if order:
        enqueue_order_event(db, event, order)
    return event


def _serialize_event(event: OrderEvent) -> dict:
    """序列化订单事件为接口响应字典。"""
    actor = event.actor
    return {
        "id": event.id,
        "event_type": event.event_type,
        "status": _status_value(event.status),
        "actor_id": event.actor_id,
        "actor_role": event.actor_role,
        "actor_name": actor.display_name if actor else None,
        "note": event.note,
        "created_at": event.created_at,
    }


def _serialize_reschedule_request(request: OrderRescheduleRequest | None) -> dict | None:
    """序列化改期申请为接口响应字典，为空返回 None。"""
    if request is None:
        return None
    return {
        "id": request.id,
        "order_id": request.order_id,
        "requested_by": request.requested_by,
        "original_appointment_time": request.original_appointment_time,
        "requested_appointment_time": request.requested_appointment_time,
        "reason": request.reason,
        "status": _status_value(request.status),
        "response_note": request.response_note,
        "expires_at": request.expires_at,
        "created_at": request.created_at,
        "resolved_at": request.resolved_at,
    }


def expire_reschedule_requests(
    db: Session,
    order_id: int | None = None,
) -> list[OrderRescheduleRequest]:
    """将超时未处理的改期申请标记为已失效。"""
    query = db.query(OrderRescheduleRequest).filter(
        OrderRescheduleRequest.status == OrderRescheduleStatus.PENDING,
        OrderRescheduleRequest.expires_at <= _utc_now_naive(),
    )
    if order_id is not None:
        query = query.filter(OrderRescheduleRequest.order_id == order_id)

    expired_requests = query.all()
    now = _utc_now_naive()
    for request in expired_requests:
        request.status = OrderRescheduleStatus.EXPIRED
        request.resolved_at = now
        order = request.order
        if order and order.reschedule_requested_time == request.requested_appointment_time:
            order.reschedule_requested_time = None
            order.reschedule_reason = None
        if order:
            from backend.app.services.automation_service import refresh_order_action_metadata
            refresh_order_action_metadata(db, order)
        record_order_event(
            db,
            request.order_id,
            None,
            "system",
            "reschedule_expired",
            order.status if order else OrderStatus.CONFIRMED,
            f"改期申请已超时失效：{_format_appointment(request.requested_appointment_time)}",
        )
    if expired_requests:
        db.flush()
    return expired_requests


def get_active_reschedule_request(
    db: Session,
    order_id: int,
) -> OrderRescheduleRequest | None:
    """获取订单当前仍处于待处理状态的改期申请。"""
    expire_reschedule_requests(db, order_id)
    return (
        db.query(OrderRescheduleRequest)
        .filter(
            OrderRescheduleRequest.order_id == order_id,
            OrderRescheduleRequest.status == OrderRescheduleStatus.PENDING,
        )
        .order_by(OrderRescheduleRequest.created_at.desc(), OrderRescheduleRequest.id.desc())
        .first()
    )


def serialize_order_history_card(order: Order, history_item: dict) -> dict:
    """将历史条目与订单信息合并为时间线卡片数据。"""
    event_id = history_item.get("id")
    created_at = history_item.get("created_at")
    fallback_id_time = created_at.isoformat() if hasattr(created_at, "isoformat") else "unknown"
    return {
        "item_type": "order_event",
        "id": f"order-event-{event_id}" if event_id is not None else f"order-{order.id}-{history_item.get('event_type')}-{fallback_id_time}",
        "message_id": None,
        "order_event_id": event_id,
        "sender_id": None,
        "receiver_id": None,
        "content": None,
        "order_id": order.id,
        "is_read": None,
        "event_type": history_item.get("event_type"),
        "status": _status_value(history_item.get("status")),
        "actor_id": history_item.get("actor_id"),
        "actor_role": history_item.get("actor_role"),
        "actor_name": history_item.get("actor_name"),
        "note": history_item.get("note"),
        "customer_id": order.customer_id,
        "photographer_id": order.photographer_id,
        "package_snapshot": order.package_snapshot,
        "source_type": order.source_type,
        "source_id": order.source_id,
        "source_application_id": order.source_application_id,
        "package_id": order.package_id,
        "package_name": order.package_name,
        "package_description": order.package_description,
        "package_price": order.package_price,
        "final_price": order.final_price,
        "currency": order.currency or CURRENCY_CNY,
        "service_location": order.service_location,
        "delivery_due_at": order.delivery_due_at,
        "original_image_count": order.original_image_count,
        "retouched_image_count": order.retouched_image_count,
        "delivery_formats": order.delivery_formats,
        "included_revision_count": order.included_revision_count,
        "commercial_license": order.commercial_license,
        "copyright_terms": order.copyright_terms,
        "cancellation_policy_snapshot": order.cancellation_policy_snapshot,
        "reschedule_policy_snapshot": order.reschedule_policy_snapshot,
        "deliverables": order.deliverables,
        "payment_mode": order.payment_mode,
        "fulfillment_mode": order.fulfillment_mode,
        "contract_snapshot": order.contract_snapshot,
        "payment_status": order.payment_status,
        "after_sales_status": order.after_sales_status,
        "payment_due_at": order.payment_due_at,
        "deposit_rate": order.deposit_rate,
        "escrow_amount": order.escrow_amount,
        "refunded_amount": order.refunded_amount,
        "settled_amount": order.settled_amount,
        "acceptance_deadline_at": order.acceptance_deadline_at,
        "completed_at": order.completed_at,
        "completion_type": order.completion_type,
        "revision_used_count": order.revision_used_count,
        "action_required_by": order.action_required_by,
        "action_deadline_at": order.action_deadline_at,
        "next_action_code": order.next_action_code,
        "auto_action_code": order.auto_action_code,
        "last_reminded_at": order.last_reminded_at,
        "reminder_count": order.reminder_count,
        "overdue_at": order.overdue_at,
        "created_at": created_at,
    }


def serialize_order_event_card(event: OrderEvent, order: Order | None = None) -> dict:
    """将订单事件序列化为时间线卡片数据。"""
    order = order or event.order
    return serialize_order_history_card(order, _serialize_event(event))


def get_latest_order_event(db: Session, order_id: int) -> OrderEvent | None:
    """查询订单最近一条事件记录。"""
    return (
        db.query(OrderEvent)
        .options(joinedload(OrderEvent.actor), joinedload(OrderEvent.order))
        .filter(OrderEvent.order_id == order_id)
        .order_by(OrderEvent.created_at.desc(), OrderEvent.id.desc())
        .first()
    )


async def push_order_event_update(event: OrderEvent | None, order: Order | None = None) -> None:
    """将订单事件实时推送给订单双方。"""
    if not event:
        return
    order = order or event.order
    if not order:
        return

    payload = {
        "type": "order_event",
        "event": serialize_order_event_card(event, order),
    }
    await manager.send_personal_message(payload, order.customer_id)
    if order.photographer_id != order.customer_id:
        await manager.send_personal_message(payload, order.photographer_id)


async def run_reschedule_expiry_worker(poll_interval_seconds: int = 60) -> None:
    """后台失效过期改期申请，并将系统事件实时推送给订单双方。"""
    import asyncio

    from backend.app.core.database import SessionLocal

    while True:
        db = SessionLocal()
        try:
            expired = expire_reschedule_requests(db)
            order_ids = sorted({request.order_id for request in expired})
            if order_ids:
                db.commit()
                for order_id in order_ids:
                    event = get_latest_order_event(db, order_id)
                    await push_order_event_update(event)
        except asyncio.CancelledError:
            db.rollback()
            raise
        except Exception:
            db.rollback()
        finally:
            db.close()
        await asyncio.sleep(poll_interval_seconds)


async def run_payment_expiry_worker(poll_interval_seconds: int = 30) -> None:
    """后台关闭超时支付单并释放待支付订单的档期。"""
    import asyncio

    from backend.app.core.database import SessionLocal
    from backend.app.services.payment_service import expire_payment_orders

    while True:
        db = SessionLocal()
        try:
            order_ids = expire_payment_orders(db)
            for order_id in order_ids:
                event = get_latest_order_event(db, order_id)
                await push_order_event_update(event)
        except asyncio.CancelledError:
            db.rollback()
            raise
        except Exception:
            db.rollback()
        finally:
            db.close()
        await asyncio.sleep(poll_interval_seconds)


async def run_acceptance_expiry_worker(poll_interval_seconds: int = 60) -> None:
    """自动验收已到期且没有返修或售后请求的交付订单。"""
    import asyncio

    from backend.app.core.database import SessionLocal
    from backend.app.services.delivery_service import expire_acceptance_orders

    while True:
        db = SessionLocal()
        try:
            order_ids = expire_acceptance_orders(db)
            for order_id in order_ids:
                event = get_latest_order_event(db, order_id)
                await push_order_event_update(event)
        except asyncio.CancelledError:
            db.rollback()
            raise
        except Exception:
            db.rollback()
        finally:
            db.close()
        await asyncio.sleep(poll_interval_seconds)


def _synthetic_history(order: Order) -> list[dict]:
    """为缺少事件记录的订单构造合成历史条目。"""
    history = [{
        "id": None,
        "event_type": "created",
        "status": OrderStatus.PENDING.value,
        "actor_id": order.customer_id,
        "actor_role": "customer",
        "actor_name": order.customer.display_name if order.customer else None,
        "note": "客户提交预约",
        "created_at": order.created_at,
    }]
    if order.status != OrderStatus.PENDING:
        history.append({
            "id": None,
            "event_type": "status_snapshot",
            "status": _status_value(order.status),
            "actor_id": None,
            "actor_role": "system",
            "actor_name": "系统记录",
            "note": "历史订单当前状态",
            "created_at": order.updated_at or order.created_at,
        })
    return history


def get_order_history(db: Session, order: Order) -> list[dict]:
    """获取订单的事件历史列表，无记录时返回合成历史。"""
    events = (
        db.query(OrderEvent)
        .options(joinedload(OrderEvent.actor))
        .filter(OrderEvent.order_id == order.id)
        .order_by(OrderEvent.created_at.asc(), OrderEvent.id.asc())
        .all()
    )
    if not events:
        return _synthetic_history(order)
    history = [_serialize_event(event) for event in events]
    if not any(item["event_type"] == "created" for item in history):
        history.insert(0, _synthetic_history(order)[0])
    return history


def _serialize_order_detail(order: Order) -> dict:
    """序列化订单详情为接口响应字典。"""
    customer = order.customer
    photographer = order.photographer
    active_reschedule = order.active_reschedule_request
    return {
        "id": order.id,
        "customer_id": order.customer_id,
        "photographer_id": order.photographer_id,
        "package_snapshot": order.package_snapshot,
        "source_type": order.source_type,
        "source_id": order.source_id,
        "source_application_id": order.source_application_id,
        "package_id": order.package_id,
        "package_name": order.package_name,
        "package_description": order.package_description,
        "package_price": order.package_price,
        "final_price": order.final_price,
        "currency": order.currency or CURRENCY_CNY,
        "service_location": order.service_location,
        "delivery_due_at": order.delivery_due_at,
        "original_image_count": order.original_image_count,
        "retouched_image_count": order.retouched_image_count,
        "delivery_formats": order.delivery_formats,
        "included_revision_count": order.included_revision_count,
        "commercial_license": order.commercial_license,
        "copyright_terms": order.copyright_terms,
        "cancellation_policy_snapshot": order.cancellation_policy_snapshot,
        "reschedule_policy_snapshot": order.reschedule_policy_snapshot,
        "deliverables": order.deliverables,
        "payment_mode": order.payment_mode,
        "fulfillment_mode": order.fulfillment_mode,
        "contract_snapshot": order.contract_snapshot,
        "payment_status": order.payment_status,
        "after_sales_status": order.after_sales_status,
        "payment_due_at": order.payment_due_at,
        "deposit_rate": order.deposit_rate,
        "escrow_amount": order.escrow_amount,
        "refunded_amount": order.refunded_amount,
        "settled_amount": order.settled_amount,
        "acceptance_deadline_at": order.acceptance_deadline_at,
        "completed_at": order.completed_at,
        "completion_type": order.completion_type,
        "revision_used_count": order.revision_used_count,
        "action_required_by": order.action_required_by,
        "action_deadline_at": order.action_deadline_at,
        "next_action_code": order.next_action_code,
        "auto_action_code": order.auto_action_code,
        "last_reminded_at": order.last_reminded_at,
        "reminder_count": order.reminder_count,
        "overdue_at": order.overdue_at,
        "appointment_time": order.appointment_time,
        "duration_minutes": order.duration_minutes,
        "notes": order.notes,
        "rejection_reason": order.rejection_reason,
        "reschedule_requested_time": order.reschedule_requested_time,
        "reschedule_reason": order.reschedule_reason,
        "active_reschedule_request": _serialize_reschedule_request(active_reschedule),
        "cancellation_reason": order.cancellation_reason,
        "cancelled_by": order.cancelled_by,
        "status": _status_value(order.status),
        "delivery": order.delivery,
        "rating": order.rating,
        "review_text": order.review_text,
        "customer_name": customer.display_name if customer else None,
        "customer_avatar_url": customer.avatar_url if customer else None,
        "photographer_name": photographer.display_name if photographer else None,
        "photographer_avatar_url": photographer.avatar_url if photographer else None,
        "created_at": order.created_at,
        "updated_at": order.updated_at,
    }


def get_order_detail(db: Session, order: Order) -> dict:
    """获取订单完整详情及关联历史、交付、争议数据。"""
    from backend.app.models.order_dispute import OrderDispute
    from backend.app.services.dispute_service import serialize_dispute
    from backend.app.services.delivery_service import (
        expire_acceptance_orders,
        list_order_deliveries,
        list_order_revision_requests,
        serialize_delivery,
        serialize_revision_request,
    )

    expire_acceptance_orders(db, order.id)
    db.refresh(order)
    expired = expire_reschedule_requests(db, order.id)
    if expired:
        db.commit()
        db.refresh(order)
    return {
        "order": _serialize_order_detail(order),
        "history": get_order_history(db, order),
        "reschedule_requests": [
            _serialize_reschedule_request(request)
            for request in order.reschedule_requests
        ],
        "deliveries": [serialize_delivery(item) for item in list_order_deliveries(db, order.id)],
        "revision_requests": [
            serialize_revision_request(item)
            for item in list_order_revision_requests(db, order.id)
        ],
        "disputes": [
            serialize_dispute(item)
            for item in db.query(OrderDispute)
            .options(
                joinedload(OrderDispute.opener),
                joinedload(OrderDispute.assigned_admin),
                joinedload(OrderDispute.evidence),
                joinedload(OrderDispute.order),
            )
            .filter(OrderDispute.order_id == order.id)
            .order_by(OrderDispute.created_at.desc(), OrderDispute.id.desc())
            .all()
        ],
    }


def create_order(db: Session, customer_id: int, data: OrderCreateRequest) -> Order:
    """客户创建订单"""

    package = get_package_by_id(db, data.package_id) if data.package_id else None
    if data.package_id and not package:
        raise HTTPException(status_code=404, detail="套餐不存在或已停止预约")
    photographer_id = package.get("photographer_id") if package else data.photographer_id
    if not photographer_id:
        raise HTTPException(status_code=400, detail="缺少摄影师或套餐信息")
    if customer_id == photographer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能向自己创建订单",
        )

    # 1. 检查摄影师是否存在
    photographer = db.query(User).filter(
        User.id == photographer_id,
        User.role == "photographer"
    ).first()
    if not photographer:
        raise HTTPException(status_code=404, detail="摄影师不存在")

    if package and data.photographer_id and package["photographer_id"] != data.photographer_id:
        raise HTTPException(status_code=400, detail="套餐不属于目标摄影师")

    # 2. 后端生成可信合同快照
    appointment_value = data.appointment_date or data.appointment_time
    if not appointment_value:
        raise HTTPException(status_code=400, detail="缺少预约日期")
    appointment_date = appointment_value.date() if isinstance(appointment_value, datetime) else appointment_value
    target_start = _appointment_for_date(appointment_value)
    if package:
        try:
            contract_snapshot = build_package_contract_snapshot(
                package=package,
                appointment_time=target_start,
                customer_notes=data.notes,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        duration_minutes = int(contract_snapshot["schedule"]["duration_minutes"])
        package_snapshot = (
            f"{contract_snapshot['title']} - ¥{contract_snapshot['pricing']['final_price']}"
            f"/{duration_minutes}分钟"
        )
    else:
        if not data.package_description or not data.duration_minutes:
            raise HTTPException(status_code=400, detail="旧订单创建缺少方案描述或服务时长")
        duration_minutes = data.duration_minutes
        package_snapshot = data.package_description
        contract_snapshot = build_legacy_contract_snapshot(
            package_snapshot=package_snapshot,
            appointment_time=target_start,
            duration_minutes=duration_minutes,
            customer_notes=data.notes,
        )

    from backend.app.core.cache import distributed_lock
    with distributed_lock(f"booking-create:{photographer_id}") as lock_acquired:
        if not lock_acquired:
            raise HTTPException(status_code=409, detail="该摄影师正在处理另一笔预约，请稍后重试")
        _ensure_photographer_available(
            db,
            photographer_id,
            target_start,
            duration_minutes,
        )

        # 5. 创建订单（存储 naive UTC）
        order = Order(
            customer_id=customer_id,
            photographer_id=photographer_id,
            package_snapshot=package_snapshot,
            appointment_time=target_start,  # 无时区 UTC
            duration_minutes=duration_minutes,
            notes=data.notes,
            status=OrderStatus.PENDING,
            **contract_to_order_fields(contract_snapshot),
        )
        db.add(order)
        db.flush()
        from backend.app.services.automation_service import refresh_order_action_metadata
        refresh_order_action_metadata(db, order)
        record_order_event(
            db,
            order.id,
            customer_id,
            "customer",
            "created",
            OrderStatus.PENDING,
            "客户提交预约",
        )
        db.commit()
        from backend.app.services.package_recommendation_service import invalidate_package_recommendation_cache
        invalidate_package_recommendation_cache(photographer_id)
        db.refresh(order)
        return order


def request_order_reschedule(
    db: Session,
    order: Order,
    actor_id: int,
    appointment_date: date | datetime | None,
    reason: str,
    expires_in_hours: int = 24,
) -> Order:
    """订单双方提交独立改期申请，订单主状态和原档期保持不变。"""
    actor_role = _ensure_order_actor(order, actor_id)
    expire_reschedule_requests(db, order.id)
    if order.status not in [OrderStatus.PENDING, OrderStatus.AWAITING_PAYMENT, OrderStatus.CONFIRMED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="当前订单状态不可申请改期",
        )
    if get_active_reschedule_request(db, order.id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="当前已有待处理的改期申请",
        )

    normalized_reason = _validate_note(reason, "申请改期必须填写原因")
    if not appointment_date:
        raise HTTPException(status_code=400, detail="缺少新的预约日期")
    requested_time = _appointment_for_date(appointment_date)
    if requested_time == _normalize_appointment(order.appointment_time):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="新预约时间不能与当前预约时间相同",
        )
    _ensure_photographer_available(
        db,
        order.photographer_id,
        requested_time,
        order.duration_minutes,
        exclude_order_id=order.id,
    )

    request = OrderRescheduleRequest(
        order_id=order.id,
        requested_by=actor_id,
        original_appointment_time=_normalize_appointment(order.appointment_time),
        requested_appointment_time=requested_time,
        reason=normalized_reason,
        status=OrderRescheduleStatus.PENDING,
        expires_at=_utc_now_naive() + timedelta(hours=expires_in_hours),
    )
    db.add(request)
    db.flush()
    order.reschedule_requested_time = requested_time
    order.reschedule_reason = normalized_reason
    from backend.app.services.automation_service import refresh_order_action_metadata
    refresh_order_action_metadata(db, order)
    record_order_event(
        db,
        order.id,
        actor_id,
        actor_role,
        "reschedule_requested",
        order.status,
        f"{('客户' if actor_role == 'customer' else '摄影师')}申请改期至 {_format_appointment(requested_time)}。原因：{normalized_reason}",
    )
    db.commit()
    db.refresh(order)
    return order


def _get_reschedule_request_for_order(
    db: Session,
    order: Order,
    request_id: int | None = None,
) -> OrderRescheduleRequest:
    """查询订单的改期申请，不存在时抛出 404。"""
    expire_reschedule_requests(db, order.id)
    query = db.query(OrderRescheduleRequest).filter(
        OrderRescheduleRequest.order_id == order.id,
    )
    if request_id is not None:
        query = query.filter(OrderRescheduleRequest.id == request_id)
    else:
        query = query.filter(OrderRescheduleRequest.status == OrderRescheduleStatus.PENDING)
    request = query.order_by(OrderRescheduleRequest.id.desc()).first()
    if not request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="改期申请不存在",
        )
    return request


def respond_order_reschedule(
    db: Session,
    order: Order,
    actor_id: int,
    decision: str,
    request_id: int | None = None,
    response_note: str | None = None,
) -> Order:
    """接受或拒绝对方的改期申请。"""
    actor_role = _ensure_order_actor(order, actor_id)
    request = _get_reschedule_request_for_order(db, order, request_id)
    if request.status != OrderRescheduleStatus.PENDING:
        if decision == "accept" and request.status == OrderRescheduleStatus.ACCEPTED:
            return order
        raise HTTPException(status_code=409, detail="改期申请已处理")
    if request.requested_by == actor_id:
        raise HTTPException(status_code=403, detail="改期申请需由对方处理")

    normalized_note = (response_note or "").strip() or None
    now = _utc_now_naive()
    if decision == "accept":
        requested_time = _normalize_appointment(request.requested_appointment_time)
        _ensure_photographer_available(
            db,
            order.photographer_id,
            requested_time,
            order.duration_minutes,
            exclude_order_id=order.id,
        )
        order.appointment_time = requested_time
        request.status = OrderRescheduleStatus.ACCEPTED
        request.response_note = normalized_note
        request.resolved_at = now
        event_type = "reschedule_accepted"
        event_note = f"改期已接受，预约时间更新为 {_format_appointment(requested_time)}"
    elif decision == "reject":
        request.status = OrderRescheduleStatus.REJECTED
        request.response_note = normalized_note
        request.resolved_at = now
        event_type = "reschedule_rejected"
        event_note = normalized_note or "改期申请已拒绝，原预约时间保持不变"
    else:
        raise HTTPException(status_code=400, detail="未知的改期响应动作")

    order.reschedule_requested_time = None
    order.reschedule_reason = None
    from backend.app.services.automation_service import refresh_order_action_metadata
    refresh_order_action_metadata(db, order)
    record_order_event(
        db,
        order.id,
        actor_id,
        actor_role,
        event_type,
        order.status,
        event_note,
    )
    db.commit()
    db.refresh(order)
    return order


def confirm_order_reschedule(db: Session, order: Order, actor_id: int) -> Order:
    """兼容旧接口：由改期申请的对方接受当前申请。"""
    return respond_order_reschedule(db, order, actor_id, "accept")


def withdraw_order_reschedule(
    db: Session,
    order: Order,
    actor_id: int,
    request_id: int | None = None,
) -> Order:
    """撤回自己提交的改期申请。"""
    actor_role = _ensure_order_actor(order, actor_id)
    request = _get_reschedule_request_for_order(db, order, request_id)
    if request.status != OrderRescheduleStatus.PENDING:
        if request.status == OrderRescheduleStatus.WITHDRAWN:
            return order
        raise HTTPException(status_code=409, detail="改期申请已处理")
    if request.requested_by != actor_id:
        raise HTTPException(status_code=403, detail="只能撤回自己提交的改期申请")

    request.status = OrderRescheduleStatus.WITHDRAWN
    request.resolved_at = _utc_now_naive()
    order.reschedule_requested_time = None
    order.reschedule_reason = None
    from backend.app.services.automation_service import refresh_order_action_metadata
    refresh_order_action_metadata(db, order)
    record_order_event(
        db,
        order.id,
        actor_id,
        actor_role,
        "reschedule_withdrawn",
        order.status,
        "改期申请已撤回，原预约时间保持不变",
    )
    db.commit()
    db.refresh(order)
    return order


def counter_order_reschedule(
    db: Session,
    order: Order,
    actor_id: int,
    appointment_date: date | datetime | None,
    reason: str,
    request_id: int | None = None,
) -> Order:
    """结束原改期申请并提交一个反向的新候选时间。"""
    actor_role = _ensure_order_actor(order, actor_id)
    request = _get_reschedule_request_for_order(db, order, request_id)
    if request.status != OrderRescheduleStatus.PENDING:
        raise HTTPException(status_code=409, detail="改期申请已处理")
    if request.requested_by == actor_id:
        raise HTTPException(status_code=403, detail="不能对自己的改期申请反提时间")

    request.status = OrderRescheduleStatus.REJECTED
    request.response_note = "对方提出了新的候选时间"
    request.resolved_at = _utc_now_naive()
    order.reschedule_requested_time = None
    order.reschedule_reason = None
    record_order_event(
        db,
        order.id,
        actor_id,
        actor_role,
        "reschedule_countered",
        order.status,
        "原改期申请已结束，对方提出新的候选时间",
    )
    db.flush()
    return request_order_reschedule(db, order, actor_id, appointment_date, reason)


def cancel_order(db: Session, order: Order, actor_id: int, actor_role: str | None, reason: str) -> Order:
    """客户或摄影师取消订单；身份以订单关系为准。"""
    actual_role = _ensure_order_actor(order, actor_id)
    return transition_order(
        db,
        order=order,
        action=OrderAction.CANCEL_ORDER,
        actor_id=actor_id,
        actor_role=actual_role,
        payload={"reason": reason},
    )


def admin_cancel_order_transition(
    db: Session,
    order: Order,
    admin_id: int,
    reason: str,
) -> Order:
    """管理员取消订单的状态转换入口。"""
    return transition_order(
        db,
        order=order,
        action=OrderAction.ADMIN_CANCEL_ORDER,
        actor_id=admin_id,
        actor_role="admin",
        payload={"reason": reason},
    )


def _validate_cancellation_status(order: Order) -> None:
    """校验订单当前状态是否允许取消。"""
    if order.status not in [OrderStatus.PENDING, OrderStatus.AWAITING_PAYMENT, OrderStatus.CONFIRMED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="当前订单状态不可取消",
        )


def get_order_by_id(db: Session, order_id: int) -> Order | None:
    """根据ID获取订单"""
    return (
        db.query(Order)
        .options(joinedload(Order.reschedule_requests))
        .filter(Order.id == order_id)
        .first()
    )


def transition_order(
    db: Session,
    *,
    order: Order,
    action: OrderAction | str,
    actor_id: int | None,
    actor_role: str | None = None,
    payload: dict | None = None,
) -> Order:
    """订单状态的唯一写入口：权限、前置条件、状态、事件在同一事务完成。"""
    try:
        action = OrderAction(action)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="未知的订单动作") from exc

    payload = payload or {}
    if action == OrderAction.ADMIN_CANCEL_ORDER:
        actual_role = "admin"
        if actor_role != "admin":
            raise HTTPException(status_code=403, detail="仅管理员可执行该操作")
    elif action == OrderAction.AUTO_ACCEPT_DELIVERY:
        actual_role = "system"
        if actor_role != "system" or actor_id is not None:
            raise HTTPException(status_code=403, detail="仅系统任务可执行自动验收")
    else:
        if actor_id is None:
            raise HTTPException(status_code=403, detail="缺少订单操作人")
        actual_role = _ensure_order_actor(order, actor_id)
        if actor_role and actor_role != actual_role:
            raise HTTPException(status_code=403, detail="订单身份与操作不匹配")

    specs = {
        OrderAction.ACCEPT_BOOKING: ({OrderStatus.PENDING}, OrderStatus.AWAITING_PAYMENT, "photographer"),
        OrderAction.REJECT_BOOKING: ({OrderStatus.PENDING}, OrderStatus.CANCELLED, "photographer"),
        OrderAction.START_SERVICE: ({OrderStatus.CONFIRMED}, OrderStatus.IN_PROGRESS, "photographer"),
        OrderAction.SUBMIT_DELIVERY: ({OrderStatus.IN_PROGRESS, OrderStatus.DELIVERED}, OrderStatus.DELIVERED, "photographer"),
        OrderAction.REQUEST_REVISION: ({OrderStatus.DELIVERED}, OrderStatus.DELIVERED, "customer"),
        OrderAction.ACKNOWLEDGE_REVISION: ({OrderStatus.DELIVERED}, OrderStatus.DELIVERED, "photographer"),
        OrderAction.ACCEPT_DELIVERY: ({OrderStatus.DELIVERED}, OrderStatus.COMPLETED, "customer"),
        OrderAction.AUTO_ACCEPT_DELIVERY: ({OrderStatus.DELIVERED}, OrderStatus.COMPLETED, "system"),
        OrderAction.SUBMIT_REVIEW: ({OrderStatus.RECEIVED, OrderStatus.COMPLETED}, OrderStatus.COMPLETED, "customer"),
        OrderAction.CANCEL_ORDER: ({OrderStatus.PENDING, OrderStatus.AWAITING_PAYMENT, OrderStatus.CONFIRMED}, OrderStatus.CANCELLED, None),
        OrderAction.ADMIN_CANCEL_ORDER: (
            {OrderStatus.PENDING, OrderStatus.AWAITING_PAYMENT, OrderStatus.CONFIRMED, OrderStatus.IN_PROGRESS, OrderStatus.DELIVERED},
            OrderStatus.CANCELLED,
            "admin",
        ),
    }
    allowed_statuses, target_status, required_role = specs[action]

    if order.after_sales_status == "dispute_open":
        raise HTTPException(status_code=409, detail="争议处理中，订单履约动作已暂停，请等待平台处理")

    # 历史 legacy 订单没有可信成交金额，继续保留阶段 A 的直接确认兼容行为。
    if action == OrderAction.ACCEPT_BOOKING and order.final_price is None:
        target_status = OrderStatus.CONFIRMED

    self_transition_actions = {
        OrderAction.SUBMIT_DELIVERY,
        OrderAction.REQUEST_REVISION,
        OrderAction.ACKNOWLEDGE_REVISION,
        OrderAction.SUBMIT_REVIEW,
    }
    if order.status == target_status and action not in self_transition_actions:
        return order
    if required_role and actual_role != required_role:
        raise HTTPException(status_code=403, detail="当前订单身份无权执行该操作")
    if order.status not in allowed_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"订单当前状态 {_status_value(order.status)} 不允许执行动作 {action.value}",
        )

    event_type = action.value
    note = None
    if action == OrderAction.ACCEPT_BOOKING:
        _ensure_photographer_available(
            db,
            order.photographer_id,
            order.appointment_time,
            order.duration_minutes,
            exclude_order_id=order.id,
        )
        if target_status == OrderStatus.AWAITING_PAYMENT:
            from backend.app.core.config import settings
            order.payment_due_at = _utc_now_naive() + timedelta(minutes=settings.PAYMENT_WINDOW_MINUTES)
            event_type, note = "awaiting_payment", "摄影师已接受预约，等待客户在规定时间内支付"
        else:
            event_type, note = "confirmed", "摄影师确认预约"
    elif action in {OrderAction.REJECT_BOOKING, OrderAction.CANCEL_ORDER, OrderAction.ADMIN_CANCEL_ORDER}:
        refund_cancelled_order = None
        if action in {OrderAction.CANCEL_ORDER, OrderAction.ADMIN_CANCEL_ORDER}:
            from backend.app.services.payment_service import ensure_order_not_settled, refund_cancelled_order
            ensure_order_not_settled(db, order)
        message = "拒绝订单必须填写原因" if action == OrderAction.REJECT_BOOKING else "取消订单必须填写原因"
        reason = _validate_note(payload.get("reason"), message)
        order.cancellation_reason = reason
        order.cancelled_by = actual_role
        if actual_role == "photographer":
            order.rejection_reason = reason
        event_type, note = "cancelled", reason
        active_request = get_active_reschedule_request(db, order.id)
        if active_request:
            active_request.status = OrderRescheduleStatus.WITHDRAWN
            active_request.response_note = "订单已取消"
            active_request.resolved_at = _utc_now_naive()
        order.reschedule_requested_time = None
        order.reschedule_reason = None
        if action in {OrderAction.CANCEL_ORDER, OrderAction.ADMIN_CANCEL_ORDER}:
            refund_cancelled_order(
                db,
                order,
                actual_role,
                reason,
                requested_by=actor_id,
            )
    elif action == OrderAction.START_SERVICE:
        if order.final_price is not None and order.payment_status != "paid_in_escrow":
            raise HTTPException(status_code=400, detail="请先完成全额支付，资金进入平台担保后再开始服务")
        event_type, note = "in_progress", "拍摄进入进行中"
    elif action == OrderAction.SUBMIT_DELIVERY:
        from backend.app.services.delivery_service import create_delivery_version

        delivery_payload = payload.get("delivery") or {}
        delivery_files = payload.get("delivery_files") or [
            {
                "file_url": url,
                "file_name": f"legacy-{index}",
                "file_type": "image/unknown",
            }
            for index, url in enumerate(delivery_payload.get("images") or [], start=1)
        ]
        delivery, created = create_delivery_version(
            db,
            order,
            actor_id,
            delivery_payload.get("description"),
            delivery_files,
            payload.get("idempotency_key") or f"delivery:{order.id}:{_utc_now_naive().isoformat()}",
        )
        if not created:
            return order
        event_type = "delivery_submitted" if delivery.version == 1 else "delivery_resubmitted"
        note = f"摄影师提交交付 V{delivery.version}" + (f"：{delivery.description}" if delivery.description else "")
    elif action == OrderAction.REQUEST_REVISION:
        from backend.app.services.delivery_service import request_order_revision

        revision, created = request_order_revision(
            db,
            order,
            actor_id,
            payload.get("instructions"),
            payload.get("reference_files") or [],
            payload.get("idempotency_key") or f"revision:{order.id}:{_utc_now_naive().isoformat()}",
        )
        if not created:
            return order
        event_type = "revision_requested"
        note = f"客户申请第 {revision.sequence} 次修改：{revision.instructions}"
    elif action == OrderAction.ACKNOWLEDGE_REVISION:
        from backend.app.services.delivery_service import acknowledge_revision_request

        revision = acknowledge_revision_request(
            db,
            order,
            payload.get("revision_id"),
            actor_id,
            payload.get("expected_redelivery_at"),
        )
        event_type = "revision_acknowledged"
        note = f"摄影师确认预计于 {_format_appointment(revision.expected_redelivery_at)} 前重新交付"
    elif action in {OrderAction.ACCEPT_DELIVERY, OrderAction.AUTO_ACCEPT_DELIVERY}:
        from backend.app.services.delivery_service import accept_current_delivery

        automatic = action == OrderAction.AUTO_ACCEPT_DELIVERY
        delivery = accept_current_delivery(db, order, "automatic" if automatic else "manual")
        if order.final_price is not None:
            from backend.app.services.payment_service import settle_order
            settle_order(db, order)
        event_type = "delivery_auto_accepted" if automatic else "delivery_accepted"
        note = f"{'验收期限届满，系统自动验收' if automatic else '客户确认验收'}交付 V{delivery.version}，订单已完成"
    elif action == OrderAction.SUBMIT_REVIEW:
        if order.rating is not None:
            return order
        rating = payload.get("rating")
        if rating is None or not 1 <= int(rating) <= 10:
            raise HTTPException(status_code=400, detail="评分必须为 1-10 分")
        order.rating = int(rating)
        order.review_text = payload.get("review_text")
        if order.completed_at is None:
            order.completed_at = _utc_now_naive()
            order.completion_type = order.completion_type or "legacy_review"
        event_type = "review_submitted"
        note = order.review_text or "客户完成评价；订单完成状态保持不变"

    order.status = target_status
    from backend.app.services.automation_service import refresh_order_action_metadata
    refresh_order_action_metadata(db, order)
    record_order_event(
        db,
        order.id,
        actor_id,
        actual_role,
        event_type,
        target_status,
        note,
    )
    db.commit()
    db.refresh(order)
    return order


def update_order_status(
    db: Session,
    order: Order,
    new_status: OrderStatus,
    photographer_id: int,
    rejection_reason: str | None = None,
) -> Order:
    """兼容旧调用方，内部映射到动作状态机。"""
    action_map = {
        OrderStatus.CONFIRMED: OrderAction.ACCEPT_BOOKING,
        OrderStatus.CANCELLED: OrderAction.REJECT_BOOKING,
        OrderStatus.IN_PROGRESS: OrderAction.START_SERVICE,
        OrderStatus.DELIVERED: OrderAction.SUBMIT_DELIVERY,
    }
    action = action_map.get(new_status)
    if not action:
        raise HTTPException(status_code=400, detail="不支持直接指定该目标状态")
    payload = {"reason": rejection_reason}
    if action == OrderAction.SUBMIT_DELIVERY:
        payload = {"delivery": order.delivery or {"images": ["legacy"], "description": "摄影师交付作品"}}
    return transition_order(
        db,
        order=order,
        action=action,
        actor_id=photographer_id,
        actor_role="photographer",
        payload=payload,
    )

def get_my_orders_as_customer(
    db: Session,
    customer_id: int,
    status: OrderStatus | None = None,
    skip: int = 0,
    limit: int = 20
) -> list[Order]:
    """客户查看自己的订单"""
    from backend.app.services.delivery_service import expire_acceptance_orders
    from backend.app.services.payment_service import expire_payment_orders
    expire_payment_orders(db)
    expire_acceptance_orders(db)
    expired = expire_reschedule_requests(db)
    if expired:
        db.commit()
    query = db.query(Order).options(joinedload(Order.reschedule_requests)).filter(Order.customer_id == customer_id)
    if status:
        query = query.filter(Order.status == status)
    return query.order_by(Order.created_at.desc()).offset(skip).limit(limit).all()


def get_my_orders_as_photographer(
    db: Session,
    photographer_id: int,
    status: OrderStatus | None = None,
    skip: int = 0,
    limit: int = 20
) -> list[Order]:
    """摄影师查看分配给自己的订单"""
    from backend.app.services.delivery_service import expire_acceptance_orders
    from backend.app.services.payment_service import expire_payment_orders
    expire_payment_orders(db)
    expire_acceptance_orders(db)
    expired = expire_reschedule_requests(db)
    if expired:
        db.commit()
    query = db.query(Order).options(joinedload(Order.reschedule_requests)).filter(Order.photographer_id == photographer_id)
    if status:
        query = query.filter(Order.status == status)
    return query.order_by(Order.created_at.desc()).offset(skip).limit(limit).all()


def get_photographer_stats(db: Session, photographer_id: int) -> dict:
    """获取摄影师数据统计"""
    from sqlalchemy import func

    now = datetime.now(timezone.utc)

    # 本月起止
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    # 下月第一天
    if now.month == 12:
        month_end = now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        month_end = now.replace(month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)

    # 本周起止（周一为起始）
    weekday = now.weekday()  # 0=周一
    week_start = (now - timedelta(days=weekday)).replace(hour=0, minute=0, second=0, microsecond=0)
    week_end = (week_start + timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)

    base_query = db.query(Order).filter(
        Order.photographer_id == photographer_id,
        Order.status != OrderStatus.CANCELLED
    )

    # 本月接单数
    monthly_orders = base_query.filter(
        Order.created_at >= month_start,
        Order.created_at < month_end
    ).count()

    # 本周接单数
    weekly_orders = base_query.filter(
        Order.created_at >= week_start,
        Order.created_at < week_end
    ).count()

    # 订单完成率（已完成 / 全部非取消订单）
    total_orders = base_query.count()
    completed_orders = base_query.filter(
        Order.status.in_([OrderStatus.COMPLETED, OrderStatus.RECEIVED, OrderStatus.REVIEWED])
    ).count()
    completion_rate = round(completed_orders / total_orders * 100, 1) if total_orders > 0 else 0.0

    # 客户平均评分（5分制，数据库存1-10，除以2转换）
    avg_rating_result = base_query.filter(Order.rating.isnot(None)).with_entities(
        func.avg(Order.rating)
    ).scalar()
    avg_rating = round((avg_rating_result or 0) / 2, 1)

    return {
        "monthly_orders": monthly_orders,
        "weekly_orders": weekly_orders,
        "completion_rate": completion_rate,
        "avg_rating": avg_rating,
    }
