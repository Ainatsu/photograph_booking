"""
摄影师资料相关 Schema 定义

包含摄影师个人资料、套餐方案、作品集的请求/响应模型。
"""

from pydantic import BaseModel, Field, model_validator
from typing import Optional
from datetime import date, datetime


class PackageSchema(BaseModel):
    """摄影套餐方案"""
    id: Optional[str] = Field(
        None,
        description="套餐唯一标识",
        example="a1b2c3d4e5f6",
    )
    name: str = Field(
        ...,
        description="套餐名称",
        example="个人写真",
    )
    price: float = Field(
        ...,
        ge=0,
        description="套餐价格（元）",
        example=699.00,
    )
    duration: int = Field(
        ...,
        gt=0,
        description="拍摄时长（分钟）",
        example=120,
    )
    description: Optional[str] = Field(
        None,
        description="套餐详细描述",
        example="包含 2 套服装，精修 30 张，底片全送",
    )
    includes: Optional[list[str]] = Field(
        None,
        description="套餐包含的服务项",
        example=["2套服装", "精修30张", "底片全送", "1个外景"],
    )
    styles: Optional[list[str]] = Field(
        None,
        description="风格领域标签",
        example=["日系", "复古", "清新", "校园"],
    )
    image_count: Optional[int] = Field(
        None,
        description="精修照片数量",
        example=30,
    )
    city: Optional[str] = Field(
        None,
        description="套餐所在城市，空字符串或 None 表示不限制城市",
        example="北京",
    )
    samples: Optional[list[str]] = Field(
        None,
        description="样片图片 URL 列表",
        example=["/static/package_samples/sample1.jpg"],
    )
    sample_thumbnails: Optional[list[str]] = Field(
        None,
        description="样片预览图 URL 列表",
        example=["/static/package_samples/thumbnails/sample1_thumb.jpg"],
    )
    is_active: bool = Field(True, description="套餐是否可预约")
    service_location: Optional[str] = Field(None, description="具体服务地点或范围")
    service_city: Optional[str] = Field(None, max_length=80)
    service_address: Optional[str] = Field(None, max_length=255)
    service_latitude: Optional[float] = Field(None, ge=-90, le=90)
    service_longitude: Optional[float] = Field(None, ge=-180, le=180)
    service_radius_km: Optional[int] = Field(None, ge=1, le=500)
    original_image_count: Optional[int] = Field(None, ge=0, description="交付原片数量")
    retouched_image_count: Optional[int] = Field(None, ge=0, description="交付精修数量")
    delivery_formats: list[str] = Field(default_factory=lambda: ["JPG"], description="交付格式")
    included_revision_count: int = Field(0, ge=0, description="包含的免费修改次数")
    delivery_days: int = Field(7, ge=0, description="拍摄后多少天交付")
    commercial_license: bool = Field(False, description="是否包含商业使用授权")
    terms_rules: Optional[str] = Field(None, description="版权、取消和改期等合并条款规则")
    copyright_terms: Optional[str] = Field(None, description="版权和使用权约定")
    cancellation_policy: Optional[dict | str] = Field(None, description="取消政策")
    reschedule_policy: Optional[dict | str] = Field(None, description="改期政策")
    payment_mode: str = Field("full", pattern="^(full|deposit_balance)$")
    deposit_rate: float = Field(0.30, gt=0, le=1, description="定金比例，仅定金加尾款模式使用")
    fulfillment_mode: str = Field("single_delivery", pattern="^single_delivery$")


class PortfolioItemSchema(BaseModel):
    """作品集单项"""

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_tags(cls, value):
        """兼容旧作品数据中的 styles 字段和缺失的 tag 字段。"""
        if not isinstance(value, dict):
            return value

        normalized = dict(value)
        tags = normalized.get("tags")
        if not tags and isinstance(normalized.get("styles"), list):
            tags = [str(tag).strip() for tag in normalized["styles"] if str(tag).strip()]
            normalized["tags"] = tags

        if not normalized.get("tag"):
            normalized["tag"] = tags[0] if tags else ""
        return normalized

    id: Optional[str] = Field(
        None,
        description="作品唯一标识",
        example="a1b2c3d4e5f6",
    )
    url: str = Field(
        ...,
        description="作品图片 URL",
        example="/static/portfolio/photo_001.jpg",
    )
    thumbnail_url: Optional[str] = Field(
        None,
        description="作品预览图 URL",
        example="/static/portfolio/thumbnails/photo_001_thumb.jpg",
    )
    tag: str = Field(
        ...,
        description="作品标签（如'婚纱'、'写真'、'商业'等）",
        example="写真",
    )
    tags: Optional[list[str]] = Field(
        None,
        description="作品风格标签",
        example=["日系", "复古"],
    )
    title: Optional[str] = Field(
        None,
        description="作品标题",
        example="春日校园写真",
    )
    description: Optional[str] = Field(
        None,
        description="作品描述",
        example="自然光拍摄，日系清新风格",
    )


class PortfolioItemUpdate(BaseModel):
    """作品标题、标签和说明更新请求。"""

    title: str = Field("", max_length=120, description="作品标题")
    tags: list[str] = Field(default_factory=list, max_length=12, description="作品风格标签")
    description: str = Field("", max_length=1200, description="作品描述")


