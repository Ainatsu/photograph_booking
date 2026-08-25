"""数据埋点相关 Schema 定义"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class AnalyticsEventCreate(BaseModel):
    """上报埋点事件请求"""

    user_id: int = Field(..., description="事件归属用户，摄影师仪表盘中通常为摄影师用户 ID")
    event_type: str = Field(..., min_length=1, max_length=50, description="事件类型")
    target_type: str = Field(..., min_length=1, max_length=50, description="目标类型")
    target_id: Optional[str] = Field(None, max_length=80, description="目标 ID")
    metadata: dict[str, Any] | None = Field(default=None, description="事件补充信息")


class AnalyticsEventResponse(BaseModel):
    """埋点事件响应"""

    id: int
    user_id: int
    actor_id: Optional[int] = None
    event_type: str
    target_type: str
    target_id: Optional[str] = None
    metadata: dict[str, Any] | None = None
    created_at: datetime | None = None
