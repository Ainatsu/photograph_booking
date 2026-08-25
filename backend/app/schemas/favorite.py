"""收藏相关 Schema 定义"""

from pydantic import BaseModel, Field
from datetime import datetime


class FavoriteToggleRequest(BaseModel):
    """切换收藏请求"""

    work_id: str | None = Field(default=None, description="作品 ID（作品收藏时使用）")
    package_id: str | None = Field(default=None, description="方案 ID（方案收藏时使用）")
    photographer_id: int | None = Field(default=None, description="摄影师用户 ID")
    work_data: dict | None = Field(default=None, description="作品快照数据")
    package_data: dict | None = Field(default=None, description="方案快照数据")


class FavoriteToggleResponse(BaseModel):
    """切换收藏响应"""

    favorited: bool


class FavoriteWorkItem(BaseModel):
    """收藏作品条目"""

    work_id: str
    work_data: dict | None = None
    photographer_id: int
    photographer_name: str | None = None
    photographer_avatar: str | None = None
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class FavoritePackageItem(BaseModel):
    """收藏套餐条目"""

    package_id: str
    package_data: dict | None = None
    photographer_id: int
    photographer_name: str | None = None
    photographer_avatar: str | None = None
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class FavoriteListResponse(BaseModel):
    """收藏作品列表响应"""

    items: list[FavoriteWorkItem]
    total: int


class FavoritePackageListResponse(BaseModel):
    """收藏套餐列表响应"""

    items: list[FavoritePackageItem]
    total: int
