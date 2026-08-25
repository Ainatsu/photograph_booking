"""轻量行为事件采集相关 API 路由。"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_active_user_optional
from backend.app.core.database import get_db
from backend.app.models.user import User
from backend.app.schemas.analytics import AnalyticsEventCreate, AnalyticsEventResponse
from backend.app.services.analytics_service import (
    record_analytics_event,
    serialize_analytics_event,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.post(
    "/events",
    response_model=AnalyticsEventResponse,
    status_code=status.HTTP_201_CREATED,
    summary="记录轻量行为事件",
)
def create_analytics_event(
    data: AnalyticsEventCreate,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_active_user_optional),
):
    """记录一条轻量行为事件。"""
    event = record_analytics_event(db, data, current_user.id if current_user else None)
    return serialize_analytics_event(event)
