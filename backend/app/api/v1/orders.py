"""
订单系统 API 路由

提供客户下单、摄影师接单/拒单、作品交付、客户验收与评价、订单查询和统计数据等功能。
"""

import hashlib
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.api.deps import get_current_active_user
from backend.app.models.user import User
from backend.app.models.order_delivery import OrderDelivery, OrderDeliveryFile
from backend.app.core.config import settings
from backend.app.schemas.order import (
    OrderCancelRequest,
    OrderCreateRequest,
    OrderDetailResponse,
    OrderRejectRequest,
    OrderRevisionAcknowledgeRequest,
    OrderRescheduleCounterRequest,
    OrderRescheduleRequest,
    OrderRescheduleResponseRequest,
    OrderResponse,
    ReviewCreateRequest,
    PhotographerStatsResponse,
)
from backend.app.schemas.dispute import OrderDisputeResponse
from backend.app.services.order_service import create_order

from backend.app.models.order import OrderStatus
from backend.app.services.order_service import (
    get_order_by_id,
    get_my_orders_as_customer,
    get_my_orders_as_photographer,
    get_order_detail,
    get_photographer_stats,
    get_latest_order_event,
    push_order_event_update,
    cancel_order,
    counter_order_reschedule,
    confirm_order_reschedule,
    respond_order_reschedule,
    request_order_reschedule,
    transition_order,
    withdraw_order_reschedule,
    OrderAction,
)
from backend.app.utils.file_upload import DELIVERY_ALLOWED_EXTENSIONS, save_upload_file
from typing import List, Optional
from backend.app.services.dispute_service import (
    add_dispute_evidence,
    get_dispute,
    list_order_disputes,
    open_order_dispute,
    serialize_dispute,
)

router = APIRouter(prefix="/orders", tags=["订单系统"])


