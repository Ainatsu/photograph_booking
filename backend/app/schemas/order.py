"""
订单系统相关 Schema 定义

包含订单创建、查看、交付、评价及数据统计的请求/响应模型。
"""

from pydantic import BaseModel, ConfigDict, Field
from decimal import Decimal
from typing import Any, Optional
from datetime import date, datetime


class OrderCreateRequest(BaseModel):
    """客户下单请求"""
    model_config = ConfigDict(extra="forbid")

    package_id: Optional[str] = Field(
        None,
        description="稳定套餐 ID；用户端创建固定方案订单时必填",
        example="a1b2c3d4e5f6",
    )
    photographer_id: Optional[int] = Field(
        None,
        description="目标摄影师的用户 ID",
        example=2,
    )
    package_description: Optional[str] = Field(
        None,
        description="旧内部调用兼容字段；用户端不得以此指定价格或套餐",
        example="个人写真 - ¥699/120分钟",
    )
    appointment_date: Optional[date] = Field(
        None,
        description="预约拍摄日期",
        example="2026-06-15",
    )
    appointment_time: Optional[datetime] = Field(
        None,
        description="旧客户端兼容字段；预约不再要求具体时刻",
        exclude=True,
    )
    duration_minutes: Optional[int] = Field(
        None,
        gt=0,
        description="旧内部调用兼容字段；固定套餐订单由后端读取套餐时长",
        example=120,
    )
    notes: Optional[str] = Field(
        None,
        description="客户备注（拍摄需求、特殊要求等）",
        example="希望拍一组校园风格的照片",
    )


class OrderRejectRequest(BaseModel):
    """摄影师拒绝订单请求"""
    rejection_reason: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="拒绝原因，会展示给客户",
        example="该时间段已有拍摄安排，建议重新选择下周工作日下午。",
    )


class OrderRescheduleRequest(BaseModel):
    """客户申请改期请求"""
    appointment_date: Optional[date] = Field(
        None,
        description="希望改到的新预约日期",
        example="2026-07-02",
    )
    appointment_time: Optional[datetime] = Field(
        None,
        description="旧客户端兼容字段；改期不再要求具体时刻",
        exclude=True,
    )
    reason: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="改期原因，会展示给对方确认",
        example="临时有工作安排，希望调整到第二天下午。",
    )


class OrderRescheduleResponseRequest(BaseModel):
    """接受或拒绝改期请求。"""
    response_note: Optional[str] = Field(
        None,
        max_length=500,
        description="响应备注",
        example="该时间可以安排。",
    )


class OrderRescheduleCounterRequest(BaseModel):
    """对改期请求提出新的候选时间。"""
    appointment_date: Optional[date] = Field(None, description="反提的新预约日期")
    appointment_time: Optional[datetime] = Field(
        None,
        description="旧客户端兼容字段；反提不再要求具体时刻",
        exclude=True,
    )
    reason: str = Field(..., min_length=1, max_length=500, description="反提原因")


class OrderRescheduleRequestResponse(BaseModel):
    """改期请求记录响应"""

    id: int
    order_id: int
    requested_by: int
    original_appointment_time: datetime
    requested_appointment_time: datetime
    reason: str
    status: str
    response_note: Optional[str] = None
    expires_at: datetime
    created_at: datetime
    resolved_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class OrderCancelRequest(BaseModel):
    """订单取消请求"""
    cancel_reason: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="取消原因，会展示给对方",
        example="行程变化，无法按原时间拍摄。",
    )


class OrderRevisionAcknowledgeRequest(BaseModel):
    """摄影师确认返修请求"""

    expected_redelivery_at: datetime = Field(..., description="摄影师预计重新交付时间")


