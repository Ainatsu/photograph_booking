"""点赞相关 Schema 定义"""

from pydantic import BaseModel, Field
from datetime import datetime


class LikeToggleRequest(BaseModel):
    """切换点赞请求"""

    target_type: str = Field(..., description="'portfolio' 或 'package'")
    target_id: str = Field(..., description="作品/方案的 uuid")


class LikeToggleResponse(BaseModel):
    """切换点赞响应"""

    liked: bool
    count: int


class LikedWorkItem(BaseModel):
    """点赞过的作品条目"""

    work_id: str
    work_data: dict | None = None
    photographer_id: int
    photographer_name: str | None = None
    photographer_avatar: str | None = None
    liked_at: datetime | None = None


class LikedWorkListResponse(BaseModel):
    """点赞作品列表响应"""

    items: list[LikedWorkItem]
    total: int


class BatchLikeStatusResponse(BaseModel):
    """批量点赞状态响应，key 为 target_id，value 为是否点赞"""
    pass  # 实际返回 dict[str, bool]，此处仅用于文档标注


class BatchLikeCountResponse(BaseModel):
    """批量点赞数响应，key 为 target_id，value 为点赞数"""
    pass  # 实际返回 dict[str, int]，此处仅用于文档标注
