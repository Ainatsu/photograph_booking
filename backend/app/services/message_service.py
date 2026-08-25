"""站内消息、联系人会话与未读状态的服务。"""

from datetime import datetime, timezone

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException, status
from backend.app.core.timezone import isoformat_utc
from backend.app.services.ws_manager import manager
from backend.app.models.message import Message
from backend.app.models.order import Order
from backend.app.models.order_event import OrderEvent
from backend.app.models.chat_read_state import ChatReadState
from backend.app.services.order_service import get_order_history, serialize_order_history_card


def _serialize_contact(user, unread_count: int = 0, last_message: dict | None = None) -> dict:
    """序列化联系人为字典（含未读数与最后一条消息）。"""
    return {
        "id": user.id,
        "display_name": user.display_name,
        "role": user.role,
        "avatar_url": user.avatar_url,
        "unread_count": unread_count,
        "last_message": last_message,
    }


def _get_latest_timeline_for_pair(db: Session, user_id: int, other_user_id: int) -> dict | None:
    """获取两个用户之间的最新消息或订单事件。"""
    message = (
        db.query(Message)
        .filter(
            or_(
                and_(Message.sender_id == user_id, Message.receiver_id == other_user_id),
                and_(Message.sender_id == other_user_id, Message.receiver_id == user_id),
            )
        )
        .order_by(Message.created_at.desc(), Message.id.desc())
        .first()
    )

    order_ids = [
        row[0]
        for row in db.query(Order.id).filter(
            or_(
                and_(Order.customer_id == user_id, Order.photographer_id == other_user_id),
                and_(Order.customer_id == other_user_id, Order.photographer_id == user_id),
            )
        ).all()
    ]

    latest_event = None
    if order_ids:
        latest_event = (
            db.query(OrderEvent)
            .filter(OrderEvent.order_id.in_(order_ids))
            .order_by(OrderEvent.created_at.desc(), OrderEvent.id.desc())
            .first()
        )

    message_time = message.created_at if message else None
    event_time = latest_event.created_at if latest_event else None

    if message_time and event_time:
        if message_time >= event_time:
            return {"type": "message", "content": message.content, "created_at": isoformat_utc(message_time)}
        else:
            return {"type": "order_event", "event_type": latest_event.event_type, "created_at": isoformat_utc(event_time)}
    elif message_time:
        return {"type": "message", "content": message.content, "created_at": isoformat_utc(message_time)}
    elif event_time:
        return {"type": "order_event", "event_type": latest_event.event_type, "created_at": isoformat_utc(event_time)}

    return None


def _contact_unread_count(db: Session, current_user_id: int, contact_user_id: int) -> int:
    """统计与某联系人的未读消息和未读订单事件数。"""
    message_unread = db.query(Message).filter(
        Message.receiver_id == current_user_id,
        Message.sender_id == contact_user_id,
        Message.is_read == False
    ).count()
    order_event_unread = _order_event_unread_count(db, current_user_id, contact_user_id)
    return message_unread + order_event_unread


def _get_chat_read_state(db: Session, user_id: int, contact_user_id: int) -> ChatReadState | None:
    """查询用户与联系人之间的已读状态记录。"""
    return db.query(ChatReadState).filter(
        ChatReadState.user_id == user_id,
        ChatReadState.contact_user_id == contact_user_id,
    ).first()


def _upsert_chat_read_state(
    db: Session,
    user_id: int,
    contact_user_id: int,
    order_events_read_at: datetime | None = None,
) -> ChatReadState:
    """更新或新建用户与联系人之间的已读状态。"""
    state = _get_chat_read_state(db, user_id, contact_user_id)
    if state is None:
        state = ChatReadState(
            user_id=user_id,
            contact_user_id=contact_user_id,
            order_events_read_at=order_events_read_at,
        )
        db.add(state)
    else:
        state.order_events_read_at = order_events_read_at
    db.flush()
    return state


def _contact_ids_for_user(db: Session, user_id: int) -> set[int]:
    """收集用户有过往来消息或共同订单的联系人 ID 集合。"""
    contact_ids = set()

    sent = db.query(Message.receiver_id).filter(Message.sender_id == user_id).distinct().all()
    received = db.query(Message.sender_id).filter(Message.receiver_id == user_id).distinct().all()
    for row in sent + received:
        contact_ids.add(row[0])

    my_orders = db.query(Order.customer_id, Order.photographer_id).filter(
        (Order.customer_id == user_id) | (Order.photographer_id == user_id)
    ).all()
    for customer_id, photographer_id in my_orders:
        if customer_id != user_id:
            contact_ids.add(customer_id)
        if photographer_id != user_id:
            contact_ids.add(photographer_id)

    return contact_ids


