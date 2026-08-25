"""
管理后台相关 Schema 定义

包含管理员登录、仪表盘统计、用户管理和订单管理的请求/响应模型。
"""

from pydantic import BaseModel, Field
from typing import Optional
from decimal import Decimal
from datetime import datetime


class AdminLoginRequest(BaseModel):
    """管理员登录请求"""
    email: str = Field(
        ...,
        description="管理员邮箱",
        example="admin@example.com",
    )
    password: str = Field(
        ...,
        description="管理员密码",
        example="Admin123456",
    )


class AdminTokenResponse(BaseModel):
    """管理员登录令牌响应"""
    access_token: str = Field(
        ...,
        description="JWT 管理员访问令牌",
        example="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    )
    token_type: str = Field(
        default="bearer",
        description="令牌类型，固定为 bearer",
        example="bearer",
    )


class DashboardStats(BaseModel):
    """管理后台仪表盘统计数据"""
    total_users: int = Field(
        ...,
        description="平台总用户数",
        example=150,
    )
    total_photographers: int = Field(
        ...,
        description="摄影师数量",
        example=45,
    )
    total_customers: int = Field(
        ...,
        description="客户数量",
        example=105,
    )
    total_orders: int = Field(
        ...,
        description="平台总订单数",
        example=320,
    )
    pending_orders: int = Field(
        ...,
        description="待处理订单数",
        example=12,
    )
    today_orders: int = Field(
        ...,
        description="今日新增订单数",
        example=5,
    )


class AdminUserItem(BaseModel):
    """管理后台用户列表项"""
    id: int = Field(..., description="用户唯一 ID", example=1)
    email: str = Field(..., description="邮箱地址", example="user@example.com")
    display_name: str = Field(..., description="显示名称", example="摄影师小王")
    role: str = Field(..., description="用户角色", example="photographer")
    is_active: bool = Field(..., description="账号是否激活", example=True)
    is_banned: bool = Field(..., description="是否被封禁", example=False)
    created_at: datetime = Field(
        ...,
        description="注册时间",
        example="2026-01-15T10:00:00",
    )

    class Config:
        from_attributes = True


class AdminOrderItem(BaseModel):
    """管理后台订单列表项"""
    id: int = Field(..., description="订单唯一 ID", example=1001)
    customer_id: int = Field(..., description="客户 ID", example=1)
    photographer_id: int = Field(..., description="摄影师 ID", example=2)
    package_snapshot: str = Field(
        ...,
        description="方案快照",
        example="个人写真 - ¥699/120分钟",
    )
    appointment_time: datetime = Field(
        ...,
        description="预约拍摄时间",
        example="2026-06-15T14:00:00",
    )
    status: str = Field(
        ...,
        description="订单状态",
        example="confirmed",
    )
    rating: Optional[int] = Field(None, description="客户评分（1-10）", example=9)
    source_type: str = "legacy"
    final_price: Optional[Decimal] = None
    currency: str = "CNY"
    payment_status: str = "unpaid"
    cancellation_reason: Optional[str] = Field(None, description="订单取消原因")
    cancelled_by: Optional[str] = Field(None, description="取消方")
    created_at: datetime = Field(
        ...,
        description="订单创建时间",
        example="2026-06-09T10:30:00",
    )

    class Config:
        from_attributes = True


class AdminOrderCancelRequest(BaseModel):
    """管理员取消订单请求。"""
    reason: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="管理员取消原因，会展示给订单双方并写入审计事件",
    )


class AdminPhotographerApplicationItem(BaseModel):
    """管理后台摄影师申请列表项"""
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


class AdminPhotographerApplicationReview(BaseModel):
    """管理后台摄影师申请审核请求"""
    review_note: Optional[str] = Field(None, description="审核备注")
