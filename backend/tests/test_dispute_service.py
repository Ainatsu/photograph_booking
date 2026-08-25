from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException

from backend.app.models.order import Order, OrderStatus
from backend.app.models.order_dispute import AdminAuditLog, OrderDisputeEvidence
from backend.app.models.payment import Payment, Refund, Settlement
from backend.app.services.delivery_service import expire_acceptance_orders
from backend.app.services.dispute_service import (
    add_dispute_evidence,
    assign_dispute,
    open_order_dispute,
    resolve_dispute,
)
from backend.app.services.order_service import OrderAction, transition_order


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _funded_order(db, customer_user, photographer_user, status=OrderStatus.IN_PROGRESS):
    order = Order(
        customer_id=customer_user.id,
        photographer_id=photographer_user.id,
        package_snapshot="阶段 E 测试方案",
        appointment_time=_now() + timedelta(days=2),
        duration_minutes=60,
        status=status,
        final_price=Decimal("1000.00"),
        currency="CNY",
        payment_status="paid_in_escrow",
        escrow_amount=Decimal("1000.00"),
        included_revision_count=1,
    )
    db.add(order)
    db.flush()
    db.add(Payment(
        payment_no=f"PAY-DISPUTE-{order.id}",
        order_id=order.id,
        customer_id=customer_user.id,
        purpose="full",
        amount=Decimal("1000.00"),
        currency="CNY",
        status="succeeded",
        provider="mock",
        idempotency_key=f"payment-dispute-{order.id}",
        expires_at=_now() + timedelta(hours=1),
        paid_at=_now(),
    ))
    db.commit()
    db.refresh(order)
    return order


def _deliver(db, order, photographer_user):
    return transition_order(
        db,
        order=order,
        action=OrderAction.SUBMIT_DELIVERY,
        actor_id=photographer_user.id,
        payload={
            "delivery": {"images": ["/static/dispute-v1.jpg"], "description": "争议测试交付"},
            "delivery_files": [{
                "file_url": "/static/dispute-v1.jpg",
                "file_name": "dispute-v1.jpg",
                "file_type": "image/jpeg",
                "file_size": 100,
                "checksum": "e" * 64,
            }],
            "idempotency_key": f"delivery-dispute-{order.id}",
        },
    )


class TestDisputeLifecycle:
    def test_customer_opens_dispute_and_freezes_auto_acceptance(self, db, customer_user, photographer_user):
        order = _deliver(db, _funded_order(db, customer_user, photographer_user), photographer_user)
        original_deadline = order.acceptance_deadline_at

        dispute = open_order_dispute(
            db,
            order,
            customer_user.id,
            "quality_issue",
            "交付成片与约定风格差异明显，请平台核查。",
            "partial_refund",
            [{"file_url": "/static/evidence.jpg", "file_name": "evidence.jpg"}],
        )

        assert dispute.opened_by_role == "customer"
        assert order.after_sales_status == "dispute_open"
        assert order.acceptance_deadline_at is None
        assert dispute.acceptance_deadline_snapshot == original_deadline
        assert len(dispute.evidence) == 1

        order.acceptance_deadline_at = _now() - timedelta(minutes=1)
        db.commit()
        assert expire_acceptance_orders(db, order.id) == []
        assert order.status == OrderStatus.DELIVERED

    def test_both_parties_can_add_evidence_while_dispute_is_active(self, db, customer_user, photographer_user):
        order = _funded_order(db, customer_user, photographer_user)
        dispute = open_order_dispute(
            db, order, photographer_user.id, "customer_cooperation", "客户未按约定提供选片反馈。", "continue_fulfillment"
        )
        add_dispute_evidence(
            db,
            dispute,
            customer_user.id,
            "补充订单聊天记录",
            reference_type="order_message",
            reference_id="88",
        )
        evidence = db.query(OrderDisputeEvidence).filter(OrderDisputeEvidence.dispute_id == dispute.id).one()
        assert evidence.submitter_role == "customer"
        assert evidence.reference_type == "order_message"

    def test_admin_partial_refund_restores_fulfillment_and_writes_audit(
        self, db, customer_user, photographer_user, admin_user
    ):
        order = _deliver(db, _funded_order(db, customer_user, photographer_user), photographer_user)
        dispute = open_order_dispute(
            db, order, customer_user.id, "quality_issue", "部分照片需要补偿。", "partial_refund"
        )
        assign_dispute(db, dispute, admin_user.id, admin_user.id)
        resolved = resolve_dispute(
            db,
            dispute,
            admin_user.id,
            "partial_refund",
            "双方证据显示部分交付未达到约定，退款 200 元后继续履约。",
            Decimal("200.00"),
        )

        refund = db.query(Refund).filter(Refund.order_id == order.id).one()
        assert resolved.status == "resolved"
        assert resolved.refund_amount == Decimal("200.00")
        assert refund.currency == "CNY"
        assert order.escrow_amount == Decimal("800.00")
        assert order.payment_status == "partially_refunded"
        assert order.after_sales_status == "none"
        assert order.acceptance_deadline_at is not None
        assert db.query(AdminAuditLog).filter(AdminAuditLog.action == "dispute_resolved").count() == 1

    def test_full_refund_terminates_order_and_cannot_exceed_escrow(
        self, db, customer_user, photographer_user, admin_user
    ):
        order = _funded_order(db, customer_user, photographer_user)
        dispute = open_order_dispute(
            db, order, customer_user.id, "service_failure", "摄影师无法继续履约。", "full_refund"
        )
        resolved = resolve_dispute(
            db, dispute, admin_user.id, "full_refund", "确认服务无法继续，退还全部担保款。"
        )
        assert resolved.refund_amount == Decimal("1000.00")
        assert order.status == OrderStatus.CANCELLED
        assert order.payment_status == "refunded"
        assert order.escrow_amount == Decimal("0.00")

        with pytest.raises(HTTPException):
            resolve_dispute(db, resolved, admin_user.id, "partial_refund", "重复处理", Decimal("1.00"))

    def test_release_settlement_completes_delivery(self, db, customer_user, photographer_user, admin_user):
        order = _deliver(db, _funded_order(db, customer_user, photographer_user), photographer_user)
        dispute = open_order_dispute(
            db, order, photographer_user.id, "acceptance_delay", "客户长期拒绝确认无争议交付。", "other"
        )
        resolve_dispute(
            db, dispute, admin_user.id, "release_settlement", "证据显示摄影师已完整履约，平台直接验收结算。"
        )
        settlement = db.query(Settlement).filter(Settlement.order_id == order.id).one()
        assert order.status == OrderStatus.COMPLETED
        assert order.payment_status == "settled"
        assert settlement.status == "settled"