class PhotographerProfileCreate(BaseModel):
    """创建 / 更新摄影师资料请求"""
    cover_image_url: Optional[str] = Field(
        None,
        description="主页封面图 URL",
        example="/static/covers/cover_1.jpg",
    )
    location: Optional[str] = Field(
        None,
        description="所在城市 / 地区",
        example="上海市浦东新区",
    )
    service_city: Optional[str] = Field(None, max_length=80)
    service_address: Optional[str] = Field(None, max_length=255)
    service_latitude: Optional[float] = Field(None, ge=-90, le=90)
    service_longitude: Optional[float] = Field(None, ge=-180, le=180)
    service_radius_km: Optional[int] = Field(None, ge=1, le=500)
    location_source: Optional[str] = Field(None, max_length=30)
    styles: Optional[list[str]] = Field(
        None,
        description="风格领域标签",
        example=["日系", "复古", "清新", "婚礼摄影", "人像写真"],
    )
    equipment: Optional[str] = Field(
        None,
        description="使用器材描述",
        example="Sony A7M4 + 24-70mm F2.8 GM II",
    )
    packages: Optional[list[PackageSchema]] = Field(
        None,
        description="摄影套餐列表",
    )
    availability_exceptions: Optional[list[dict]] = Field(
        None,
        description="每日档期设置，默认空闲，仅需标记忙碌日期；可附带当天所在地",
        example=[{"date": "2026-07-01", "status": "busy", "location": "香港中环"}],
    )
    advance_notice: Optional[int] = Field(
        None,
        description="最少提前预约天数",
        example=3,
    )
    max_daily_bookings: Optional[int] = Field(
        None,
        description="每日最大接单量",
        example=3,
    )
    max_booking_date: Optional[date] = Field(None, description="最远可预约日期")


class PhotographerProfileResponse(BaseModel):
    """摄影师资料响应"""
    id: int = Field(..., description="资料 ID", example=1)
    user_id: int = Field(..., description="关联的用户 ID", example=2)
    user_role: Optional[str] = Field(
        None,
        description="用户角色（photographer/client）",
        example="photographer",
    )
    user_display_name: Optional[str] = Field(
        None,
        description="用户显示名称",
        example="摄影师小王",
    )
    user_avatar_url: Optional[str] = Field(
        None,
        description="用户头像 URL",
        example="/static/avatars/user_2.jpg",
    )
    user_bio: Optional[str] = Field(
        None,
        description="用户个人简介",
        example="擅长人像摄影，5 年经验",
    )
    public_email: Optional[str] = Field(None, description="用户主动公开且已验证的邮箱")
    background_url: Optional[str] = Field(
        None,
        description="个人主页背景图 URL",
        example="/static/backgrounds/user_1_bg.jpg",
    )
    cover_image_url: Optional[str] = Field(
        None,
        description="主页封面图 URL",
        example="/static/covers/cover_1.jpg",
    )
    location: Optional[str] = Field(
        None,
        description="所在城市 / 地区",
        example="上海市浦东新区",
    )
    service_city: Optional[str] = None
    service_address: Optional[str] = None
    service_latitude: Optional[float] = None
    service_longitude: Optional[float] = None
    service_radius_km: Optional[int] = None
    location_source: Optional[str] = None
    styles: Optional[list[str]] = Field(
        None,
        description="风格领域标签（合并原风格标签和擅长领域）",
        example=["日系", "复古", "清新", "婚礼摄影", "人像写真"],
    )
    equipment: Optional[str] = Field(
        None,
        description="使用器材描述",
        example="Sony A7M4 + 24-70mm F2.8 GM II",
    )
    packages: Optional[list[PackageSchema]] = Field(
        None,
        description="摄影套餐列表",
    )
    availability_exceptions: Optional[list[dict]] = Field(
        None,
        description="每日档期设置，默认空闲，仅需标记忙碌日期；可附带当天所在地",
        example=[{"date": "2026-07-01", "status": "busy", "location": "香港中环"}],
    )
    advance_notice: Optional[int] = Field(
        None,
        description="最少提前预约天数",
        example=3,
    )
    max_daily_bookings: Optional[int] = Field(
        None,
        description="每日最大接单量",
        example=3,
    )
    max_booking_date: Optional[date] = Field(None, description="最远可预约日期")
    portfolio: Optional[list[PortfolioItemSchema]] = Field(
        None,
        description="作品集列表",
    )
    avg_rating: Optional[float] = Field(
        None,
        description="客户平均评分（5 分制）",
        example=4.6,
    )
    follower_count: int = Field(
        default=0,
        description="粉丝数",
        example=0,
    )
    following_count: int = Field(
        default=0,
        description="关注数",
        example=0,
    )
    created_at: datetime = Field(
        ...,
        description="资料创建时间",
        example="2026-01-01T00:00:00",
    )
    updated_at: Optional[datetime] = Field(
        None,
        description="资料最后更新时间",
        example="2026-06-09T10:00:00",
    )

    class Config:
        from_attributes = True
