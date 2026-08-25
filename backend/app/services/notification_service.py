"""通知服务：将订单/企划事件写入发件箱并推送站内通知。"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.models.notification import OrderNotification, OutboxEvent
from backend.app.models.order import Order
from backend.app.models.order_event import OrderEvent
from backend.app.services.ws_manager import manager


NOTIFICATION_TITLES = {
    "created": "新的预约已提交",
    "awaiting_payment": "预约已确认，请及时支付",
    "payment_succeeded": "支付成功，资金已进入平台担保",
    "payment_expired": "支付超时，预约已关闭",
    "order_confirmation_expired": "预约确认超时，订单已关闭",
    "confirmed": "预约已确认",
    "in_progress": "拍摄服务已开始",
    "delivery_submitted": "摄影师已提交交付",
    "delivery_resubmitted": "摄影师已重新交付",
    "delivery_overdue": "订单交付已逾期",
    "delivery_accepted": "客户已确认验收",
    "delivery_auto_accepted": "订单已自动验收",
    "revision_requested": "客户提交了修改申请",
    "revision_acknowledged": "摄影师已确认返修排期",
    "order_reminder_sent": "订单有待处理事项",
    "reschedule_requested": "收到改期申请",
    "reschedule_expired": "改期申请已失效",
    "dispute_opened": "订单争议已提交平台",
    "dispute_resolved": "平台已完成争议仲裁",
    "cancelled": "订单已取消",
    "settlement_succeeded": "订单资金已完成结算",
    "project_application_submitted": "收到新的企划应邀",
    "project_application_updated": "摄影师更新了应邀方案",
    "project_application_withdrawn": "摄影师撤回了应邀方案",
    "project_application_selected": "你的应邀方案已被选定",
    "project_application_rejected": "企划应邀结果已更新",
    "project_expired": "企划招募已截止",
    "project_closed": "企划已关闭",
}


def _now() -> datetime:
    """返回当前 UTC 时间（不含时区信息）。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def enqueue_order_event(db: Session, event: OrderEvent, order: Order) -> OutboxEvent:
    """将订单事件写入发件箱并返回发件箱记录。"""
    event_key = f"order-event:{event.id}"
    existing = db.query(OutboxEvent).filter(OutboxEvent.event_key == event_key).first()
    if existing:
        return existing
    recipient_ids = sorted({int(order.customer_id), int(order.photographer_id)})
    outbox = OutboxEvent(
        event_key=event_key,
        aggregate_type="order",
        aggregate_id=str(order.id),
        event_type=event.event_type,
        recipient_ids=recipient_ids,
        payload={
            "order_id": order.id,
            "event_id": event.id,
            "event_type": event.event_type,
            "status": event.status,
            "actor_id": event.actor_id,
            "actor_role": event.actor_role,
            "note": event.note,
            "package_snapshot": order.package_snapshot,
        },
        status="pending",
        attempts=0,
        next_attempt_at=_now(),
    )
    db.add(outbox)
    db.flush()
    return outbox


def enqueue_project_notification(
    db: Session,
    *,
    project_id: int,
    event_key: str,
    event_type: str,
    recipient_ids: list[int],
    content: str,
    application_id: int | None = None,
) -> OutboxEvent | None:
    """将企划通知写入发件箱并返回发件箱记录。"""
    recipients = sorted({int(user_id) for user_id in recipient_ids if user_id is not None})
    if not recipients:
        return None
    full_event_key = f"project-event:{project_id}:{event_key}"
    existing = db.query(OutboxEvent).filter(OutboxEvent.event_key == full_event_key).first()
    if existing:
        return existing
    outbox = OutboxEvent(
        event_key=full_event_key,
        aggregate_type="project",
        aggregate_id=str(project_id),
        event_type=event_type,
        recipient_ids=recipients,
        payload={
            "project_id": project_id,
            "application_id": application_id,
            "event_type": event_type,
            "content": content,
        },
        status="pending",
        attempts=0,
        next_attempt_at=_now(),
    )
    db.add(outbox)
    db.flush()
    return outbox


def _notification_copy(outbox: OutboxEvent) -> tuple[str, str]:
    """根据发件箱事件生成通知标题与内容。"""
    payload = outbox.payload or {}
    title = NOTIFICATION_TITLES.get(outbox.event_type, "订单状态更新")
    if outbox.aggregate_type == "project":
        return title, payload.get("content") or f"企划 #{payload.get('project_id')} 状态已更新"
    content = payload.get("note") or f"订单 #{payload.get('order_id')} 状态已更新"
    return title, content


