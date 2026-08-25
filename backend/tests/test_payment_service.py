from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy.orm.attributes import flag_modified

from backend.app.models.order import OrderStatus
from backend.app.models.payment import PaymentStatus, Refund, Settlement
from backend.app.schemas.order import OrderCreateRequest
from backend.app.schemas.payment import PaymentCallbackRequest
from backend.app.services.order_service import OrderAction, create_order, transition_order
from backend.app.services.payment_service import (
    available_escrow_amount,
    create_payment,
    expire_payment_orders,
    mock_confirm_payment,
    payment_signature,
    process_payment_callback,
)


def _future_time(days: int = 10) -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=days)


def _create_package_order(db, customer_user, photographer_user, appointment_time=None):
    return create_order(
        db,
        customer_user.id,
        OrderCreateRequest(
            package_id="package-test-1",
            photographer_id=photographer_user.id,
            appointment_time=appointment_time or _future_time(),
        ),
    )


def _accept_for_payment(db, order, photographer_user):
    return transition_order(
        db,
        order=order,
        action=OrderAction.ACCEPT_BOOKING,
        actor_id=photographer_user.id,
    )


def _pay(db, order, customer_user, key="payment-key-0001"):
    payment = create_payment(db, order, customer_user.id, key)
    db.commit()
    return mock_confirm_payment(db, payment)


