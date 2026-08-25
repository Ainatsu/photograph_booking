"""评论相关 Schema 定义"""

from datetime import datetime

from pydantic import BaseModel, Field


class CommentCreateRequest(BaseModel):
    """发表评论请求"""

    target_type: str = Field(..., description="'portfolio' or 'package'")
    target_id: str = Field(..., description="Target item id")
    content: str = Field(..., min_length=1, max_length=500, description="Comment content")


class CommentItem(BaseModel):
    """评论条目"""

    id: int
    user_id: int
    user_display_name: str | None = None
    user_avatar_url: str | None = None
    target_type: str
    target_id: str
    content: str
    created_at: datetime | None = None


class CommentListResponse(BaseModel):
    """评论列表响应"""

    items: list[CommentItem]
    total: int