async def process_outbox_events(db: Session, limit: int = 100) -> dict:
    """处理待发送的发件箱事件，创建通知并实时推送，返回处理统计。"""
    now = _now()
    events = db.query(OutboxEvent).filter(
        OutboxEvent.status.in_(["pending", "failed"]),
        OutboxEvent.attempts < max(1, settings.OUTBOX_MAX_ATTEMPTS),
        or_(OutboxEvent.next_attempt_at.is_(None), OutboxEvent.next_attempt_at <= now),
    ).order_by(OutboxEvent.created_at.asc(), OutboxEvent.id.asc()).limit(limit).all()
    sent = 0
    failed = 0
    for outbox in events:
        attempt_number = int(outbox.attempts or 0) + 1
        outbox.status = "processing"
        outbox.attempts = attempt_number
        try:
            title, content = _notification_copy(outbox)
            payload = outbox.payload or {}
            is_project_notification = outbox.aggregate_type == "project"
            aggregate_id = int(payload.get("project_id") or payload.get("order_id") or outbox.aggregate_id)
            order_id = None if is_project_notification else aggregate_id
            action_url = f"/projects/{aggregate_id}" if is_project_notification else f"/orders/{aggregate_id}"
            created_notifications = []
            for user_id in outbox.recipient_ids or []:
                notification = db.query(OrderNotification).filter(
                    OrderNotification.outbox_event_id == outbox.id,
                    OrderNotification.user_id == int(user_id),
                ).first()
                if not notification:
                    notification = OrderNotification(
                        outbox_event_id=outbox.id,
                        user_id=int(user_id),
                        order_id=order_id,
                        notification_type=outbox.event_type,
                        title=title,
                        content=content,
                        action_url=action_url,
                    )
                    db.add(notification)
                    db.flush()
                created_notifications.append(notification)

            for notification in created_notifications:
                await manager.send_personal_message({
                    "type": "notification",
                    "notification": serialize_notification(notification),
                }, notification.user_id)

            outbox.status = "sent"
            outbox.processed_at = now
            outbox.last_error = None
            outbox.next_attempt_at = None
            db.commit()
            sent += 1
        except Exception as exc:
            db.rollback()
            failed_event = db.query(OutboxEvent).filter(OutboxEvent.id == outbox.id).first()
            if failed_event:
                failed_event.attempts = attempt_number
                failed_event.status = "failed"
                failed_event.last_error = str(exc)[:2000]
                failed_event.next_attempt_at = _now() + timedelta(seconds=min(3600, 30 * (2 ** max(0, attempt_number - 1))))
                db.commit()
            failed += 1
    return {"processed": len(events), "sent": sent, "failed": failed}


def serialize_notification(item: OrderNotification) -> dict:
    """将通知模型序列化为字典。"""
    outbox = item.outbox_event
    project_id = None
    if outbox and outbox.aggregate_type == "project":
        project_id = int((outbox.payload or {}).get("project_id") or outbox.aggregate_id)
    return {
        "id": item.id,
        "order_id": item.order_id,
        "project_id": project_id,
        "notification_type": item.notification_type,
        "title": item.title,
        "content": item.content,
        "action_url": item.action_url,
        "is_read": item.is_read,
        "read_at": item.read_at,
        "created_at": item.created_at,
    }


def list_notifications(db: Session, user_id: int, unread_only: bool = False, skip: int = 0, limit: int = 50):
    """分页查询用户的站内通知列表，可按未读过滤。"""
    query = db.query(OrderNotification).filter(OrderNotification.user_id == user_id)
    if unread_only:
        query = query.filter(OrderNotification.is_read.is_(False))
    return query.order_by(OrderNotification.created_at.desc(), OrderNotification.id.desc()).offset(skip).limit(limit).all()


def unread_notification_count(db: Session, user_id: int) -> int:
    """统计用户未读通知的数量。"""
    return db.query(OrderNotification).filter(
        OrderNotification.user_id == user_id,
        OrderNotification.is_read.is_(False),
    ).count()


def mark_notification_read(db: Session, user_id: int, notification_id: int | None = None) -> int:
    """将用户通知标记为已读，返回本次更新的数量。"""
    query = db.query(OrderNotification).filter(
        OrderNotification.user_id == user_id,
        OrderNotification.is_read.is_(False),
    )
    if notification_id is not None:
        query = query.filter(OrderNotification.id == notification_id)
    items = query.all()
    now = _now()
    for item in items:
        item.is_read = True
        item.read_at = now
    if items:
        db.commit()
    return len(items)


async def run_outbox_worker(poll_interval_seconds: int | None = None) -> None:
    """常驻后台任务：按间隔循环处理发件箱事件。"""
    import asyncio
    from backend.app.core.database import SessionLocal

    interval = max(5, poll_interval_seconds or settings.ORDER_AUTOMATION_POLL_SECONDS)
    while True:
        db = SessionLocal()
        try:
            from backend.app.services.project_service import expire_open_projects
            expire_open_projects(db)
            await process_outbox_events(db)
        except asyncio.CancelledError:
            db.rollback()
            raise
        except Exception:
            db.rollback()
        finally:
            db.close()
        await asyncio.sleep(interval)
