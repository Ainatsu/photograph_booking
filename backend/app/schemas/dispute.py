"""订单纠纷相关 Schema 定义"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, Field


class OrderDisputeEvidenceResponse(BaseModel):
    """纠纷证据响应"""

    id: int
    dispute_id: int
    submitted_by: int
    submitter_role: str
    submitter_name: Optional[str] = None
    description: Optional[str] = None
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    file_type: Optional[str] = None
    file_size: Optional[int] = None
    checksum: Optional[str] = None
    reference_type: Optional[str] = None
    reference_id: Optional[str] = None
    created_at: datetime


class OrderDisputeResponse(BaseModel):
    """订单纠纷响应"""

    id: int
    dispute_no: str
    order_id: int
    opened_by: int
    opened_by_role: str
    opener_name: Optional[str] = None
    reason_code: str
    description: str
    requested_resolution: str
    status: str
    assigned_admin_id: Optional[int] = None
    assigned_admin_name: Optional[str] = None
    resolution: Optional[str] = None
    resolution_note: Optional[str] = None
    refund_amount: Decimal = Decimal("0.00")
    currency: str = "CNY"
    available_escrow_amount: Decimal = Decimal("0.00")
    evidence: list[OrderDisputeEvidenceResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None


class AdminDisputeAssignRequest(BaseModel):
    """管理员分配纠纷处理请求"""

    assigned_admin_id: Optional[int] = Field(None, description="为空时分配给当前管理员")


class AdminDisputeInvestigateRequest(BaseModel):
    """管理员调查纠纷请求"""

    note: Optional[str] = Field(None, max_length=1000)


class AdminDisputeResolveRequest(BaseModel):
    """管理员裁决纠纷请求"""

    resolution: str = Field(..., description="continue_fulfillment / partial_refund / full_refund / release_settlement / other")
    resolution_note: str = Field(..., min_length=1, max_length=3000)
    refund_amount: Optional[Decimal] = Field(None, ge=0, decimal_places=2)


class AdminAuditLogResponse(BaseModel):
    """管理员操作审计日志响应"""

    id: int
    admin_id: int
    admin_name: Optional[str] = None
    action: str
    before_data: Optional[dict] = None
    after_data: Optional[dict] = None
    note: Optional[str] = None
    created_at: datetime


class AdminDisputeDetailResponse(BaseModel):
    """管理员纠纷详情响应"""

    dispute: OrderDisputeResponse
    order: dict[str, Any]
    context: dict[str, Any]
    audit_logs: list[AdminAuditLogResponse] = Field(default_factory=list)