class OrderResponse(BaseModel):
    """订单响应"""
    id: int = Field(..., description="订单唯一 ID", example=1001)
    customer_id: int = Field(..., description="下单客户 ID", example=1)
    photographer_id: int = Field(..., description="接单摄影师 ID", example=2)
    package_snapshot: str = Field(
        ...,
        description="下单时的方案快照",
        example="个人写真 - ¥699/120分钟",
    )
    source_type: str = Field("legacy", description="订单来源：package / project / legacy")
    source_id: Optional[str] = None
    source_application_id: Optional[int] = None
    payment_status: str = Field("unpaid", description="支付状态")
    after_sales_status: str = Field("none", description="售后状态")
    payment_due_at: Optional[datetime] = None
    deposit_rate: Decimal = Decimal("0.3000")
    escrow_amount: Decimal = Decimal("0.00")
    refunded_amount: Decimal = Decimal("0.00")
    settled_amount: Decimal = Decimal("0.00")
    acceptance_deadline_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    completion_type: Optional[str] = None
    revision_used_count: int = 0
    action_required_by: Optional[str] = None
    action_deadline_at: Optional[datetime] = None
    next_action_code: Optional[str] = None
    auto_action_code: Optional[str] = None
    last_reminded_at: Optional[datetime] = None
    reminder_count: int = 0
    overdue_at: Optional[datetime] = None
    package_id: Optional[str] = None
    package_name: Optional[str] = None
    package_description: Optional[str] = None
    package_price: Optional[Decimal] = None
    final_price: Optional[Decimal] = None
    currency: str = Field("CNY", description="固定为人民币 CNY")
    service_location: Optional[str] = None
    delivery_due_at: Optional[datetime] = None
    original_image_count: Optional[int] = None
    retouched_image_count: Optional[int] = None
    delivery_formats: Optional[list[str]] = None
    included_revision_count: Optional[int] = None
    commercial_license: bool = False
    copyright_terms: Optional[str] = None
    cancellation_policy_snapshot: Optional[Any] = None
    reschedule_policy_snapshot: Optional[Any] = None
    deliverables: Optional[Any] = None
    payment_mode: str = "full"
    fulfillment_mode: str = "single_delivery"
    contract_snapshot: Optional[dict] = None
    appointment_time: datetime = Field(
        ...,
        description="预约拍摄时间",
        example="2026-06-15T14:00:00",
    )
    duration_minutes: int = Field(..., description="服务时长（分钟）", example=120)
    notes: Optional[str] = Field(
        None,
        description="客户备注",
        example="希望拍一组校园风格的照片",
    )
    rejection_reason: Optional[str] = Field(
        None,
        description="摄影师拒绝订单时填写的原因",
        example="该时间段已有拍摄安排，建议重新选择下周工作日下午。",
    )
    reschedule_requested_time: Optional[datetime] = Field(
        None,
        description="客户申请改期时填写的新预约时间，待摄影师确认后生效",
        example="2026-07-02T15:00:00",
    )
    reschedule_reason: Optional[str] = Field(
        None,
        description="客户申请改期的原因",
        example="临时有工作安排，希望调整到第二天下午。",
    )
    active_reschedule_request: Optional[OrderRescheduleRequestResponse] = Field(
        None,
        description="当前待处理的独立改期请求；订单主状态保持不变",
    )
    cancellation_reason: Optional[str] = Field(
        None,
        description="订单取消原因",
        example="行程变化，无法按原时间拍摄。",
    )
    cancelled_by: Optional[str] = Field(
        None,
        description="取消方：customer（客户）/ photographer（摄影师）/ admin（管理员）",
        example="customer",
    )
    status: str = Field(
        ...,
        description="订单状态：pending（待确认）/ awaiting_customer_payment（待支付）/ confirmed（已确认）/ in_progress（履约中）/ delivered（待验收或返修）/ completed（已完成）/ cancelled（已取消）；received/reviewed 仅用于历史兼容",
        example="confirmed",
    )
    delivery: Optional[dict] = Field(
        None,
        description="交付内容（含作品图片链接和描述）",
        example={"images": ["/static/deliveries/photo1.jpg"], "description": "精修 30 张"},
    )
    rating: Optional[int] = Field(None, description="客户评分（1-10）", example=9)
    review_text: Optional[str] = Field(
        None,
        description="客户评价内容",
        example="非常专业，超出预期！",
    )
    customer_name: Optional[str] = Field(
        None,
        description="下单客户昵称",
        example="测试客户",
    )
    customer_avatar_url: Optional[str] = Field(
        None,
        description="下单客户头像",
        example="/static/avatars/customer.jpg",
    )
    photographer_name: Optional[str] = Field(
        None,
        description="摄影师昵称",
        example="摄影师张三",
    )
    photographer_avatar_url: Optional[str] = Field(
        None,
        description="摄影师头像",
        example="/static/avatars/photographer.jpg",
    )
    created_at: datetime = Field(
        ...,
        description="订单创建时间",
        example="2026-06-09T10:30:00",
    )
    updated_at: Optional[datetime] = Field(
        None,
        description="最后更新时间",
        example="2026-06-09T12:00:00",
    )

    class Config:
        from_attributes = True