def _order_event_unread_count(db: Session, user_id: int, contact_user_id: int) -> int:
    """统计与某联系人相关订单的未读事件数。"""
    read_state = _get_chat_read_state(db, user_id, contact_user_id)
    read_at = read_state.order_events_read_at if read_state else None

    order_ids = [
        row[0]
        for row in db.query(Order.id).filter(
            or_(
                and_(Order.customer_id == user_id, Order.photographer_id == contact_user_id),
                and_(Order.customer_id == contact_user_id, Order.photographer_id == user_id),
            )
        ).all()
    ]
    if not order_ids:
        return 0

    query = (
        db.query(OrderEvent)
        .join(Order, Order.id == OrderEvent.order_id)
        .filter(
            OrderEvent.order_id.in_(order_ids),
            or_(OrderEvent.actor_id != user_id, OrderEvent.actor_id.is_(None)),
        )
    )
    if read_at is not None:
        query = query.filter(OrderEvent.created_at > read_at)
    return query.count()


def _normalize_message_reference(reference: dict | None) -> dict | None:
    """规范化消息引用：限定类型并裁剪标题与链接长度。"""
    if hasattr(reference, "model_dump"):
        reference = reference.model_dump(exclude_none=True)
    if not isinstance(reference, dict):
        return None

    reference_type = str(reference.get("type") or "item").strip()
    if reference_type not in {"package", "work", "item"}:
        reference_type = "item"

    title = str(reference.get("title") or "").strip()
    if not title:
        return None

    url = str(reference.get("url") or "").strip()
    cover_url = str(reference.get("cover_url") or reference.get("coverUrl") or "").strip()
    normalized = {
        "type": reference_type,
        "title": title[:200],
    }
    if url:
        normalized["url"] = url[:500]
    if cover_url:
        normalized["cover_url"] = cover_url[:500]
    return normalized


async def send_message(
    db: Session,
    sender_id: int,
    receiver_id: int,
    content: str,
    order_id: int | None = None,
    reference: dict | None = None,
) -> Message:
    """发送消息"""

    # 不能给自己发消息
    if sender_id == receiver_id:
        raise HTTPException(status_code=400, detail="不能给自己发消息")

    if order_id is not None:
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            raise HTTPException(status_code=404, detail="关联订单不存在")
        participants = {order.customer_id, order.photographer_id}
        if sender_id not in participants or receiver_id not in participants:
            raise HTTPException(status_code=403, detail="只能将消息绑定到双方共同参与的订单")

    message_reference = _normalize_message_reference(reference)
    message = Message(
        sender_id=sender_id,
        receiver_id=receiver_id,
        content=content,
        order_id=order_id,
        reference=message_reference,
    )
    db.add(message)
    db.commit()
    db.refresh(message)

    # 在 send_message 函数的 return message 之前添加：
    # 实时推送给接收方
    await manager.send_personal_message({
        "type": "new_message",
        "message": {
            "item_type": "message",
            "id": message.id,
            "message_id": message.id,
            "sender_id": sender_id,
            "receiver_id": receiver_id,
            "content": content,
            "order_id": order_id,
            "reference": message_reference,
            "is_read": message.is_read,
            "created_at": isoformat_utc(message.created_at)
        }
    }, receiver_id)

    return message


def _serialize_message_timeline_item(message: Message) -> dict:
    """将消息序列化为时间线条目。"""
    return {
        "item_type": "message",
        "id": message.id,
        "message_id": message.id,
        "order_event_id": None,
        "sender_id": message.sender_id,
        "receiver_id": message.receiver_id,
        "content": message.content,
        "order_id": message.order_id,
        "reference": message.reference,
        "is_read": message.is_read,
        "event_type": None,
        "status": None,
        "actor_id": None,
        "actor_role": None,
        "actor_name": None,
        "note": None,
        "customer_id": None,
        "photographer_id": None,
        "package_snapshot": None,
        "created_at": message.created_at,
    }


