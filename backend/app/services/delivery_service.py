"""订单交付、返修与验收相关的业务逻辑服务。"""

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from backend.app.core.config import settings
from backend.app.models.order import Order, OrderStatus
from backend.app.models.order_delivery import (
    DeliveryStatus,
    OrderDelivery,
    OrderDeliveryFile,
    OrderRevisionRequest,
    RevisionStatus,
)


def _now() -> datetime:
    """返回不带时区的当前 UTC 时间。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def serialize_delivery_file(item: OrderDeliveryFile) -> dict:
    """序列化交付文件为字典。"""
    return {
        "id": item.id,
        "file_url": item.file_url,
        "file_name": item.file_name,
        "file_type": item.file_type,
        "file_size": item.file_size,
        "checksum": item.checksum,
        "created_at": item.created_at,
    }


def serialize_delivery(item: OrderDelivery) -> dict:
    """序列化交付记录为字典（含文件列表）。"""
    return {
        "id": item.id,
        "order_id": item.order_id,
        "version": item.version,
        "submitted_by": item.submitted_by,
        "description": item.description,
        "file_count": item.file_count,
        "status": item.status,
        "acceptance_deadline_at": item.acceptance_deadline_at,
        "accepted_at": item.accepted_at,
        "created_at": item.created_at,
        "files": [serialize_delivery_file(file) for file in item.files],
    }


def serialize_revision_request(item: OrderRevisionRequest) -> dict:
    """序列化返修请求为字典。"""
    return {
        "id": item.id,
        "order_id": item.order_id,
        "delivery_id": item.delivery_id,
        "sequence": item.sequence,
        "requested_by": item.requested_by,
        "instructions": item.instructions,
        "reference_files": item.reference_files or [],
        "counts_as_free": bool(item.counts_as_free),
        "status": item.status,
        "response_due_at": item.response_due_at,
        "expected_redelivery_at": item.expected_redelivery_at,
        "created_at": item.created_at,
        "resolved_at": item.resolved_at,
    }


def list_order_deliveries(db: Session, order_id: int) -> list[OrderDelivery]:
    """列出订单的全部交付版本，新版本在前。"""
    return (
        db.query(OrderDelivery)
        .options(joinedload(OrderDelivery.files))
        .filter(OrderDelivery.order_id == order_id)
        .order_by(OrderDelivery.version.desc())
        .all()
    )


def list_order_revision_requests(db: Session, order_id: int) -> list[OrderRevisionRequest]:
    """列出订单的全部返修请求，新请求在前。"""
    return (
        db.query(OrderRevisionRequest)
        .filter(OrderRevisionRequest.order_id == order_id)
        .order_by(OrderRevisionRequest.sequence.desc())
        .all()
    )


def get_latest_delivery(db: Session, order_id: int) -> OrderDelivery | None:
    """获取订单最新一版交付。"""
    return (
        db.query(OrderDelivery)
        .options(joinedload(OrderDelivery.files))
        .filter(OrderDelivery.order_id == order_id)
        .order_by(OrderDelivery.version.desc())
        .first()
    )


def get_active_revision_request(db: Session, order_id: int) -> OrderRevisionRequest | None:
    """获取订单当前待处理的返修请求。"""
    return (
        db.query(OrderRevisionRequest)
        .filter(
            OrderRevisionRequest.order_id == order_id,
            OrderRevisionRequest.status == RevisionStatus.REQUESTED.value,
        )
        .order_by(OrderRevisionRequest.sequence.desc())
        .first()
    )


def create_delivery_version(
    db: Session,
    order: Order,
    submitted_by: int,
    description: str | None,
    files: list[dict],
    idempotency_key: str,
) -> tuple[OrderDelivery, bool]:
    """创建新交付版本（幂等），返回 (交付, 是否新建)。"""
    existing = db.query(OrderDelivery).filter(OrderDelivery.idempotency_key == idempotency_key).first()
    if existing:
        if existing.order_id != order.id:
            raise HTTPException(status_code=409, detail="交付幂等键已用于其他订单")
        return existing, False

    if order.photographer_id != submitted_by:
        raise HTTPException(status_code=403, detail="只有订单摄影师可以提交交付")
    if order.status not in {OrderStatus.IN_PROGRESS, OrderStatus.DELIVERED}:
        raise HTTPException(status_code=400, detail="当前订单状态不可提交交付")
    if order.after_sales_status == "dispute_open":
        raise HTTPException(status_code=409, detail="争议处理中，暂不能提交或更新交付")

    latest = get_latest_delivery(db, order.id)
    active_revision = get_active_revision_request(db, order.id)
    if order.status == OrderStatus.DELIVERED:
        if order.after_sales_status != "revision_requested" or not active_revision:
            raise HTTPException(status_code=409, detail="客户尚未申请返修，不能覆盖当前交付")
    if not files:
        raise HTTPException(status_code=400, detail="交付文件不能为空")

    version = (latest.version if latest else 0) + 1
    deadline = _now() + timedelta(days=max(1, settings.ACCEPTANCE_WINDOW_DAYS))
    if latest:
        latest.status = DeliveryStatus.SUPERSEDED.value
        latest.acceptance_deadline_at = None

    delivery = OrderDelivery(
        order_id=order.id,
        version=version,
        submitted_by=submitted_by,
        description=(description or "").strip() or None,
        file_count=len(files),
        status=DeliveryStatus.SUBMITTED.value,
        idempotency_key=idempotency_key,
        acceptance_deadline_at=deadline,
    )
    db.add(delivery)
    db.flush()
    for index, file in enumerate(files, start=1):
        db.add(OrderDeliveryFile(
            delivery_id=delivery.id,
            file_url=file["file_url"],
            file_name=file.get("file_name") or f"delivery-{version}-{index}",
            file_type=file.get("file_type"),
            file_size=file.get("file_size"),
            checksum=file.get("checksum"),
        ))

    if active_revision:
        active_revision.status = RevisionStatus.FULFILLED.value
        active_revision.resolved_at = _now()

    order.delivery = {
        "delivery_id": delivery.id,
        "version": version,
        "images": [file["file_url"] for file in files],
        "description": delivery.description,
    }
    order.after_sales_status = "none"
    order.acceptance_deadline_at = deadline
    db.flush()
    db.refresh(delivery)
    return delivery, True


def request_order_revision(
    db: Session,
    order: Order,
    requested_by: int,
    instructions: str,
    reference_files: list[dict],
    idempotency_key: str,
) -> tuple[OrderRevisionRequest, bool]:
    """客户对当前交付发起返修请求，返回 (请求, 是否新建)。"""
    existing = db.query(OrderRevisionRequest).filter(
        OrderRevisionRequest.idempotency_key == idempotency_key
    ).first()
    if existing:
        if existing.order_id != order.id:
            raise HTTPException(status_code=409, detail="返修幂等键已用于其他订单")
        return existing, False

    if order.customer_id != requested_by:
        raise HTTPException(status_code=403, detail="只有订单客户可以申请修改")
    if order.status != OrderStatus.DELIVERED:
        raise HTTPException(status_code=400, detail="只有待验收订单可以申请修改")
    if order.after_sales_status != "none" or get_active_revision_request(db, order.id):
        raise HTTPException(status_code=409, detail="已有返修或售后请求正在处理中")

    included = max(0, int(order.included_revision_count or 0))
    used = max(0, int(order.revision_used_count or 0))
    if used >= included:
        raise HTTPException(status_code=409, detail="订单包含的免费修改次数已用完")

    normalized = (instructions or "").strip()
    if not normalized:
        raise HTTPException(status_code=400, detail="请填写具体修改说明")
    latest = get_latest_delivery(db, order.id)
    if not latest or latest.status != DeliveryStatus.SUBMITTED.value:
        raise HTTPException(status_code=409, detail="当前没有可申请修改的交付版本")

    sequence = (db.query(func.max(OrderRevisionRequest.sequence)).filter(
        OrderRevisionRequest.order_id == order.id
    ).scalar() or 0) + 1
    revision = OrderRevisionRequest(
        order_id=order.id,
        delivery_id=latest.id,
        sequence=sequence,
        requested_by=requested_by,
        instructions=normalized,
        reference_files=reference_files or [],
        counts_as_free=True,
        status=RevisionStatus.REQUESTED.value,
        idempotency_key=idempotency_key,
        response_due_at=_now() + timedelta(hours=max(1, settings.REVISION_RESPONSE_HOURS)),
    )
    db.add(revision)
    latest.status = DeliveryStatus.REVISION_REQUESTED.value
    latest.acceptance_deadline_at = None
    order.revision_used_count = used + 1
    order.after_sales_status = "revision_requested"
    order.acceptance_deadline_at = None
    db.flush()
    db.refresh(revision)
    return revision, True


def acknowledge_revision_request(
    db: Session,
    order: Order,
    revision_id: int,
    photographer_id: int,
    expected_redelivery_at: datetime,
) -> OrderRevisionRequest:
    """摄影师确认返修请求并设定预计重新交付时间。"""
    if order.photographer_id != photographer_id:
        raise HTTPException(status_code=403, detail="只有订单摄影师可以确认返修排期")
    revision = db.query(OrderRevisionRequest).filter(
        OrderRevisionRequest.id == revision_id,
        OrderRevisionRequest.order_id == order.id,
        OrderRevisionRequest.status == RevisionStatus.REQUESTED.value,
    ).first()
    if not revision:
        raise HTTPException(status_code=404, detail="待处理返修请求不存在")
    expected = expected_redelivery_at
    if expected.tzinfo is not None:
        expected = expected.astimezone(timezone.utc).replace(tzinfo=None)
    if expected <= _now():
        raise HTTPException(status_code=400, detail="预计重新交付时间必须晚于当前时间")
    revision.expected_redelivery_at = expected
    db.flush()
    return revision


def accept_current_delivery(db: Session, order: Order, completion_type: str) -> OrderDelivery:
    """客户验收当前交付并完成订单。"""
    if order.after_sales_status != "none":
        raise HTTPException(status_code=409, detail="返修或售后处理中，暂不能验收")
    latest = get_latest_delivery(db, order.id)
    if not latest or latest.status != DeliveryStatus.SUBMITTED.value:
        raise HTTPException(status_code=409, detail="当前没有可验收的交付版本")

    now = _now()
    latest.status = DeliveryStatus.ACCEPTED.value
    latest.accepted_at = now
    latest.acceptance_deadline_at = None
    order.acceptance_deadline_at = None
    order.completed_at = now
    order.completion_type = completion_type
    return latest


def expire_acceptance_orders(db: Session, order_id: int | None = None) -> list[int]:
    """自动验收超期未处理的交付订单，返回完成的订单 ID 列表。"""
    now = _now()
    query = db.query(Order).filter(
        Order.status == OrderStatus.DELIVERED,
        Order.after_sales_status == "none",
        Order.acceptance_deadline_at.isnot(None),
        Order.acceptance_deadline_at <= now,
    )
    if order_id is not None:
        query = query.filter(Order.id == order_id)
    orders = query.all()
    completed_ids = []
    for order in orders:
        from backend.app.services.order_service import OrderAction, transition_order

        transition_order(
            db,
            order=order,
            action=OrderAction.AUTO_ACCEPT_DELIVERY,
            actor_id=None,
            actor_role="system",
        )
        completed_ids.append(order.id)
    return completed_ids
