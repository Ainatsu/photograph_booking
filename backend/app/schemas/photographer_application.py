"""摄影师入驻申请相关 Schema 定义"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PhotographerApplicationSubmit(BaseModel):
    """提交摄影师入驻申请请求"""

    profile_intro: Optional[str] = Field(None, max_length=1000, description="摄影师基础介绍")
    location: str = Field(..., min_length=1, max_length=255, description="国家/地区；中国大陆细化到省份与城市")
    equipment: str = Field(..., min_length=1, max_length=500, description="设备信息")
    styles: list[str] = Field(default_factory=list, description="风格领域")
    portfolio_refs: list[dict] = Field(default_factory=list, description="提交审核的作品")


class PhotographerApplicationReviewRequest(BaseModel):
    """审核摄影师入驻申请请求"""

    review_note: Optional[str] = Field(None, max_length=1000, description="审核备注")


class PhotographerApplicationResponse(BaseModel):
    """摄影师入驻申请响应"""

    id: int
    user_id: int
    user_display_name: Optional[str] = None
    user_email: Optional[str] = None
    user_avatar_url: Optional[str] = None
    status: str
    profile_intro: Optional[str] = None
    location: str
    equipment: str
    styles: list[str] = Field(default_factory=list)
    portfolio_refs: list[dict] = Field(default_factory=list)
    review_note: Optional[str] = None
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