@router.post(
    "/",
    response_model=OrderResponse,
    status_code=201,
    summary="客户下单",
    description="用户选择摄影师和套餐方案后提交预约订单。订单创建后状态为 pending（待确认）。",
    response_description="下单成功，返回新创建的订单信息",
)
async def place_order(
    data: OrderCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """客户提交预约订单，创建新订单"""
    if not data.package_id:
        raise HTTPException(status_code=400, detail="创建固定方案订单必须提交 package_id")
    order = create_order(db, current_user.id, data)
    await push_order_event_update(get_latest_order_event(db, order.id), order)
    return order


@router.put(
    "/{order_id}/confirm",
    response_model=OrderResponse,
    summary="摄影师确认订单",
    description="摄影师确认客户提交的订单，确认后订单状态变为 confirmed（已确认）。仅摄影师可操作自己名下订单。",
    response_description="确认后的订单信息",
)
async def confirm_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """摄影师确认客户提交的订单"""
    order = get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    order = transition_order(
        db,
        order=order,
        action=OrderAction.ACCEPT_BOOKING,
        actor_id=current_user.id,
    )
    await push_order_event_update(get_latest_order_event(db, order.id), order)
    return order


@router.put(
    "/{order_id}/start",
    response_model=OrderResponse,
    summary="摄影师开始拍摄",
    description="摄影师将已确认订单标记为 in_progress（拍摄中/待交付）。仅摄影师可操作自己名下订单。",
    response_description="进入拍摄中/待交付后的订单信息",
)
async def start_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """摄影师开始拍摄服务"""
    order = get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    order = transition_order(
        db,
        order=order,
        action=OrderAction.START_SERVICE,
        actor_id=current_user.id,
    )
    await push_order_event_update(get_latest_order_event(db, order.id), order)
    return order


@router.put(
    "/{order_id}/reject",
    response_model=OrderResponse,
    summary="摄影师拒绝订单",
    description="摄影师拒绝客户提交的订单，订单状态变为 cancelled（已取消）。仅摄影师可操作自己名下订单。",
    response_description="拒绝后的订单信息",
)
async def reject_order(
    order_id: int,
    data: OrderRejectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """摄影师拒绝客户提交的订单"""
    order = get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    order = transition_order(
        db,
        order=order,
        action=OrderAction.REJECT_BOOKING,
        actor_id=current_user.id,
        payload={"reason": data.rejection_reason},
    )
    await push_order_event_update(get_latest_order_event(db, order.id), order)
    return order


@router.put(
    "/{order_id}/reschedule/request",
    response_model=OrderResponse,
    summary="客户申请改期",
    description="订单双方提交独立改期申请；订单主状态和原预约时间保持不变，新候选时间临时锁定。",
    response_description="提交改期申请后的订单信息",
)
async def request_reschedule(
    order_id: int,
    data: OrderRescheduleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """客户申请订单改期"""
    order = get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    order = request_order_reschedule(
        db,
        order,
        current_user.id,
        data.appointment_time,
        data.reason,
    )
    await push_order_event_update(get_latest_order_event(db, order.id), order)
    return order


@router.put(
    "/{order_id}/reschedule/confirm",
    response_model=OrderResponse,
    summary="摄影师确认改期",
    description="摄影师确认客户提交的改期申请，确认后预约时间更新为客户申请的新时间，订单回到 confirmed（已确认）。",
    response_description="确认改期后的订单信息",
)
async def confirm_reschedule(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """摄影师确认客户的改期申请"""
    order = get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    order = confirm_order_reschedule(db, order, current_user.id)
    await push_order_event_update(get_latest_order_event(db, order.id), order)
    return order


@router.put("/{order_id}/reschedule/{request_id}/accept", response_model=OrderResponse)
async def accept_reschedule_request(
    order_id: int,
    request_id: int,
    data: OrderRescheduleResponseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """接受对方的改期申请"""
    order = get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    order = respond_order_reschedule(
        db, order, current_user.id, "accept", request_id, data.response_note
    )
    await push_order_event_update(get_latest_order_event(db, order.id), order)
    return order


@router.put("/{order_id}/reschedule/{request_id}/reject", response_model=OrderResponse)
async def reject_reschedule_request(
    order_id: int,
    request_id: int,
    data: OrderRescheduleResponseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """拒绝对方的改期申请"""
    order = get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    order = respond_order_reschedule(
        db, order, current_user.id, "reject", request_id, data.response_note
    )
    await push_order_event_update(get_latest_order_event(db, order.id), order)
    return order


@router.put("/{order_id}/reschedule/{request_id}/withdraw", response_model=OrderResponse)
async def withdraw_reschedule_request(
    order_id: int,
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """撤回自己提交的改期申请"""
    order = get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    order = withdraw_order_reschedule(db, order, current_user.id, request_id)
    await push_order_event_update(get_latest_order_event(db, order.id), order)
    return order


@router.put("/{order_id}/reschedule/{request_id}/counter", response_model=OrderResponse)
async def counter_reschedule_request(
    order_id: int,
    request_id: int,
    data: OrderRescheduleCounterRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """对改期申请提出新的时间建议"""
    order = get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    order = counter_order_reschedule(
        db, order, current_user.id, data.appointment_time, data.reason, request_id
    )
    await push_order_event_update(get_latest_order_event(db, order.id), order)
    return order


@router.put(
    "/{order_id}/cancel",
    response_model=OrderResponse,
    summary="双方取消订单",
    description="客户或订单所属摄影师可在待确认、已确认或改期待确认阶段取消订单，必须填写取消原因。",
    response_description="取消后的订单信息",
)
async def cancel_current_order(
    order_id: int,
    data: OrderCancelRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """取消当前订单，需填写取消原因"""
    order = get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    order = cancel_order(db, order, current_user.id, None, data.cancel_reason)
    await push_order_event_update(get_latest_order_event(db, order.id), order)
    return order


@router.get(
    "/my-customer",
    response_model=list[OrderResponse],
    summary="客户查看自己的订单",
    description="客户查看自己提交的所有订单，可按订单状态筛选，支持分页。",
    response_description="客户订单列表",
)
def list_my_orders_as_customer(
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """客户查看自己提交的订单列表，可按状态筛选并分页"""
    order_status = OrderStatus(status) if status else None
    return get_my_orders_as_customer(db, current_user.id, order_status, skip, limit)


@router.get(
    "/my-photographer",
    response_model=list[OrderResponse],
    summary="摄影师查看自己的订单",
    description="摄影师查看分配给自己处理的所有订单，可按订单状态筛选，支持分页。",
    response_description="摄影师订单列表",
)
def list_my_orders_as_photographer(
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """摄影师查看分配给自己处理的订单列表，可按状态筛选并分页"""
    order_status = OrderStatus(status) if status else None
    return get_my_orders_as_photographer(db, current_user.id, order_status, skip, limit)


@router.get(
    "/{order_id}/detail",
    response_model=OrderDetailResponse,
    summary="查看订单详情",
    description="查看单个订单的完整详情和历史时间线。客户和订单所属摄影师可查看。",
    response_description="订单详情和历史记录",
)
def view_order_detail(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """查看单个订单的完整详情和历史时间线"""
    order = get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if current_user.id not in [order.customer_id, order.photographer_id] and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="只能查看您的订单")
    return get_order_detail(db, order)


@router.get("/{order_id}/deliveries/{delivery_id}/files/{file_id}/download")
def download_delivery_file(
    order_id: int,
    delivery_id: int,
    file_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """下载订单交付文件，本地文件直接返回，外链则重定向"""
    order = get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if current_user.id not in [order.customer_id, order.photographer_id] and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="无权下载该订单的交付文件")

    item = (
        db.query(OrderDeliveryFile)
        .join(OrderDelivery, OrderDelivery.id == OrderDeliveryFile.delivery_id)
        .filter(
            OrderDelivery.order_id == order_id,
            OrderDelivery.id == delivery_id,
            OrderDeliveryFile.id == file_id,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="交付文件不存在")

    if item.file_url.startswith("/static/"):
        relative_path = item.file_url.removeprefix("/static/")
        upload_root = Path(settings.UPLOAD_DIR).resolve()
        file_path = (upload_root / relative_path).resolve()
        try:
            file_path.relative_to(upload_root)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="无效的交付文件路径") from exc
        if not file_path.is_file():
            raise HTTPException(status_code=404, detail="交付文件已不存在")
        return FileResponse(file_path, filename=item.file_name, media_type=item.file_type or "application/octet-stream")

    return RedirectResponse(item.file_url)


@router.post(
    "/{order_id}/deliver",
    response_model=OrderResponse,
    summary="摄影师交付作品",
    description="摄影师上传作品图片并交付给客户。仅拍摄中的订单可以交付，交付后订单状态变为 delivered（已交付）。",
    response_description="交付后的订单信息",
)
async def deliver_works(
    order_id: int,
    description: str = Form(""),
    idempotency_key: Optional[str] = Form(None),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """摄影师上传作品图片并交付给客户"""
    order = get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.photographer_id != current_user.id:
        raise HTTPException(status_code=403, detail="只能操作分配给您的订单")
    if order.status not in {OrderStatus.IN_PROGRESS, OrderStatus.DELIVERED}:
        raise HTTPException(status_code=400, detail="请先开始服务，再交付作品")

    delivery_key = (idempotency_key or f"delivery-{order.id}-{uuid.uuid4().hex}").strip()
    if len(delivery_key) < 8 or len(delivery_key) > 80:
        raise HTTPException(status_code=400, detail="交付幂等键长度必须为 8-80 个字符")
    existing = db.query(OrderDelivery).filter(OrderDelivery.idempotency_key == delivery_key).first()
    if existing:
        if existing.order_id != order.id:
            raise HTTPException(status_code=409, detail="交付幂等键已用于其他订单")
        return order

    image_urls = []
    delivery_files = []
    for file in files:
        content = await file.read()
        await file.seek(0)
        url = await save_upload_file(file, sub_dir="deliveries", allowed_extensions=DELIVERY_ALLOWED_EXTENSIONS)
        image_urls.append(url)
        delivery_files.append({
            "file_url": url,
            "file_name": file.filename or "delivery-image",
            "file_type": file.content_type,
            "file_size": len(content),
            "checksum": hashlib.sha256(content).hexdigest(),
        })

    order = transition_order(
        db,
        order=order,
        action=OrderAction.SUBMIT_DELIVERY,
        actor_id=current_user.id,
        payload={
            "delivery": {"images": image_urls, "description": description},
            "delivery_files": delivery_files,
            "idempotency_key": delivery_key,
        },
    )
    await push_order_event_update(get_latest_order_event(db, order.id), order)
    return order


@router.post(
    "/{order_id}/revision",
    response_model=OrderResponse,
    summary="客户申请修改交付作品",
    description="客户针对当前交付版本提交返修说明；免费修改次数由订单合同快照控制。",
)
async def request_delivery_revision(
    order_id: int,
    instructions: str = Form(...),
    idempotency_key: Optional[str] = Form(None),
    files: Optional[List[UploadFile]] = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """客户针对当前交付版本提交返修申请"""
    order = get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.customer_id != current_user.id:
        raise HTTPException(status_code=403, detail="只有订单客户可以申请修改")
    if order.status != OrderStatus.DELIVERED:
        raise HTTPException(status_code=400, detail="只有待验收订单可以申请修改")
    if int(order.revision_used_count or 0) >= int(order.included_revision_count or 0):
        raise HTTPException(status_code=409, detail="订单包含的免费修改次数已用完")

    revision_key = (idempotency_key or f"revision-{order.id}-{uuid.uuid4().hex}").strip()
    if len(revision_key) < 8 or len(revision_key) > 80:
        raise HTTPException(status_code=400, detail="返修幂等键长度必须为 8-80 个字符")

    reference_files = []
    for file in files or []:
        content = await file.read()
        await file.seek(0)
        url = await save_upload_file(file, sub_dir="revision-references")
        reference_files.append({
            "file_url": url,
            "file_name": file.filename or "revision-reference",
            "file_type": file.content_type,
            "file_size": len(content),
            "checksum": hashlib.sha256(content).hexdigest(),
        })

    order = transition_order(
        db,
        order=order,
        action=OrderAction.REQUEST_REVISION,
        actor_id=current_user.id,
        payload={
            "instructions": instructions,
            "reference_files": reference_files,
            "idempotency_key": revision_key,
        },
    )
    await push_order_event_update(get_latest_order_event(db, order.id), order)
    return order


@router.get("/{order_id}/disputes", response_model=list[OrderDisputeResponse], summary="查看订单争议")
def view_order_disputes(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """查看订单的争议列表"""
    order = get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    return [serialize_dispute(item) for item in list_order_disputes(db, order, current_user.id)]


@router.post("/{order_id}/disputes", response_model=OrderDisputeResponse, summary="发起订单争议")
async def create_order_dispute(
    order_id: int,
    reason_code: str = Form(...),
    description: str = Form(...),
    requested_resolution: str = Form(...),
    files: Optional[List[UploadFile]] = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """发起订单争议并附上证据文件"""
    order = get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    evidence_files = []
    for file in files or []:
        content = await file.read()
        await file.seek(0)
        url = await save_upload_file(file, sub_dir="dispute-evidence")
        evidence_files.append({
            "file_url": url,
            "file_name": file.filename or "dispute-evidence",
            "file_type": file.content_type,
            "file_size": len(content),
            "checksum": hashlib.sha256(content).hexdigest(),
        })
    dispute = open_order_dispute(
        db,
        order,
        current_user.id,
        reason_code,
        description,
        requested_resolution,
        evidence_files,
    )
    await push_order_event_update(get_latest_order_event(db, order.id), order)
    return serialize_dispute(dispute)


@router.post(
    "/{order_id}/disputes/{dispute_id}/evidence",
    response_model=OrderDisputeResponse,
    summary="补充争议证据",
)
async def supplement_dispute_evidence(
    order_id: int,
    dispute_id: int,
    description: Optional[str] = Form(None),
    reference_type: Optional[str] = Form(None),
    reference_id: Optional[str] = Form(None),
    files: Optional[List[UploadFile]] = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """为订单争议补充证据文件"""
    order = get_order_by_id(db, order_id)
    dispute = get_dispute(db, dispute_id)
    if not order or not dispute or dispute.order_id != order.id:
        raise HTTPException(status_code=404, detail="争议不存在")
    evidence_files = []
    for file in files or []:
        content = await file.read()
        await file.seek(0)
        url = await save_upload_file(file, sub_dir="dispute-evidence")
        evidence_files.append({
            "file_url": url,
            "file_name": file.filename or "dispute-evidence",
            "file_type": file.content_type,
            "file_size": len(content),
            "checksum": hashlib.sha256(content).hexdigest(),
        })
    dispute = add_dispute_evidence(
        db,
        dispute,
        current_user.id,
        description,
        evidence_files,
        reference_type,
        reference_id,
    )
    await push_order_event_update(get_latest_order_event(db, order.id), order)
    return serialize_dispute(dispute)


@router.put(
    "/{order_id}/revision/{revision_id}/acknowledge",
    response_model=OrderResponse,
    summary="摄影师确认返修排期",
)
async def acknowledge_delivery_revision(
    order_id: int,
    revision_id: int,
    data: OrderRevisionAcknowledgeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """摄影师确认返修排期"""
    order = get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    order = transition_order(
        db,
        order=order,
        action=OrderAction.ACKNOWLEDGE_REVISION,
        actor_id=current_user.id,
        payload={
            "revision_id": revision_id,
            "expected_redelivery_at": data.expected_redelivery_at,
        },
    )
    await push_order_event_update(get_latest_order_event(db, order.id), order)
    return order


@router.put(
    "/{order_id}/accept",
    response_model=OrderResponse,
    summary="客户接收作品",
    description="客户确认验收摄影师当前交付版本，订单进入 completed；评价不再影响完成和结算。",
    response_description="接收后的订单信息",
)
async def accept_delivery(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """客户确认验收当前交付的作品"""
    order = get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    order = transition_order(
        db,
        order=order,
        action=OrderAction.ACCEPT_DELIVERY,
        actor_id=current_user.id,
    )
    await push_order_event_update(get_latest_order_event(db, order.id), order)
    return order


@router.put(
    "/{order_id}/review",
    response_model=OrderResponse,
    summary="客户评价",
    description="客户对已完成的服务进行评分和评价。评分为 1-10 分，评价后订单状态变为 reviewed（已完成）。",
    response_description="评价后的订单信息",
)
async def review_order(
    order_id: int,
    data: ReviewCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """客户对已完成的服务进行评分和评价"""
    order = get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    order = transition_order(
        db,
        order=order,
        action=OrderAction.SUBMIT_REVIEW,
        actor_id=current_user.id,
        payload={"rating": data.rating, "review_text": data.review_text},
    )
    await push_order_event_update(get_latest_order_event(db, order.id), order)
    return order


@router.get(
    "/stats",
    response_model=PhotographerStatsResponse,
    summary="摄影师数据统计",
    description="获取当前摄影师用户的业务数据统计，包括本月/本周接单数、完成率和客户平均评分。仅摄影师可查看。",
    response_description="摄影师数据统计",
)
def get_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """获取当前摄影师用户的业务数据统计"""
    if current_user.role != "photographer":
        raise HTTPException(status_code=403, detail="仅摄影师可查看数据统计")
    return get_photographer_stats(db, current_user.id)


@router.get(
    "/stats/{user_id}",
    response_model=PhotographerStatsResponse,
    summary="查看指定摄影师数据统计",
    description="公开查看指定摄影师的业务数据统计，包括本月/本周接单数、完成率和客户平均评分。",
    response_description="摄影师数据统计",
)
def get_public_stats(
    user_id: int,
    db: Session = Depends(get_db),
):
    """公开查看指定摄影师的业务数据统计"""
    user = db.query(User).filter(User.id == user_id, User.role == "photographer").first()
    if not user:
        raise HTTPException(status_code=404, detail="摄影师不存在")
    return get_photographer_stats(db, user_id)