def _timeline_sort_time(value):
    """将时间统一为可比较的无时区时间用于排序。"""
    if value is None:
        return datetime.min
    if getattr(value, "tzinfo", None) is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def get_conversation(
        db: Session,
        user_id: int,
        other_user_id: int,
        skip: int = 0,
        limit: int = 50,
        order_id: int | None = None,
) -> list[dict]:
    """查看两个用户之间的对话历史"""
    message_query = db.query(Message).filter(
        (
                (Message.sender_id == user_id) & (Message.receiver_id == other_user_id)
        ) | (
                (Message.sender_id == other_user_id) & (Message.receiver_id == user_id)
        )
    )
    if order_id is not None:
        message_query = message_query.filter(Message.order_id == order_id)
    messages = message_query.order_by(Message.created_at.asc(), Message.id.asc()).all()

    order_query = (
        db.query(Order)
        .options(joinedload(Order.customer), joinedload(Order.photographer))
        .filter(
            or_(
                and_(Order.customer_id == user_id, Order.photographer_id == other_user_id),
                and_(Order.customer_id == other_user_id, Order.photographer_id == user_id),
            )
        )
    )
    if order_id is not None:
        order_query = order_query.filter(Order.id == order_id)
    orders = order_query.all()
    if order_id is not None and not orders:
        raise HTTPException(status_code=403, detail="只能查看与双方共同参与的订单沟通")

    timeline = [_serialize_message_timeline_item(message) for message in messages]
    for order in orders:
        timeline.extend(
            serialize_order_history_card(order, history_item)
            for history_item in get_order_history(db, order)
        )

    timeline.sort(
        key=lambda item: (
            _timeline_sort_time(item["created_at"]),
            0 if item["item_type"] == "order_event" else 1,
            str(item["id"]),
        )
    )
    return timeline[skip: skip + limit]


def get_my_contacts(db: Session, user_id: int) -> list[dict]:
    """获取当前用户的联系人列表（含未读数与最新动态）。"""
    from backend.app.models.user import User

    contact_ids = _contact_ids_for_user(db, user_id)

    contacts = []
    for cid in contact_ids:
        user = db.query(User).filter(User.id == cid).first()
        if user:
            contacts.append(_serialize_contact(
                user,
                _contact_unread_count(db, user_id, cid),
                _get_latest_timeline_for_pair(db, user_id, cid),
            ))
    return contacts


def get_contact_by_id(db: Session, current_user_id: int, contact_user_id: int) -> dict:
    """按 ID 获取单个联系人信息。"""
    from backend.app.models.user import User

    if current_user_id == contact_user_id:
        raise HTTPException(status_code=400, detail="不能给自己发消息")

    user = db.query(User).filter(
        User.id == contact_user_id,
        User.is_active == True,
        User.is_banned == False,
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="联系人不存在")
    return _serialize_contact(user, _contact_unread_count(db, current_user_id, contact_user_id))


def get_unread_count(db: Session, user_id: int) -> int:
    """统计用户全部未读消息与订单事件数。"""
    message_count = db.query(Message).filter(
        Message.receiver_id == user_id,
        Message.is_read == False
    ).count()

    order_count = sum(
        _order_event_unread_count(db, user_id, contact_user_id)
        for contact_user_id in _contact_ids_for_user(db, user_id)
    )

    return message_count + order_count


def mark_as_read(db: Session, user_id: int, other_user_id: int) -> int:
    """将用户与联系人的消息标记为已读并更新已读状态。"""
    updated = db.query(Message).filter(
        Message.receiver_id == user_id,
        Message.sender_id == other_user_id,
        Message.is_read == False
    ).update({"is_read": True})

    order_events = (
        db.query(OrderEvent.created_at)
        .join(Order, Order.id == OrderEvent.order_id)
        .filter(
            or_(
                and_(Order.customer_id == user_id, Order.photographer_id == other_user_id),
                and_(Order.customer_id == other_user_id, Order.photographer_id == user_id),
            ),
            or_(OrderEvent.actor_id != user_id, OrderEvent.actor_id.is_(None)),
        )
        .order_by(OrderEvent.created_at.desc(), OrderEvent.id.desc())
        .all()
    )
    latest_read_at = order_events[0][0] if order_events else None
    _upsert_chat_read_state(db, user_id, other_user_id, latest_read_at)
    db.commit()
    return updated
