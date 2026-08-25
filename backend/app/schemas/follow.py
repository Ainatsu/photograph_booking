"""关注/粉丝功能相关的 Schema 定义"""

from pydantic import BaseModel, Field
from typing import Optional


class FollowToggleResponse(BaseModel):
    """关注/取关操作的结果响应"""
    following: bool = Field(..., description="是否已关注")
    follower_count: int = Field(..., description="粉丝数")
    following_count: int = Field(..., description="关注数")


class FollowUserItem(BaseModel):
    """关注/粉丝列表中的用户项"""
    user_id: int
    display_name: str
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    role: str = "customer"
    is_followed: bool = False  # 当前用户是否也关注了此人
    followed_at: Optional[str] = None


class FollowListResponse(BaseModel):
    """关注/粉丝列表响应"""
    items: list[FollowUserItem]
    total: int