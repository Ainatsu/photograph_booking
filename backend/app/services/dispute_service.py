"""订单争议领域服务：发起、证据补充、分配审核与仲裁处理。"""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from backend.app.models.order import Order, OrderStatus
from backend.app.models.order_delivery import OrderDelivery
from backend.app.models.order_dispute import (
    AdminAuditLog,
    DisputeResolution,
    DisputeStatus,
    OrderDispute,
    OrderDisputeEvidence,
)
from backend.app.models.order_event import OrderEvent
from backend.app.models.payment import Payment, Refund, Settlement
from backend.app.services.order_service import record_order_event
from backend.app.services.payment_service import (
    available_escrow_amount,
    refund_dispute_order,
    settle_order,
)


ACTIVE_DISPUTE_STATUSES = {
    DisputeStatus.OPEN.value,
    DisputeStatus.ASSIGNED.value,
    DisputeStatus.INVESTIGATING.value,
}
OPENABLE_ORDER_STATUSES = {
    OrderStatus.CONFIRMED,
    OrderStatus.IN_PROGRESS,
    OrderStatus.DELIVERED,
}
MONEY_QUANTUM = Decimal("0.01")


def _now() -> datetime:
    """返回去除时区信息的当前 UTC 时间。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _money(value) -> Decimal:
    """将数值规范化为保留两位小数的金额。"""
    return Decimal(str(value or 0)).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def _actor_role(order: Order, user_id: int) -> str:
    """判断用户在该订单中的角色，非订单参与方抛出 403。"""
    if order.customer_id == user_id:
        return "customer"
    if order.photographer_id == user_id:
        return "photographer"
    raise HTTPException(status_code=403, detail="只有订单客户或摄影师可以参与争议")


def _dispute_query(db: Session):
    """构造带关联加载的争议查询对象。"""
    return db.query(OrderDispute).options(
        joinedload(OrderDispute.opener),
        joinedload(OrderDispute.assigned_admin),
        joinedload(OrderDispute.evidence).joinedload(OrderDisputeEvidence.submitter),
        joinedload(OrderDispute.order),
    )


def get_active_order_dispute(db: Session, order_id: int) -> OrderDispute | None:
    """查询订单当前进行中的争议。"""
    return _dispute_query(db).filter(
        OrderDispute.order_id == order_id,
        OrderDispute.status.in_(ACTIVE_DISPUTE_STATUSES),
    ).order_by(OrderDispute.created_at.desc(), OrderDispute.id.desc()).first()


def get_dispute(db: Session, dispute_id: int) -> OrderDispute | None:
    """按 ID 查询争议并返回带关联数据的记录。"""
    return _dispute_query(db).filter(OrderDispute.id == dispute_id).first()


def serialize_evidence(item: OrderDisputeEvidence) -> dict:
    """将争议证据记录转为可返回的字典。"""
    return {
        "id": item.id,
        "dispute_id": item.dispute_id,
        "submitted_by": item.submitted_by,
        "submitter_role": item.submitter_role,
        "submitter_name": item.submitter.display_name if item.submitter else None,
        "description": item.description,
        "file_url": item.file_url,
        "file_name": item.file_name,
        "file_type": item.file_type,
        "file_size": item.file_size,
        "checksum": item.checksum,
        "reference_type": item.reference_type,
        "reference_id": item.reference_id,
        "created_at": item.created_at,
    }


def serialize_dispute(item: OrderDispute) -> dict:
    """将争议记录序列化为包含证据与担保余额的字典。"""
    return {
        "id": item.id,
        "dispute_no": item.dispute_no,
        "order_id": item.order_id,
        "opened_by": item.opened_by,
        "opened_by_role": item.opened_by_role,
        "opener_name": item.opener.display_name if item.opener else None,
        "reason_code": item.reason_code,
        "description": item.description,
        "requested_resolution": item.requested_resolution,
        "status": item.status,
        "assigned_admin_id": item.assigned_admin_id,
        "assigned_admin_name": item.assigned_admin.display_name if item.assigned_admin else None,
        "resolution": item.resolution,
        "resolution_note": item.resolution_note,
        "refund_amount": item.refund_amount or Decimal("0.00"),
        "currency": item.currency,
        "available_escrow_amount": available_escrow_amount_from_order(item.order),
        "evidence": [serialize_evidence(evidence) for evidence in item.evidence],
        "created_at": item.created_at,
        "updated_at": item.updated_at,
        "resolved_at": item.resolved_at,
    }


def available_escrow_amount_from_order(order: Order | None) -> Decimal:
    """从订单对象直接取得可用担保余额，空订单返回 0。"""
    if not order:
        return Decimal("0.00")
    return max(Decimal("0.00"), _money(order.escrow_amount))


def _add_evidence_rows(
    db: Session,
    dispute: OrderDispute,
    submitted_by: int,
    submitter_role: str,
    description: str | None,
    files: list[dict] | None = None,
    reference_type: str | None = None,
    reference_id: str | None = None,
) -> list[OrderDisputeEvidence]:
    """为争议批量写入证据行（描述、文件或订单记录引用）。"""
    normalized_description = (description or "").strip() or None
    items = files or []
    if not normalized_description and not items and not reference_type:
        raise HTTPException(status_code=400, detail="请填写证据说明、上传文件或选择订单记录作为证据")
    rows = []
    if reference_type or (normalized_description and not items):
        rows.append(OrderDisputeEvidence(
            dispute_id=dispute.id,
            submitted_by=submitted_by,
            submitter_role=submitter_role,
            description=normalized_description,
            reference_type=reference_type,
            reference_id=reference_id,
        ))
    for file in items:
        rows.append(OrderDisputeEvidence(
            dispute_id=dispute.id,
            submitted_by=submitted_by,
            submitter_role=submitter_role,
            description=normalized_description,
            file_url=file.get("file_url"),
            file_name=file.get("file_name"),
            file_type=file.get("file_type"),
            file_size=file.get("file_size"),
            checksum=file.get("checksum"),
        ))
    db.add_all(rows)
    db.flush()
    return rows


def open_order_dispute(
    db: Session,
    order: Order,
    opened_by: int,
    reason_code: str,
    description: str,
    requested_resolution: str,
    files: list[dict] | None = None,
) -> OrderDispute:
    """由订单参与方发起争议并挂起订单售后状态。"""
    opener_role = _actor_role(order, opened_by)
    if order.status not in OPENABLE_ORDER_STATUSES:
        raise HTTPException(status_code=409, detail="当前订单阶段不支持发起争议")
    if get_active_order_dispute(db, order.id):
        raise HTTPException(status_code=409, detail="该订单已有进行中的争议")
    normalized_description = (description or "").strip()
    if not normalized_description:
        raise HTTPException(status_code=400, detail="请说明争议事实和希望平台核查的内容")
    if requested_resolution not in {
        DisputeResolution.CONTINUE_FULFILLMENT.value,
        DisputeResolution.PARTIAL_REFUND.value,
        DisputeResolution.FULL_REFUND.value,
        DisputeResolution.OTHER.value,
    }:
        raise HTTPException(status_code=400, detail="不支持的争议处理诉求")

    dispute = OrderDispute(
        dispute_no=f"DSP-{uuid.uuid4().hex[:24].upper()}",
        order_id=order.id,
        opened_by=opened_by,
        opened_by_role=opener_role,
        reason_code=(reason_code or "other").strip() or "other",
        description=normalized_description,
        requested_resolution=requested_resolution,
        status=DisputeStatus.OPEN.value,
        currency="CNY",
        previous_after_sales_status=order.after_sales_status or "none",
        acceptance_deadline_snapshot=order.acceptance_deadline_at,
    )
    db.add(dispute)
    db.flush()
    if files:
        _add_evidence_rows(db, dispute, opened_by, opener_role, "发起争议时提交的附件", files)
    order.after_sales_status = "dispute_open"
    order.acceptance_deadline_at = None
    latest_delivery = db.query(OrderDelivery).filter(
        OrderDelivery.order_id == order.id,
    ).order_by(OrderDelivery.version.desc()).first()
    if latest_delivery:
        latest_delivery.acceptance_deadline_at = None
    from backend.app.services.automation_service import refresh_order_action_metadata
    refresh_order_action_metadata(db, order)
    record_order_event(
        db,
        order.id,
        opened_by,
        opener_role,
        "dispute_opened",
        order.status,
        f"{('客户' if opener_role == 'customer' else '摄影师')}发起争议：{normalized_description}",
    )
    db.commit()
    return get_dispute(db, dispute.id)


def add_dispute_evidence(
    db: Session,
    dispute: OrderDispute,
    submitted_by: int,
    description: str | None,
    files: list[dict] | None = None,
    reference_type: str | None = None,
    reference_id: str | None = None,
) -> OrderDispute:
    """向进行中的争议补充新的证据材料。"""
    role = _actor_role(dispute.order, submitted_by)
    if dispute.status not in ACTIVE_DISPUTE_STATUSES:
        raise HTTPException(status_code=409, detail="争议已结束，不能继续补充证据")
    _add_evidence_rows(
        db,
        dispute,
        submitted_by,
        role,
        description,
        files,
        reference_type,
        reference_id,
    )
    record_order_event(
        db,
        dispute.order_id,
        submitted_by,
        role,
        "dispute_evidence_added",
        dispute.order.status,
        f"{('客户' if role == 'customer' else '摄影师')}补充争议证据",
    )
    db.commit()
    return get_dispute(db, dispute.id)


def list_disputes(db: Session, status_value: str | None = None, skip: int = 0, limit: int = 50):
    """分页列出争议，可按状态过滤。"""
    query = _dispute_query(db)
    if status_value:
        query = query.filter(OrderDispute.status == status_value)
    return query.order_by(OrderDispute.created_at.desc(), OrderDispute.id.desc()).offset(skip).limit(limit).all()


def list_order_disputes(db: Session, order: Order, user_id: int) -> list[OrderDispute]:
    """列出指定订单的全部争议（仅限订单参与方）。"""
    _actor_role(order, user_id)
    return _dispute_query(db).filter(
        OrderDispute.order_id == order.id,
    ).order_by(OrderDispute.created_at.desc(), OrderDispute.id.desc()).all()


def _audit(
    db: Session,
    admin_id: int,
    dispute: OrderDispute,
    action: str,
    before: dict,
    after: dict,
    note: str | None = None,
) -> None:
    """记录一条管理员对争议的操作审计日志。"""
    db.add(AdminAuditLog(
        admin_id=admin_id,
        action=action,
        resource_type="order_dispute",
        resource_id=str(dispute.id),
        order_id=dispute.order_id,
        before_data=before,
        after_data=after,
        note=note,
    ))
    db.flush()


def assign_dispute(db: Session, dispute: OrderDispute, operator_admin_id: int, assigned_admin_id: int) -> OrderDispute:
    """将争议分配给指定管理员处理。"""
    if dispute.status not in ACTIVE_DISPUTE_STATUSES:
        raise HTTPException(status_code=409, detail="已结束的争议不能重新分配")
    before = {"status": dispute.status, "assigned_admin_id": dispute.assigned_admin_id}
    dispute.assigned_admin_id = assigned_admin_id
    dispute.status = DisputeStatus.ASSIGNED.value
    after = {"status": dispute.status, "assigned_admin_id": dispute.assigned_admin_id}
    _audit(db, operator_admin_id, dispute, "dispute_assigned", before, after)
    record_order_event(
        db, dispute.order_id, operator_admin_id, "admin", "dispute_assigned", dispute.order.status,
        f"平台已分配管理员 #{assigned_admin_id} 处理争议",
    )
    db.commit()
    return get_dispute(db, dispute.id)


def investigate_dispute(db: Session, dispute: OrderDispute, admin_id: int, note: str | None = None) -> OrderDispute:
    """将争议置为审核中并记录操作备注。"""
    if dispute.status not in ACTIVE_DISPUTE_STATUSES:
        raise HTTPException(status_code=409, detail="已结束的争议不能进入审核")
    before = {"status": dispute.status, "assigned_admin_id": dispute.assigned_admin_id}
    dispute.assigned_admin_id = dispute.assigned_admin_id or admin_id
    dispute.status = DisputeStatus.INVESTIGATING.value
    after = {"status": dispute.status, "assigned_admin_id": dispute.assigned_admin_id}
    _audit(db, admin_id, dispute, "dispute_investigating", before, after, note)
    record_order_event(
        db, dispute.order_id, admin_id, "admin", "dispute_investigating", dispute.order.status,
        note or "平台已开始审核双方证据",
    )
    db.commit()
    return get_dispute(db, dispute.id)


def _restore_fulfillment(db: Session, dispute: OrderDispute) -> None:
    """争议处理后恢复订单的履约状态与验收期限。"""
    order = dispute.order
    previous = dispute.previous_after_sales_status or "none"
    order.after_sales_status = previous if previous == "revision_requested" else "none"
    if order.status == OrderStatus.DELIVERED and order.after_sales_status == "none":
        deadline = _now() + timedelta(days=5)
        order.acceptance_deadline_at = deadline
        latest = db.query(OrderDelivery).filter(
            OrderDelivery.order_id == order.id,
        ).order_by(OrderDelivery.version.desc()).first()
        if latest:
            latest.acceptance_deadline_at = deadline
    else:
        order.acceptance_deadline_at = None


def resolve_dispute(
    db: Session,
    dispute: OrderDispute,
    admin_id: int,
    resolution: str,
    resolution_note: str,
    refund_amount=None,
) -> OrderDispute:
    """按仲裁结果处理争议：继续履约、部分/全额退款或直接结算。"""
    if dispute.status not in ACTIVE_DISPUTE_STATUSES:
        if dispute.status == DisputeStatus.RESOLVED.value and dispute.resolution == resolution:
            return dispute
        raise HTTPException(status_code=409, detail="该争议已经结束")
    if resolution not in {item.value for item in DisputeResolution}:
        raise HTTPException(status_code=400, detail="不支持的仲裁结果")
    normalized_note = (resolution_note or "").strip()
    if not normalized_note:
        raise HTTPException(status_code=400, detail="请填写仲裁依据和对双方的处理说明")

    order = dispute.order
    before = {
        "dispute_status": dispute.status,
        "order_status": getattr(order.status, "value", order.status),
        "after_sales_status": order.after_sales_status,
        "escrow_amount": str(_money(order.escrow_amount)),
        "payment_status": order.payment_status,
    }
    resolved_refund = Decimal("0.00")

    if resolution == DisputeResolution.CONTINUE_FULFILLMENT.value:
        _restore_fulfillment(db, dispute)
    elif resolution == DisputeResolution.PARTIAL_REFUND.value:
        available = available_escrow_amount(db, order)
        requested = _money(refund_amount)
        if requested >= available:
            raise HTTPException(status_code=400, detail="退还全部担保余额时请选择全额退款")
        refund_dispute_order(db, order, dispute.id, requested, admin_id, normalized_note)
        resolved_refund = requested
        _restore_fulfillment(db, dispute)
    elif resolution == DisputeResolution.FULL_REFUND.value:
        available = available_escrow_amount(db, order)
        if available <= 0:
            raise HTTPException(status_code=409, detail="订单当前没有可退款的担保资金")
        refund_dispute_order(db, order, dispute.id, available, admin_id, normalized_note)
        resolved_refund = available
        order.after_sales_status = "none"
        order.acceptance_deadline_at = None
        order.status = OrderStatus.CANCELLED
        order.cancelled_by = "admin"
        order.cancellation_reason = normalized_note
    elif resolution == DisputeResolution.RELEASE_SETTLEMENT.value:
        if order.status != OrderStatus.DELIVERED:
            raise HTTPException(status_code=409, detail="只有已交付待验收订单可以由平台直接结算")
        order.after_sales_status = "none"
        from backend.app.services.delivery_service import accept_current_delivery
        accept_current_delivery(db, order, "admin_resolution")
        order.status = OrderStatus.COMPLETED
        settle_order(db, order)
    else:
        _restore_fulfillment(db, dispute)

    dispute.status = DisputeStatus.RESOLVED.value
    dispute.assigned_admin_id = dispute.assigned_admin_id or admin_id
    dispute.resolution = resolution
    dispute.resolution_note = normalized_note
    dispute.refund_amount = resolved_refund
    dispute.resolved_at = _now()
    from backend.app.services.automation_service import refresh_order_action_metadata
    refresh_order_action_metadata(db, order)
    after = {
        "dispute_status": dispute.status,
        "resolution": resolution,
        "refund_amount": str(resolved_refund),
        "order_status": getattr(order.status, "value", order.status),
        "after_sales_status": order.after_sales_status,
        "escrow_amount": str(_money(order.escrow_amount)),
        "payment_status": order.payment_status,
    }
    _audit(db, admin_id, dispute, "dispute_resolved", before, after, normalized_note)
    record_order_event(
        db,
        order.id,
        admin_id,
        "admin",
        "dispute_resolved",
        order.status,
        f"平台仲裁结果：{resolution}。{normalized_note}",
    )
    db.commit()
    return get_dispute(db, dispute.id)


def get_dispute_admin_detail(db: Session, dispute: OrderDispute) -> dict:
    """组装管理员视角的争议详情，含订单、资金与审计上下文。"""
    order = dispute.order
    audit_logs = db.query(AdminAuditLog).options(joinedload(AdminAuditLog.admin)).filter(
        AdminAuditLog.resource_type == "order_dispute",
        AdminAuditLog.resource_id == str(dispute.id),
    ).order_by(AdminAuditLog.created_at.asc(), AdminAuditLog.id.asc()).all()
    order_events = db.query(OrderEvent).filter(OrderEvent.order_id == order.id).order_by(OrderEvent.id.asc()).all()
    deliveries = db.query(OrderDelivery).filter(OrderDelivery.order_id == order.id).order_by(OrderDelivery.version.asc()).all()
    payments = db.query(Payment).filter(Payment.order_id == order.id).order_by(Payment.id.asc()).all()
    refunds = db.query(Refund).filter(Refund.order_id == order.id).order_by(Refund.id.asc()).all()
    settlement = db.query(Settlement).filter(Settlement.order_id == order.id).first()
    return {
        "dispute": serialize_dispute(dispute),
        "order": {
            "id": order.id,
            "status": getattr(order.status, "value", order.status),
            "payment_status": order.payment_status,
            "after_sales_status": order.after_sales_status,
            "final_price": order.final_price,
            "escrow_amount": order.escrow_amount,
            "refunded_amount": order.refunded_amount,
            "settled_amount": order.settled_amount,
            "customer_id": order.customer_id,
            "photographer_id": order.photographer_id,
            "package_snapshot": order.package_snapshot,
        },
        "context": {
            "order_events": [
                {
                    "id": item.id,
                    "event_type": item.event_type,
                    "status": item.status,
                    "actor_id": item.actor_id,
                    "actor_role": item.actor_role,
                    "note": item.note,
                    "created_at": item.created_at,
                }
                for item in order_events
            ],
            "deliveries": [
                {
                    "id": item.id,
                    "version": item.version,
                    "status": item.status,
                    "description": item.description,
                    "file_count": item.file_count,
                    "created_at": item.created_at,
                }
                for item in deliveries
            ],
            "payments": [
                {
                    "id": item.id,
                    "payment_no": item.payment_no,
                    "purpose": item.purpose,
                    "amount": item.amount,
                    "currency": item.currency,
                    "status": item.status,
                    "paid_at": item.paid_at,
                    "created_at": item.created_at,
                }
                for item in payments
            ],
            "refunds": [
                {
                    "id": item.id,
                    "refund_no": item.refund_no,
                    "amount": item.amount,
                    "currency": item.currency,
                    "status": item.status,
                    "reason_code": item.reason_code,
                    "reason": item.reason,
                    "completed_at": item.completed_at,
                }
                for item in refunds
            ],
            "settlement": None if not settlement else {
                "id": settlement.id,
                "settlement_no": settlement.settlement_no,
                "gross_amount": settlement.gross_amount,
                "net_amount": settlement.net_amount,
                "currency": settlement.currency,
                "status": settlement.status,
                "settled_at": settlement.settled_at,
            },
        },
        "audit_logs": [
            {
                "id": item.id,
                "admin_id": item.admin_id,
                "admin_name": item.admin.display_name if item.admin else None,
                "action": item.action,
                "before_data": item.before_data,
                "after_data": item.after_data,
                "note": item.note,
                "created_at": item.created_at,
            }
            for item in audit_logs
        ],
    }
