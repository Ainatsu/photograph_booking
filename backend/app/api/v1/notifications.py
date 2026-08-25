"""
订单通知 API 路由

提供用户通知列表、未读数统计和已读标记等功能。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_active_user
from backend.app.core.database import get_db
from backend.app.models.user import User
from backend.app.schemas.notification import NotificationResponse
from backend.app.services.notification_service import (
    list_notifications,
    mark_notification_read,
    serialize_notification,
    unread_notification_count,
)


router = APIRouter(prefix="/notifications", tags=["订单通知"])


@router.get("/", response_model=list[NotificationResponse])
def get_notifications(
    unread_only: bool = False,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """分页获取当前用户的通知列表，可按未读状态筛选"""
    return [
        serialize_notification(item)
        for item in list_notifications(db, current_user.id, unread_only, skip, limit)
    ]


@router.get("/unread-count")
def get_notification_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """获取当前用户的未读通知数量"""
    return {"count": unread_notification_count(db, current_user.id)}


@router.put("/{notification_id}/read")
def read_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """将指定通知标记为已读"""
    return {"updated": mark_notification_read(db, current_user.id, notification_id)}


@router.put("/read-all")
def read_all_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """将当前用户的全部通知标记为已读"""
    return {"updated": mark_notification_read(db, current_user.id)}