class TestPaymentAndEscrow:
    def test_provider_acceptance_moves_structured_order_to_payment(
        self, db, customer_user, photographer_user, photographer_profile
    ):
        order = _create_package_order(db, customer_user, photographer_user)

        order = _accept_for_payment(db, order, photographer_user)

        assert order.status == OrderStatus.AWAITING_PAYMENT
        assert order.payment_status == "unpaid"
        assert order.payment_due_at is not None

    def test_full_payment_callback_confirms_order_and_freezes_cny_funds(
        self, db, customer_user, photographer_user, photographer_profile
    ):
        order = _accept_for_payment(
            db,
            _create_package_order(db, customer_user, photographer_user),
            photographer_user,
        )
        payment = create_payment(db, order, customer_user.id, "payment-full-0001")
        db.commit()

        paid = mock_confirm_payment(db, payment, "provider-full-0001")
        db.refresh(order)

        assert paid.status == PaymentStatus.SUCCEEDED.value
        assert paid.amount == Decimal("699.00")
        assert paid.currency == "CNY"
        assert order.status == OrderStatus.CONFIRMED
        assert order.payment_status == "paid_in_escrow"
        assert order.escrow_amount == Decimal("699.00")

    def test_payment_creation_and_callback_are_idempotent(
        self, db, customer_user, photographer_user, photographer_profile
    ):
        order = _accept_for_payment(
            db,
            _create_package_order(db, customer_user, photographer_user),
            photographer_user,
        )
        first = create_payment(db, order, customer_user.id, "payment-idempotent-0001")
        db.commit()
        second = create_payment(db, order, customer_user.id, "payment-idempotent-0001")
        assert second.id == first.id

        paid = mock_confirm_payment(db, first, "provider-idempotent-0001")
        duplicate = mock_confirm_payment(db, first, "provider-idempotent-0001")
        assert duplicate.id == paid.id
        assert order.status == OrderStatus.CONFIRMED

    def test_callback_rejects_invalid_signature(
        self, db, customer_user, photographer_user, photographer_profile
    ):
        order = _accept_for_payment(
            db,
            _create_package_order(db, customer_user, photographer_user),
            photographer_user,
        )
        payment = create_payment(db, order, customer_user.id, "payment-signature-0001")
        db.commit()
        data = PaymentCallbackRequest(
            payment_no=payment.payment_no,
            provider_transaction_id="provider-signature-0001",
            amount=payment.amount,
            currency="CNY",
            status="succeeded",
            signature="invalid",
        )

        with pytest.raises(HTTPException) as exc:
            process_payment_callback(db, data)
        assert exc.value.status_code == 400
        assert "签名" in exc.value.detail

    def test_callback_rejects_non_cny_currency(
        self, db, customer_user, photographer_user, photographer_profile
    ):
        order = _accept_for_payment(
            db,
            _create_package_order(db, customer_user, photographer_user),
            photographer_user,
        )
        payment = create_payment(db, order, customer_user.id, "payment-currency-0001")
        db.commit()
        transaction_id = "provider-currency-0001"
        data = PaymentCallbackRequest(
            payment_no=payment.payment_no,
            provider_transaction_id=transaction_id,
            amount=payment.amount,
            currency="USD",
            status="succeeded",
            signature=payment_signature(payment.payment_no, transaction_id, payment.amount, "USD", "succeeded"),
        )

        with pytest.raises(HTTPException) as exc:
            process_payment_callback(db, data)
        assert exc.value.status_code == 400
        assert "人民币" in exc.value.detail

    def test_failed_payment_does_not_confirm_order(
        self, db, customer_user, photographer_user, photographer_profile
    ):
        order = _accept_for_payment(
            db,
            _create_package_order(db, customer_user, photographer_user),
            photographer_user,
        )
        payment = create_payment(db, order, customer_user.id, "payment-failed-0001")
        db.commit()
        transaction_id = "provider-failed-0001"
        failed = process_payment_callback(
            db,
            PaymentCallbackRequest(
                payment_no=payment.payment_no,
                provider_transaction_id=transaction_id,
                amount=payment.amount,
                currency="CNY",
                status="failed",
                signature=payment_signature(
                    payment.payment_no,
                    transaction_id,
                    payment.amount,
                    "CNY",
                    "failed",
                ),
            ),
        )
        db.refresh(order)

        assert failed.status == "failed"
        assert order.status == OrderStatus.AWAITING_PAYMENT
        assert order.payment_status == "payment_failed"

    def test_payment_timeout_cancels_order_and_releases_slot(
        self, db, customer_user, photographer_user, photographer_profile
    ):
        appointment_time = _future_time()
        order = _accept_for_payment(
            db,
            _create_package_order(db, customer_user, photographer_user, appointment_time),
            photographer_user,
        )
        payment = create_payment(db, order, customer_user.id, "payment-timeout-0001")
        payment.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
        db.commit()

        expired_order_ids = expire_payment_orders(db)
        db.refresh(order)

        assert expired_order_ids == [order.id]
        assert order.status == OrderStatus.CANCELLED
        assert order.cancelled_by == "system"
        assert "支付超时" in order.cancellation_reason

        replacement = _create_package_order(
            db,
            customer_user,
            photographer_user,
            appointment_time,
        )
        assert replacement.status == OrderStatus.PENDING

    def test_payment_window_expires_even_when_customer_never_created_payment(
        self, db, customer_user, photographer_user, photographer_profile
    ):
        appointment_time = _future_time()
        order = _accept_for_payment(
            db,
            _create_package_order(db, customer_user, photographer_user, appointment_time),
            photographer_user,
        )
        order.payment_due_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
        db.commit()

        expired_order_ids = expire_payment_orders(db)
        db.refresh(order)

        assert expired_order_ids == [order.id]
        assert order.status == OrderStatus.CANCELLED
        assert order.cancelled_by == "system"

    def test_deposit_and_balance_are_both_supported(
        self, db, customer_user, photographer_user, photographer_profile
    ):
        packages = [dict(item) for item in photographer_profile.packages]
        packages[0]["payment_mode"] = "deposit_balance"
        packages[0]["deposit_rate"] = 0.30
        photographer_profile.packages = packages
        flag_modified(photographer_profile, "packages")
        db.commit()

        order = _accept_for_payment(
            db,
            _create_package_order(db, customer_user, photographer_user),
            photographer_user,
        )
        deposit = create_payment(db, order, customer_user.id, "payment-deposit-0001")
        db.commit()
        mock_confirm_payment(db, deposit, "provider-deposit-0001")
        db.refresh(order)

        assert deposit.purpose == "deposit"
        assert deposit.amount == Decimal("209.70")
        assert order.status == OrderStatus.CONFIRMED
        assert order.payment_status == "deposit_paid"

        with pytest.raises(HTTPException) as exc:
            transition_order(
                db,
                order=order,
                action=OrderAction.START_SERVICE,
                actor_id=photographer_user.id,
            )
        assert "全额支付" in exc.value.detail

        balance = create_payment(db, order, customer_user.id, "payment-balance-0001")
        db.commit()
        mock_confirm_payment(db, balance, "provider-balance-0001")
        db.refresh(order)
        assert balance.purpose == "balance"
        assert balance.amount == Decimal("489.30")
        assert order.payment_status == "paid_in_escrow"

    def test_customer_cancellation_uses_time_based_refund_policy(
        self, db, customer_user, photographer_user, photographer_profile
    ):
        order = _accept_for_payment(
            db,
            _create_package_order(db, customer_user, photographer_user, _future_time(10)),
            photographer_user,
        )
        _pay(db, order, customer_user, "payment-refund-0001")
        db.refresh(order)

        transition_order(
            db,
            order=order,
            action=OrderAction.CANCEL_ORDER,
            actor_id=customer_user.id,
            payload={"reason": "客户行程变化"},
        )
        refund = db.query(Refund).filter(Refund.order_id == order.id).one()

        assert refund.amount == Decimal("629.10")
        assert refund.currency == "CNY"
        assert refund.status == "succeeded"
        assert order.payment_status == "partially_refunded"
        assert order.escrow_amount == Decimal("69.90")

    def test_acceptance_settles_escrow_after_delivery(
        self, db, customer_user, photographer_user, photographer_profile
    ):
        order = _accept_for_payment(
            db,
            _create_package_order(db, customer_user, photographer_user),
            photographer_user,
        )
        _pay(db, order, customer_user, "payment-settlement-0001")
        db.refresh(order)
        transition_order(db, order=order, action=OrderAction.START_SERVICE, actor_id=photographer_user.id)
        transition_order(
            db,
            order=order,
            action=OrderAction.SUBMIT_DELIVERY,
            actor_id=photographer_user.id,
            payload={"delivery": {"images": ["/static/test.jpg"], "description": "已交付"}},
        )
        transition_order(db, order=order, action=OrderAction.ACCEPT_DELIVERY, actor_id=customer_user.id)
        settlement = db.query(Settlement).filter(Settlement.order_id == order.id).one()

        assert settlement.status == "settled"
        assert settlement.gross_amount == Decimal("699.00")
        assert settlement.platform_fee_amount == Decimal("69.90")
        assert settlement.net_amount == Decimal("629.10")
        assert order.payment_status == "settled"
        assert order.escrow_amount == Decimal("0.00")
        assert available_escrow_amount(db, order) == Decimal("0.00")

    def test_settled_order_cannot_be_cancelled_and_refunded_again(
        self, db, customer_user, photographer_user, photographer_profile
    ):
        order = _accept_for_payment(
            db,
            _create_package_order(db, customer_user, photographer_user),
            photographer_user,
        )
        _pay(db, order, customer_user, "payment-settlement-cancel-0001")
        db.refresh(order)
        transition_order(db, order=order, action=OrderAction.START_SERVICE, actor_id=photographer_user.id)
        transition_order(
            db,
            order=order,
            action=OrderAction.SUBMIT_DELIVERY,
            actor_id=photographer_user.id,
            payload={"delivery": {"images": ["/static/test.jpg"]}},
        )
        transition_order(db, order=order, action=OrderAction.ACCEPT_DELIVERY, actor_id=customer_user.id)

        with pytest.raises(HTTPException) as exc:
            transition_order(
                db,
                order=order,
                action=OrderAction.ADMIN_CANCEL_ORDER,
                actor_id=customer_user.id,
                actor_role="admin",
                payload={"reason": "结算后错误取消"},
            )

        assert exc.value.status_code == 400
        db.refresh(order)
        assert order.status == OrderStatus.COMPLETED
        assert db.query(Refund).filter(Refund.order_id == order.id).count() == 0

    def test_after_sales_status_freezes_settlement(
        self, db, customer_user, photographer_user, photographer_profile
    ):
        order = _accept_for_payment(
            db,
            _create_package_order(db, customer_user, photographer_user),
            photographer_user,
        )
        _pay(db, order, customer_user, "payment-freeze-0001")
        db.refresh(order)
        transition_order(db, order=order, action=OrderAction.START_SERVICE, actor_id=photographer_user.id)
        transition_order(
            db,
            order=order,
            action=OrderAction.SUBMIT_DELIVERY,
            actor_id=photographer_user.id,
            payload={"delivery": {"images": ["/static/test.jpg"]}},
        )
        order.after_sales_status = "dispute_open"
        db.commit()

        with pytest.raises(HTTPException) as exc:
            transition_order(db, order=order, action=OrderAction.ACCEPT_DELIVERY, actor_id=customer_user.id)
        assert exc.value.status_code == 409
        assert db.query(Settlement).filter(Settlement.order_id == order.id).count() == 0


