"""摄影师仪表盘响应模型。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PhotographerDashboardPeriod(BaseModel):
    """当前统计时间范围。"""

    range_key: str = Field(..., description="时间范围标识")
    label: str = Field(..., description="时间范围展示名称")
    current_start: Optional[datetime] = Field(None, description="当前周期开始时间")
    current_end: Optional[datetime] = Field(None, description="当前周期结束时间")
    previous_start: Optional[datetime] = Field(None, description="上一周期开始时间")
    previous_end: Optional[datetime] = Field(None, description="上一周期结束时间")
    has_comparison: bool = Field(..., description="是否存在可比较的上一周期数据")


class PhotographerDashboardSummary(BaseModel):
    """顶部摘要指标。"""

    monthly_orders: int = Field(..., description="本月接单数")
    weekly_orders: int = Field(..., description="本周接单数")
    period_orders: int = Field(..., description="当前时间范围内的非取消订单数")
    confirmed_shoots: int = Field(..., description="当前时间范围内的已确认拍摄数")
    completion_rate: float = Field(..., description="订单完成率百分比")
    avg_rating: float = Field(..., description="客户平均评分（5 分制）")


class PhotographerDashboardTrends(BaseModel):
    """相较上一周期的变化。"""

    has_comparison: bool = Field(..., description="是否存在可比较的上一周期数据")
    period_orders_delta: Optional[int] = Field(None, description="接单数变化")
    confirmed_shoots_delta: Optional[int] = Field(None, description="已确认拍摄数变化")
    completion_rate_delta: Optional[float] = Field(None, description="完成率变化")
    avg_rating_delta: Optional[float] = Field(None, description="平均评分变化")


class PhotographerDashboardRevenue(BaseModel):
    """收入指标。"""

    available: bool = Field(..., description="是否可展示收入指标")
    reason: Optional[str] = Field(None, description="不可用原因")
    month_estimated: Optional[float] = Field(None, description="本月预估收入")
    completed: Optional[float] = Field(None, description="已完成收入")
    pending: Optional[float] = Field(None, description="待确认收入")
    average_order_value: Optional[float] = Field(None, description="平均客单价")


class PhotographerDashboardContent(BaseModel):
    """内容健康度。"""

    portfolio_count: int = Field(..., description="作品数量")
    package_count: int = Field(..., description="套餐数量")
    packages_with_samples: int = Field(..., description="带示例图的套餐数量")
    recent_upload_count: int = Field(..., description="近 30 天上传作品数量")


class PhotographerDashboardTopWork(BaseModel):
    """热门作品。"""

    id: str = Field(..., description="作品 ID")
    title: str = Field(..., description="作品标题")
    url: str = Field(..., description="作品地址")
    thumbnail_url: str = Field("", description="缩略图地址")
    media_type: str = Field("image", description="媒体类型")
    tags: list[str] = Field(default_factory=list, description="风格标签")
    like_count: int = Field(..., description="点赞数")
    favorite_count: int = Field(..., description="收藏数")
    total_interactions: int = Field(..., description="点赞与收藏合计")


class PhotographerDashboardTopPackage(BaseModel):
    """热门套餐。"""

    id: str = Field(..., description="套餐 ID")
    name: str = Field(..., description="套餐名称")
    price: Optional[float] = Field(None, description="套餐价格")
    duration: Optional[int] = Field(None, description="服务时长")
    sample_url: str = Field("", description="套餐示例图")
    favorite_count: int = Field(..., description="收藏数")
    booking_count: Optional[int] = Field(None, description="预约数，缺少稳定套餐来源时为空")
    booking_count_available: bool = Field(..., description="是否可按套餐统计预约数")


class PhotographerDashboardTodo(BaseModel):
    """待处理事项计数。"""

    pending_orders: int = Field(..., description="待确认预约数")
    reschedule_requests: int = Field(..., description="待处理改期数")
    orders_to_deliver: int = Field(..., description="待交付订单数")
    orders_waiting_review: int = Field(..., description="待客户评价订单数")


class PhotographerDashboardOrderItem(BaseModel):
    """仪表盘中的轻量订单项。"""

    id: int = Field(..., description="订单 ID")
    package_snapshot: str = Field(..., description="方案快照")
    appointment_time: datetime = Field(..., description="预约拍摄时间")
    duration_minutes: int = Field(..., description="服务时长（分钟）")
    status: str = Field(..., description="订单状态")
    customer_id: int = Field(..., description="客户 ID")
    customer_name: Optional[str] = Field(None, description="客户昵称")
    customer_avatar_url: Optional[str] = Field(None, description="客户头像")
    reschedule_requested_time: Optional[datetime] = Field(None, description="客户申请改期时间")


class PhotographerDashboardSchedule(BaseModel):
    """近期日程。"""

    today_orders: int = Field(..., description="今日已确认拍摄数")
    week_confirmed_orders: int = Field(..., description="本周已确认拍摄数")
    next_order: Optional[PhotographerDashboardOrderItem] = Field(None, description="下一场已确认拍摄")
    upcoming_orders: list[PhotographerDashboardOrderItem] = Field(
        default_factory=list,
        description="最近 3 个未取消预约",
    )


class PhotographerDashboardInteractions(BaseModel):
    """客户互动指标。"""

    new_followers: int = Field(..., description="当前时间范围内新增粉丝数")
    message_conversations: int = Field(..., description="当前时间范围内发生过私信的会话数")
    work_likes: int = Field(..., description="当前时间范围内作品点赞数")
    work_favorites: int = Field(..., description="当前时间范围内作品收藏数")
    package_favorites: int = Field(..., description="当前时间范围内套餐收藏数")
    profile_views: int = Field(..., description="当前时间范围内主页访问事件数")
    portfolio_views: int = Field(..., description="当前时间范围内作品曝光或访问事件数")
    package_views: int = Field(..., description="当前时间范围内套餐曝光或详情访问事件数")


class PhotographerDashboardFunnelNode(BaseModel):
    """转化漏斗节点。"""

    key: str = Field(..., description="漏斗节点标识")
    label: str = Field(..., description="漏斗节点名称")
    count: int = Field(..., description="节点数量")
    conversion_rate: Optional[float] = Field(None, description="相对上一步的转化率")
    source: str = Field(..., description="统计数据来源说明")


class PhotographerDashboardFunnel(BaseModel):
    """客户从访问到预约的转化路径。"""

    nodes: list[PhotographerDashboardFunnelNode] = Field(default_factory=list)
    tracked_event_count: int = Field(..., description="当前范围内 analytics 事件数")


class PhotographerDashboardProjectPerformance(BaseModel):
    """企划应邀表现。"""

    submitted_applications: int = Field(..., description="当前范围内提交的企划应邀数")
    selected_applications: int = Field(..., description="当前范围内被选中的企划应邀数")
    converted_orders: int = Field(..., description="当前范围内由企划转化的订单数")
    application_conversion_rate: Optional[float] = Field(None, description="应邀被选中率")
    average_quote: Optional[float] = Field(None, description="平均报价")
    budget_match_rate: Optional[float] = Field(None, description="报价落在客户预算范围内的比例")
    budget_match_sample_count: int = Field(..., description="可计算预算匹配的样本数")


class PhotographerPublicDashboardTrust(BaseModel):
    """公开展示的服务可信度指标。"""

    completed_orders: int = Field(..., description="已完成服务数")
    avg_rating: Optional[float] = Field(None, description="客户平均评分（5 分制），无评价时为空")
    rating_count: int = Field(..., description="评价样本数")
    rating_visible: bool = Field(..., description="是否可展示平均评分")
    completion_rate: Optional[float] = Field(None, description="完成率百分比，样本不足时为空")
    completion_rate_visible: bool = Field(..., description="是否可展示完成率")
    completion_sample_count: int = Field(..., description="完成率统计样本数")
    recent_order_activity: bool = Field(..., description="近 90 天是否有非取消订单")


class PhotographerDashboardResponse(BaseModel):
    """摄影师仪表盘聚合响应。"""

    period: PhotographerDashboardPeriod
    summary: PhotographerDashboardSummary
    trends: PhotographerDashboardTrends
    revenue: PhotographerDashboardRevenue
    content: PhotographerDashboardContent
    top_works: list[PhotographerDashboardTopWork] = Field(default_factory=list)
    top_packages: list[PhotographerDashboardTopPackage] = Field(default_factory=list)
    todo: PhotographerDashboardTodo
    schedule: PhotographerDashboardSchedule
    interactions: PhotographerDashboardInteractions
    funnel: PhotographerDashboardFunnel
    project_performance: PhotographerDashboardProjectPerformance


class PhotographerPublicDashboardResponse(BaseModel):
    """其它用户可查看的摄影师公开仪表盘。"""

    trust: PhotographerPublicDashboardTrust
    content: PhotographerDashboardContent
    top_works: list[PhotographerDashboardTopWork] = Field(default_factory=list)
    top_packages: list[PhotographerDashboardTopPackage] = Field(default_factory=list)
