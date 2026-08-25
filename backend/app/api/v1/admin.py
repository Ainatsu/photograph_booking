"""
管理后台 API 路由

提供管理员登录、仪表盘统计、用户管理和订单管理等功能。
"""

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.security import create_access_token, verify_password
from backend.app.models.user import User
from backend.app.schemas.admin import (
    AdminLoginRequest,
    AdminTokenResponse,
    DashboardStats,
    AdminUserItem,
    AdminOrderItem,
    AdminOrderCancelRequest,
    AdminPhotographerApplicationItem,
    AdminPhotographerApplicationReview,
)
from backend.app.services.admin_service import (
    get_dashboard_stats,
    get_all_users,
    ban_user,
    unban_user,
    get_all_orders,
    admin_cancel_order,
)
from backend.app.services.photographer_application_service import (
    approve_application,
    list_applications,
    reject_application,
    serialize_application,
)
from backend.app.services.order_service import get_latest_order_event, push_order_event_update
from backend.app.schemas.payment import PaymentResponse, RefundResponse, SettlementResponse
from backend.app.services.payment_service import list_financial_records
from backend.app.schemas.dispute import (
    AdminDisputeAssignRequest,
    AdminDisputeDetailResponse,
    AdminDisputeInvestigateRequest,
    AdminDisputeResolveRequest,
    OrderDisputeResponse,
)
from backend.app.services.dispute_service import (
    assign_dispute,
    get_dispute,
    get_dispute_admin_detail,
    investigate_dispute,
    list_disputes,
    resolve_dispute,
    serialize_dispute,
)
from backend.app.services.ai_index_job_service import enqueue_index_job, process_index_jobs
from backend.app.services.ai_trace_service import agent_quality_dashboard

router = APIRouter(prefix="/admin", tags=["管理后台"])


# ===================== 鉴权辅助 =====================


def _verify_admin(token: str, db: Session) -> User:
    """从 token 解析用户，并校验管理员权限"""
    from jose import jwt, JWTError
    from backend.app.core.config import settings

    if not token or not token.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")
    try:
        payload = jwt.decode(token[7:], settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = int(payload.get("sub"))
        is_admin = payload.get("is_admin", False)
        if not is_admin:
            raise HTTPException(status_code=403, detail="无管理员权限")
    except (JWTError, ValueError, TypeError):
        raise HTTPException(status_code=401, detail="无效 token")

    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_admin:
        raise HTTPException(status_code=403, detail="无管理员权限")
    return user


@router.get("/ai/quality-dashboard", summary="AI Agent quality dashboard")
def ai_quality_dashboard(
    days: int = 7,
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
):
    """获取 AI Agent 质量看板数据"""
    _verify_admin(authorization, db)
    return agent_quality_dashboard(db, days=days)


@router.post("/ai/index-jobs", summary="Enqueue AI index rebuild")
def create_ai_index_job(
    owner_user_id: int | None = None,
    force: bool = False,
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
):
    """创建 AI 索引重建任务"""
    _verify_admin(authorization, db)
    job = enqueue_index_job(
        db,
        owner_user_id=owner_user_id,
        reason="admin_rebuild",
        force=force,
    )
    return {"id": job.id, "status": job.status, "job_key": job.job_key}


@router.post("/ai/index-jobs/process", summary="Process pending AI index jobs")
def process_ai_index_jobs(
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
):
    """处理待执行的 AI 索引任务"""
    _verify_admin(authorization, db)
    return process_index_jobs(db)


# ===================== 端点 =====================


@router.post(
    "/login",
    response_model=AdminTokenResponse,
    summary="管理员登录",
    description="使用管理员邮箱和密码登录后台管理系统。非管理员账号无法登录。",
    response_description="登录成功，返回管理员 JWT 令牌",
)
def admin_login(data: AdminLoginRequest, db: Session = Depends(get_db)):
    """管理员登录，校验管理员身份并签发 JWT 令牌"""
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not user.is_admin or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="邮箱或密码错误，或非管理员账号")
    token = create_access_token(data={"sub": str(user.id), "role": user.role, "is_admin": True, "ver": user.token_version or 0})
    return AdminTokenResponse(access_token=token)