class TestPaymentAPI:
    def test_customer_can_create_and_mock_confirm_payment(
        self,
        client,
        db,
        customer_user,
        photographer_user,
        photographer_profile,
        customer_headers,
    ):
        order = _accept_for_payment(
            db,
            _create_package_order(db, customer_user, photographer_user),
            photographer_user,
        )

        create_res = client.post(
            f"/api/v1/payments/orders/{order.id}",
            json={"idempotency_key": "payment-api-0001"},
            headers=customer_headers,
        )
        assert create_res.status_code == 201
        payment = create_res.json()
        assert payment["currency"] == "CNY"
        assert payment["amount"] == "699.00"

        pay_res = client.post(
            f"/api/v1/payments/{payment['id']}/mock-confirm",
            json={"provider_transaction_id": "provider-api-0001"},
            headers=customer_headers,
        )
        assert pay_res.status_code == 200

        summary_res = client.get(
            f"/api/v1/payments/orders/{order.id}",
            headers=customer_headers,
        )
        assert summary_res.status_code == 200
        summary = summary_res.json()
        assert summary["payment_status"] == "paid_in_escrow"
        assert summary["escrow_amount"] == "699.00"

    def test_admin_finance_endpoints_expose_payment_refund_and_settlement_records(
        self,
        client,
        db,
        customer_user,
        photographer_user,
        photographer_profile,
        admin_headers,
    ):
        order = _accept_for_payment(
            db,
            _create_package_order(db, customer_user, photographer_user, _future_time(10)),
            photographer_user,
        )
        _pay(db, order, customer_user, "payment-admin-finance-0001")
        db.refresh(order)
        transition_order(
            db,
            order=order,
            action=OrderAction.CANCEL_ORDER,
            actor_id=customer_user.id,
            payload={"reason": "财务记录测试"},
        )

        payments_res = client.get("/api/v1/admin/finance/payments", headers=admin_headers)
        refunds_res = client.get("/api/v1/admin/finance/refunds", headers=admin_headers)
        settlements_res = client.get("/api/v1/admin/finance/settlements", headers=admin_headers)

        assert payments_res.status_code == 200
        assert payments_res.json()[0]["currency"] == "CNY"
        assert refunds_res.status_code == 200
        assert refunds_res.json()[0]["order_id"] == order.id
        assert settlements_res.status_code == 200
        assert settlements_res.json() == []
