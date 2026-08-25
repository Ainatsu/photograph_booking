"""通知功能相关的 Schema 定义"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class NotificationResponse(BaseModel):
    """通知消息响应"""
    id: int
    order_id: Optional[int] = None
    project_id: Optional[int] = None
    notification_type: str
    title: str
    content: str
    action_url: Optional[str] = None
    is_read: bool
    read_at: Optional[datetime] = None
    created_at: datetime
