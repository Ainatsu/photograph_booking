"""分析事件服务：序列化事件记录并写入数据库。"""

from sqlalchemy.orm import Session

from backend.app.models.analytics import AnalyticsEvent
from backend.app.schemas.analytics import AnalyticsEventCreate


def serialize_analytics_event(event: AnalyticsEvent) -> dict:
    """将分析事件模型序列化为字典。"""
    return {
        "id": event.id,
        "user_id": event.user_id,
        "actor_id": event.actor_id,
        "event_type": event.event_type,
        "target_type": event.target_type,
        "target_id": event.target_id,
        "metadata": event.event_metadata,
        "created_at": event.created_at,
    }


def record_analytics_event(
    db: Session,
    data: AnalyticsEventCreate,
    actor_id: int | None = None,
) -> AnalyticsEvent:
    """创建并持久化一条分析事件记录，返回保存后的事件。"""
    event = AnalyticsEvent(
        user_id=data.user_id,
        actor_id=actor_id,
        event_type=data.event_type.strip(),
        target_type=data.target_type.strip(),
        target_id=(data.target_id or "").strip() or None,
        event_metadata=data.metadata or None,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event
