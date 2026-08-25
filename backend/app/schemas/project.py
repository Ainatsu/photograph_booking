"""项目相关 Schema 定义"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, Field

from backend.app.schemas.order import OrderResponse


class ProjectBase(BaseModel):
    """项目基础信息模型"""

    title: str = Field(..., min_length=1, max_length=120)
    description: str = Field(..., min_length=1)
    category: str = Field(..., min_length=1, max_length=50)
    style_tags: Optional[list[str]] = None
    city: str = Field(..., min_length=1, max_length=80)
    location_text: Optional[str] = Field(None, max_length=255)
    location_name: Optional[str] = Field(None, max_length=120)
    location_address: Optional[str] = Field(None, max_length=255)
    location_latitude: Optional[Decimal] = Field(None, ge=-90, le=90)
    location_longitude: Optional[Decimal] = Field(None, ge=-180, le=180)
    location_place_id: Optional[str] = Field(None, max_length=160)
    location_provider: Optional[str] = Field(None, max_length=30)
    coordinate_system: Optional[str] = Field(None, pattern="^(WGS84|GCJ02)$")
    location_precision: Optional[str] = Field(None, pattern="^(exact|approximate)$")
    shoot_date_start: Optional[datetime] = None
    shoot_date_end: Optional[datetime] = None
    duration_minutes: Optional[int] = Field(None, gt=0)
    budget_min: Optional[int] = Field(None, ge=0)
    budget_max: Optional[int] = Field(None, ge=0)
    deliverables: Optional[Any] = None
    reference_images: Optional[list[str]] = None
    visibility: str = Field("public", pattern="^(public|invite_only)$")
    expires_at: Optional[datetime] = None


class ProjectCreate(ProjectBase):
    """创建项目请求"""

    publish: bool = False

    def model_post_init(self, __context: Any) -> None:
        """校验经纬度必须同时提供"""
        if (self.location_latitude is None) != (self.location_longitude is None):
            raise ValueError("location_latitude and location_longitude must be provided together")


class ProjectUpdate(BaseModel):
    """更新项目请求"""

    title: Optional[str] = Field(None, min_length=1, max_length=120)
    description: Optional[str] = Field(None, min_length=1)
    category: Optional[str] = Field(None, min_length=1, max_length=50)
    style_tags: Optional[list[str]] = None
    city: Optional[str] = Field(None, min_length=1, max_length=80)
    location_text: Optional[str] = Field(None, max_length=255)
    location_name: Optional[str] = Field(None, max_length=120)
    location_address: Optional[str] = Field(None, max_length=255)
    location_latitude: Optional[Decimal] = Field(None, ge=-90, le=90)
    location_longitude: Optional[Decimal] = Field(None, ge=-180, le=180)
    location_place_id: Optional[str] = Field(None, max_length=160)
    location_provider: Optional[str] = Field(None, max_length=30)
    coordinate_system: Optional[str] = Field(None, pattern="^(WGS84|GCJ02)$")
    location_precision: Optional[str] = Field(None, pattern="^(exact|approximate)$")
    shoot_date_start: Optional[datetime] = None
    shoot_date_end: Optional[datetime] = None
    duration_minutes: Optional[int] = Field(None, gt=0)
    budget_min: Optional[int] = Field(None, ge=0)
    budget_max: Optional[int] = Field(None, ge=0)
    deliverables: Optional[Any] = None
    reference_images: Optional[list[str]] = None
    visibility: Optional[str] = Field(None, pattern="^(public|invite_only)$")
    expires_at: Optional[datetime] = None

    def model_post_init(self, __context: Any) -> None:
        """校验经纬度必须成对更新"""
        latitude_set = "location_latitude" in self.model_fields_set
        longitude_set = "location_longitude" in self.model_fields_set
        if latitude_set != longitude_set:
            raise ValueError("location_latitude and location_longitude must be updated together")
        if latitude_set and ((self.location_latitude is None) != (self.location_longitude is None)):
            raise ValueError("location_latitude and location_longitude must be provided together")


class ProjectCloseRequest(BaseModel):
    """关闭项目请求"""

    reason: Optional[str] = Field(None, max_length=500)


class ProjectResponse(BaseModel):
    """项目响应模型"""

    id: int
    customer_id: int
    customer_name: Optional[str] = None
    customer_avatar_url: Optional[str] = None
    title: str
    description: str
    category: str
    style_tags: Optional[list[str]] = None
    city: str
    location_text: Optional[str] = None
    location_name: Optional[str] = None
    location_address: Optional[str] = None
    location_latitude: Optional[Decimal] = None
    location_longitude: Optional[Decimal] = None
    location_place_id: Optional[str] = None
    location_provider: Optional[str] = None
    coordinate_system: Optional[str] = None
    location_precision: Optional[str] = None
    shoot_date_start: Optional[datetime] = None
    shoot_date_end: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    budget_min: Optional[int] = None
    budget_max: Optional[int] = None
    deliverables: Optional[Any] = None
    reference_images: Optional[list[str]] = None
    visibility: str
    status: str
    selected_application_id: Optional[int] = None
    converted_order_id: Optional[int] = None
    expires_at: Optional[datetime] = None
    application_count: int = 0
    my_application_id: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ProjectApplicationCreate(BaseModel):
    """摄影师投递项目申请请求"""

    proposal_text: str = Field(..., min_length=1)
    price_quote: int = Field(..., gt=0)
    package_snapshot: Optional[str] = Field(None, max_length=500)
    portfolio_refs: Optional[Any] = None
    revision_note: Optional[str] = None


class ProjectApplicationUpdate(BaseModel):
    """更新项目申请请求"""

    proposal_text: Optional[str] = Field(None, min_length=1)
    price_quote: Optional[int] = Field(None, gt=0)
    package_snapshot: Optional[str] = Field(None, max_length=500)
    portfolio_refs: Optional[Any] = None
    revision_note: Optional[str] = None


class ProjectSummary(BaseModel):
    """项目摘要模型"""

    id: int
    title: str
    category: str
    city: str
    status: str
    budget_min: Optional[int] = None
    budget_max: Optional[int] = None
    shoot_date_start: Optional[datetime] = None
    converted_order_id: Optional[int] = None


class ProjectApplicationResponse(BaseModel):
    """项目申请响应模型"""

    id: int
    project_id: int
    photographer_id: int
    photographer_name: Optional[str] = None
    photographer_avatar_url: Optional[str] = None
    photographer_city: Optional[str] = None
    photographer_equipment: Optional[str] = None
    photographer_styles: Optional[list[str]] = None
    photographer_portfolio: Optional[list[dict]] = None
    status: str
    proposal_text: str
    price_quote: int
    package_snapshot: Optional[str] = None
    portfolio_refs: Optional[Any] = None
    revision_note: Optional[str] = None
    project: Optional[ProjectSummary] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ProjectEventResponse(BaseModel):
    """项目动态事件响应"""

    id: int
    project_id: int
    application_id: Optional[int] = None
    actor_id: Optional[int] = None
    actor_role: Optional[str] = None
    event_type: str
    status: str
    note: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ProjectDetailResponse(BaseModel):
    """项目详情响应"""

    project: ProjectResponse
    applications: list[ProjectApplicationResponse] = []
    my_application: Optional[ProjectApplicationResponse] = None
    events: list[ProjectEventResponse] = []


class ProjectSelectResponse(BaseModel):
    """选中项目申请后生成订单的响应"""

    project: ProjectResponse
    application: ProjectApplicationResponse
    order: OrderResponse