class OrderHistoryItem(BaseModel):
    """订单历史事件"""
    id: Optional[int] = Field(None, description="历史事件 ID")
    event_type: str = Field(..., description="事件类型", example="confirmed")
    status: str = Field(..., description="事件发生后的订单状态", example="confirmed")
    actor_id: Optional[int] = Field(None, description="操作者用户 ID")
    actor_role: Optional[str] = Field(None, description="操作者角色", example="photographer")
    actor_name: Optional[str] = Field(None, description="操作者显示名称")
    note: Optional[str] = Field(None, description="事件说明")
    created_at: datetime = Field(..., description="事件时间")


class OrderDeliveryFileResponse(BaseModel):
    """交付文件响应"""

    id: int
    file_url: str
    file_name: str
    file_type: Optional[str] = None
    file_size: Optional[int] = None
    checksum: Optional[str] = None
    created_at: datetime


class OrderDeliveryResponse(BaseModel):
    """交付记录响应"""

    id: int
    order_id: int
    version: int
    submitted_by: int
    description: Optional[str] = None
    file_count: int
    status: str
    acceptance_deadline_at: Optional[datetime] = None
    accepted_at: Optional[datetime] = None
    created_at: datetime
    files: list[OrderDeliveryFileResponse] = Field(default_factory=list)


class OrderRevisionRequestResponse(BaseModel):
    """返修请求记录响应"""

    id: int
    order_id: int
    delivery_id: int
    sequence: int
    requested_by: int
    instructions: str
    reference_files: list[dict] = Field(default_factory=list)
    counts_as_free: bool
    status: str
    response_due_at: datetime
    expected_redelivery_at: Optional[datetime] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None


class OrderDetailResponse(BaseModel):
    """订单详情响应"""
    order: OrderResponse
    history: list[OrderHistoryItem]
    reschedule_requests: list[OrderRescheduleRequestResponse] = Field(default_factory=list)
    deliveries: list[OrderDeliveryResponse] = Field(default_factory=list)
    revision_requests: list[OrderRevisionRequestResponse] = Field(default_factory=list)
    disputes: list[Any] = Field(default_factory=list)


class ReviewCreateRequest(BaseModel):
    """客户评价请求"""
    rating: int = Field(
        ...,
        ge=1,
        le=10,
        description="评分（1-10 分）",
        example=9,
    )
    review_text: Optional[str] = Field(
        None,
        description="评价文字内容",
        example="非常专业，超出预期！",
    )


class PhotographerStatsResponse(BaseModel):
    """摄影师数据统计响应"""
    monthly_orders: int = Field(
        ...,
        description="本月接单数",
        example=12,
    )
    weekly_orders: int = Field(
        ...,
        description="本周接单数",
        example=3,
    )
    completion_rate: float = Field(
        ...,
        description="订单完成率（百分比，如 85.5 表示 85.5%）",
        example=85.5,
    )
    avg_rating: float = Field(
        ...,
        description="客户平均评分（5 分制）",
        example=4.6,
    )
