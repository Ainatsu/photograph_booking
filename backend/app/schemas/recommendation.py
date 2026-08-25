"""推荐相关 Schema 定义"""

from typing import Any, Literal
from datetime import date
from pydantic import BaseModel, Field, field_validator, model_validator
from backend.app.schemas.project import ProjectResponse

class RecommendationWorkItem(BaseModel):
    """推荐作品条目"""

    id: str
    title: str = ""
    tags: list[str] = Field(default_factory=list)
    photographer_id: int
    recommendation_reason: str
    candidate_source: str
    url: str = ""
    images: list[str] = Field(default_factory=list)
    media_type: str = "image"
    thumbnail_url: str = ""
    thumbnail_urls: list[str] = Field(default_factory=list)
    compressed_url: str = ""
    duration: float | None = None
    compressed_duration: float | None = None
    tag: str = ""
    description: str = ""
    user_id: int
    user_display_name: str | None = None
    user_avatar_url: str | None = None

class RecommendationWorksResponse(BaseModel):
    """作品推荐结果响应"""

    recommendation_id: str
    algorithm_version: str
    next_cursor: str | None = None
    items: list[RecommendationWorkItem]

class RecommendationPackageItem(BaseModel):
    """推荐套餐条目"""

    id: str
    package_name: str
    price: float
    duration: int = 0
    image_count: int = 0
    description: str = ""
    includes: list[str] = Field(default_factory=list)
    styles: list[str] = Field(default_factory=list)
    city: str = ""
    samples: list[str] = Field(default_factory=list)
    sample_thumbnails: list[str] = Field(default_factory=list)
    photographer_id: int
    photographer_name: str | None = None
    photographer_avatar: str | None = None
    photographer_location: str | None = None
    recommendation_reason: str
    candidate_source: str
    distance_km: float | None = None
    distance_label: str = "同城，距离未知"
    distance_confidence: str = "unknown"
    availability: dict[str, Any] | None = None
    match: dict[str, float] = Field(default_factory=dict)
    recommendation_reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

class RecommendationPackagesResponse(BaseModel):
    """套餐推荐结果响应"""

    recommendation_id: str
    algorithm_version: str
    next_cursor: str | None = None
    fallback_level: int = 0
    relaxations: list[dict[str, Any]] = Field(default_factory=list)
    no_result: bool = False
    feature_enabled: bool = True
    observability: dict[str, Any] = Field(default_factory=dict)
    items: list[RecommendationPackageItem]


class PackageRecommendationQuery(BaseModel):
    """套餐推荐查询参数"""

    city: str | None = None
    styles: list[str] = Field(default_factory=list)
    budget_min: float | None = Field(None, ge=0)
    budget_max: float | None = Field(None, ge=0)
    budget_strict: bool = False
    date_strict: bool = False
    shoot_date: date | None = None
    time_start: str | None = None
    time_end: str | None = None
    duration_minutes: int | None = Field(None, gt=0)
    location_text: str | None = None
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)
    max_distance_km: float | None = Field(None, ge=0)
    require_exact_availability: bool = False
    sort_mode: Literal["best_match", "nearest", "lowest_price", "earliest_available"] = "best_match"

    @model_validator(mode="after")
    def validate_pairs(self):
        """校验时间、经纬度、预算等成对参数是否合法"""
        if (self.time_start is None) != (self.time_end is None):
            raise ValueError("time_start 和 time_end 必须同时提供")
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude 和 longitude 必须同时提供")
        if self.budget_min is not None and self.budget_max is not None and self.budget_min > self.budget_max:
            raise ValueError("budget_min 不能大于 budget_max")
        for value in (self.time_start, self.time_end):
            if value is None:
                continue
            try:
                hour, minute = (int(part) for part in value.split(":"))
            except (TypeError, ValueError):
                raise ValueError("时间必须使用 HH:MM 格式")
            if not 0 <= hour <= 23 or not 0 <= minute <= 59:
                raise ValueError("时间必须使用 HH:MM 格式")
        if self.time_start and self.time_end:
            start = tuple(int(part) for part in self.time_start.split(":"))
            end = tuple(int(part) for part in self.time_end.split(":"))
            if start >= end:
                raise ValueError("time_end 必须晚于 time_start")
        return self

class RecommendationProjectItem(ProjectResponse):
    """推荐项目条目"""

    match_reason: str
    candidate_source: str

class RecommendationProjectsResponse(BaseModel):
    """项目推荐结果响应"""

    recommendation_id: str
    algorithm_version: str
    next_cursor: str | None = None
    items: list[RecommendationProjectItem]

class RecommendationEventCreate(BaseModel):
    """推荐曝光事件上报"""

    event_type: str = Field(min_length=1, max_length=60)
    target_type: str = Field(default="portfolio", max_length=30)
    target_id: str = Field(min_length=1, max_length=80)
    owner_user_id: int | None = None
    recommendation_id: str | None = Field(default=None, max_length=50)
    request_id: str | None = Field(default=None, max_length=50)
    session_id: str | None = Field(default=None, max_length=100)
    scene: str | None = Field(default=None, max_length=40)
    position: int | None = Field(default=None, ge=0)
    algorithm_version: str | None = Field(default=None, max_length=40)
    candidate_source: str | None = Field(default=None, max_length=40)
    metadata: dict[str, Any] | None = None

    @field_validator("target_id", mode="before")
    @classmethod
    def _stringify_target_id(cls, value: Any) -> Any:
        """企划、订单等实体主键是整数，统一转成字符串以匹配存储列类型。"""
        return str(value) if isinstance(value, int) and not isinstance(value, bool) else value

class RecommendationEventBatchCreate(BaseModel):
    """批量上报推荐事件"""

    events: list[RecommendationEventCreate] = Field(min_length=1, max_length=100)

class RecommendationEventBatchResponse(BaseModel):
    """批量上报结果统计"""

    accepted: int
    deduplicated: int