class TestDisputeApi:
    def test_customer_can_open_and_supplement_dispute(
        self, client, db, customer_user, photographer_user, customer_headers
    ):
        order = _funded_order(db, customer_user, photographer_user)
        response = client.post(
            f"/api/v1/orders/{order.id}/disputes",
            headers=customer_headers,
            data={
                "reason_code": "service_failure",
                "description": "摄影服务未按合同约定继续推进。",
                "requested_resolution": "full_refund",
            },
            files={"files": ("evidence.png", b"fake-png-content", "image/png")},
        )
        assert response.status_code == 200, response.text
        dispute_id = response.json()["id"]
        assert response.json()["currency"] == "CNY"

        supplement = client.post(
            f"/api/v1/orders/{order.id}/disputes/{dispute_id}/evidence",
            headers=customer_headers,
            data={"description": "补充说明：已多次沟通仍未恢复履约。"},
        )
        assert supplement.status_code == 200, supplement.text
        assert len(supplement.json()["evidence"]) == 2

        detail = client.get(f"/api/v1/orders/{order.id}/detail", headers=customer_headers)
        assert detail.status_code == 200, detail.text
        assert detail.json()["disputes"][0]["status"] == "open"

    def test_admin_can_view_assign_and_resolve_dispute(
        self, client, db, customer_user, photographer_user, admin_user, admin_headers
    ):
        order = _funded_order(db, customer_user, photographer_user)
        dispute = open_order_dispute(
            db, order, customer_user.id, "service_failure", "无法继续履约。", "full_refund"
        )

        listed = client.get("/api/v1/admin/disputes", headers=admin_headers)
        assert listed.status_code == 200, listed.text
        assert listed.json()[0]["id"] == dispute.id

        assigned = client.put(
            f"/api/v1/admin/disputes/{dispute.id}/assign",
            headers=admin_headers,
            json={},
        )
        assert assigned.status_code == 200, assigned.text
        assert assigned.json()["assigned_admin_id"] == admin_user.id

        detail = client.get(f"/api/v1/admin/disputes/{dispute.id}", headers=admin_headers)
        assert detail.status_code == 200, detail.text
        assert detail.json()["order"]["id"] == order.id
        assert len(detail.json()["audit_logs"]) == 1

        resolved = client.put(
            f"/api/v1/admin/disputes/{dispute.id}/resolve",
            headers=admin_headers,
            json={
                "resolution": "full_refund",
                "resolution_note": "平台核查确认服务无法继续，退还全部人民币担保款。",
            },
        )
        assert resolved.status_code == 200, resolved.text
        assert resolved.json()["status"] == "resolved"
        assert resolved.json()["refund_amount"] == "1000.00"