@router.get(
    "/dashboard",
    response_model=DashboardStats,
    summary="仪表盘统计",
    description="获取平台核心运营数据的统计概览，包括用户数、订单数、待处理订单等关键指标。",
    response_description="平台统计数据",
)
def dashboard(db: Session = Depends(get_db)):
    """获取平台核心运营数据的统计概览"""
    return get_dashboard_stats(db)


@router.get(
    "/users",
    response_model=list[AdminUserItem],
    summary="用户列表",
    description="分页查询平台所有用户，支持通过 skip 和 limit 控制分页。",
    response_description="用户列表",
)
def list_users(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """分页查询平台所有用户"""
    return get_all_users(db, skip=skip, limit=limit)


@router.put(
    "/users/{user_id}/ban",
    response_model=AdminUserItem,
    summary="封禁用户",
    description="封禁指定用户，封禁后该用户无法登录和使用平台功能。",
    response_description="封禁后的用户信息",
)
def user_ban(user_id: int, db: Session = Depends(get_db)):
    """封禁指定用户"""
    user = ban_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user


@router.put(
    "/users/{user_id}/unban",
    response_model=AdminUserItem,
    summary="解封用户",
    description="解除指定用户的封禁状态，恢复其正常使用权限。",
    response_description="解封后的用户信息",
)
def user_unban(user_id: int, db: Session = Depends(get_db)):
    """解除指定用户的封禁状态"""
    user = unban_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user


@router.get(
    "/orders",
    response_model=list[AdminOrderItem],
    summary="全平台订单",
    description="分页查询平台所有订单，支持通过 skip 和 limit 控制分页。",
    response_description="订单列表",
)
def list_orders(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """分页查询平台所有订单"""
    return get_all_orders(db, skip=skip, limit=limit)


@router.get("/finance/payments", response_model=list[PaymentResponse], summary="支付记录")
def list_payments(
    skip: int = 0,
    limit: int = 50,
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
):
    """分页查询支付记录"""
    _verify_admin(authorization, db)
    return list_financial_records(db, "payments", skip, limit)


@router.get("/finance/refunds", response_model=list[RefundResponse], summary="退款记录")
def list_refunds(
    skip: int = 0,
    limit: int = 50,
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
):
    """分页查询退款记录"""
    _verify_admin(authorization, db)
    return list_financial_records(db, "refunds", skip, limit)


@router.get("/finance/settlements", response_model=list[SettlementResponse], summary="结算记录")
def list_settlements(
    skip: int = 0,
    limit: int = 50,
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
):
    """分页查询结算记录"""
    _verify_admin(authorization, db)
    return list_financial_records(db, "settlements", skip, limit)


@router.get("/disputes", response_model=list[OrderDisputeResponse], summary="争议列表")
def admin_list_disputes(
    status_value: str | None = None,
    skip: int = 0,
    limit: int = 50,
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
):
    """分页查询订单争议列表"""
    _verify_admin(authorization, db)
    return [serialize_dispute(item) for item in list_disputes(db, status_value, skip, limit)]


@router.get("/disputes/{dispute_id}", response_model=AdminDisputeDetailResponse, summary="争议详情")
def admin_get_dispute(
    dispute_id: int,
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
):
    """查看争议的完整管理详情"""
    _verify_admin(authorization, db)
    dispute = get_dispute(db, dispute_id)
    if not dispute:
        raise HTTPException(status_code=404, detail="争议不存在")
    return get_dispute_admin_detail(db, dispute)


@router.put("/disputes/{dispute_id}/assign", response_model=OrderDisputeResponse, summary="分配争议")
def admin_assign_dispute(
    dispute_id: int,
    data: AdminDisputeAssignRequest,
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
):
    """将争议分配给管理员处理"""
    admin = _verify_admin(authorization, db)
    dispute = get_dispute(db, dispute_id)
    if not dispute:
        raise HTTPException(status_code=404, detail="争议不存在")
    target_admin_id = data.assigned_admin_id or admin.id
    target_admin = db.query(User).filter(User.id == target_admin_id, User.is_admin.is_(True)).first()
    if not target_admin:
        raise HTTPException(status_code=404, detail="目标管理员不存在")
    return serialize_dispute(assign_dispute(db, dispute, admin.id, target_admin_id))


@router.put("/disputes/{dispute_id}/investigate", response_model=OrderDisputeResponse, summary="开始审核争议")
def admin_investigate_dispute(
    dispute_id: int,
    data: AdminDisputeInvestigateRequest,
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
):
    """管理员开始审核争议"""
    admin = _verify_admin(authorization, db)
    dispute = get_dispute(db, dispute_id)
    if not dispute:
        raise HTTPException(status_code=404, detail="争议不存在")
    return serialize_dispute(investigate_dispute(db, dispute, admin.id, data.note))


@router.put("/disputes/{dispute_id}/resolve", response_model=OrderDisputeResponse, summary="仲裁争议")
async def admin_resolve_dispute(
    dispute_id: int,
    data: AdminDisputeResolveRequest,
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
):
    """管理员仲裁争议"""
    admin = _verify_admin(authorization, db)
    dispute = get_dispute(db, dispute_id)
    if not dispute:
        raise HTTPException(status_code=404, detail="争议不存在")
    dispute = resolve_dispute(
        db,
        dispute,
        admin.id,
        data.resolution,
        data.resolution_note,
        data.refund_amount,
    )
    await push_order_event_update(get_latest_order_event(db, dispute.order_id), dispute.order)
    return serialize_dispute(dispute)


@router.put(
    "/orders/{order_id}/cancel",
    response_model=AdminOrderItem,
    summary="管理员取消订单",
    description="管理员取消指定订单，订单状态变为 cancelled（已取消）。",
    response_description="取消后的订单信息",
)
async def cancel_order(
    order_id: int,
    data: AdminOrderCancelRequest,
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
):
    """管理员取消指定订单"""
    admin = _verify_admin(authorization, db)
    order = admin_cancel_order(db, order_id, admin.id, data.reason)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    await push_order_event_update(get_latest_order_event(db, order.id), order)
    return order


@router.get(
    "/photographer-applications",
    response_model=list[AdminPhotographerApplicationItem],
    summary="摄影师申请列表",
    description="分页查询用户提交的摄影师身份申请。",
)
def photographer_applications(
    status: str | None = None,
    skip: int = 0,
    limit: int = 50,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """分页查询摄影师身份申请列表"""
    _verify_admin(authorization, db)
    applications = list_applications(db, status, skip=skip, limit=limit)
    return [serialize_application(application) for application in applications]


@router.put(
    "/photographer-applications/{application_id}/approve",
    response_model=AdminPhotographerApplicationItem,
    summary="通过摄影师申请",
)
def approve_photographer_application(
    application_id: int,
    data: AdminPhotographerApplicationReview | None = None,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """通过摄影师的入驻申请"""
    admin = _verify_admin(authorization, db)
    application = approve_application(
        db,
        application_id,
        reviewer_id=admin.id,
        review_note=data.review_note if data else None,
    )
    if not application:
        raise HTTPException(status_code=404, detail="申请不存在")
    return serialize_application(application)


@router.put(
    "/photographer-applications/{application_id}/reject",
    response_model=AdminPhotographerApplicationItem,
    summary="拒绝摄影师申请",
)
def reject_photographer_application(
    application_id: int,
    data: AdminPhotographerApplicationReview | None = None,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """拒绝摄影师的入驻申请"""
    admin = _verify_admin(authorization, db)
    application = reject_application(
        db,
        application_id,
        reviewer_id=admin.id,
        review_note=data.review_note if data else None,
    )
    if not application:
        raise HTTPException(status_code=404, detail="申请不存在")
    return serialize_application(application)
