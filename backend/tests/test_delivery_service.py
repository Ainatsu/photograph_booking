from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from backend.app.models.order import Order, OrderStatus
from backend.app.models.order_delivery import OrderDelivery, OrderRevisionRequest
from backend.app.services.delivery_service import expire_acceptance_orders
from backend.app.services.order_service import OrderAction, get_order_detail, transition_order


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _in_progress_order(db, customer_user, photographer_user, included_revisions=1):
    order = Order(
        customer_id=customer_user.id,
        photographer_id=photographer_user.id,
        package_snapshot="阶段 D 测试方案",
        appointment_time=_now() + timedelta(days=2),
        duration_minutes=60,
        status=OrderStatus.IN_PROGRESS,
        included_revision_count=included_revisions,
        revision_used_count=0,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def _delivery_payload(key, url="/static/deliveries/v1.jpg", description="首次交付"):
    return {
        "delivery": {"images": [url], "description": description},
        "delivery_files": [{
            "file_url": url,
            "file_name": url.rsplit("/", 1)[-1],
            "file_type": "image/jpeg",
            "file_size": 128,
            "checksum": "a" * 64,
        }],
        "idempotency_key": key,
    }


class TestDeliveryLifecycle:
    def test_delivery_is_versioned_and_exposed_in_detail(self, db, customer_user, photographer_user):
        order = _in_progress_order(db, customer_user, photographer_user)

        transition_order(
            db,
            order=order,
            action=OrderAction.SUBMIT_DELIVERY,
            actor_id=photographer_user.id,
            payload=_delivery_payload("delivery-version-0001"),
        )
        detail = get_order_detail(db, order)

        assert order.status == OrderStatus.DELIVERED
        assert order.acceptance_deadline_at is not None
        assert detail["deliveries"][0]["version"] == 1
        assert detail["deliveries"][0]["status"] == "submitted"
        assert detail["deliveries"][0]["files"][0]["checksum"] == "a" * 64

    def test_revision_creates_v2_and_consumes_free_quota(self, db, customer_user, photographer_user):
        order = _in_progress_order(db, customer_user, photographer_user)
        transition_order(
            db,
            order=order,
            action=OrderAction.SUBMIT_DELIVERY,
            actor_id=photographer_user.id,
            payload=_delivery_payload("delivery-revision-0001"),
        )

        transition_order(
            db,
            order=order,
            action=OrderAction.REQUEST_REVISION,
            actor_id=customer_user.id,
            payload={
                "instructions": "请调整整体色温并减少锐化",
                "reference_files": [{"file_url": "/static/references/ref.jpg"}],
                "idempotency_key": "revision-request-0001",
            },
        )
        assert order.after_sales_status == "revision_requested"
        assert order.revision_used_count == 1
        assert order.acceptance_deadline_at is None

        expected_redelivery = _now() + timedelta(days=2)
        transition_order(
            db,
            order=order,
            action=OrderAction.ACKNOWLEDGE_REVISION,
            actor_id=photographer_user.id,
            payload={
                "revision_id": db.query(OrderRevisionRequest).filter(
                    OrderRevisionRequest.order_id == order.id
                ).one().id,
                "expected_redelivery_at": expected_redelivery,
            },
        )

        transition_order(
            db,
            order=order,
            action=OrderAction.SUBMIT_DELIVERY,
            actor_id=photographer_user.id,
            payload=_delivery_payload(
                "delivery-revision-0002",
                "/static/deliveries/v2.jpg",
                "已根据反馈调整",
            ),
        )
        deliveries = db.query(OrderDelivery).filter(OrderDelivery.order_id == order.id).order_by(OrderDelivery.version).all()
        revision = db.query(OrderRevisionRequest).filter(OrderRevisionRequest.order_id == order.id).one()

        assert [item.version for item in deliveries] == [1, 2]
        assert deliveries[0].status == "superseded"
        assert deliveries[1].status == "submitted"
        assert revision.status == "fulfilled"
        assert revision.expected_redelivery_at == expected_redelivery
        assert order.after_sales_status == "none"
        assert order.acceptance_deadline_at is not None

    def test_revision_quota_is_enforced(self, db, customer_user, photographer_user):
        order = _in_progress_order(db, customer_user, photographer_user, included_revisions=0)
        transition_order(
            db,
            order=order,
            action=OrderAction.SUBMIT_DELIVERY,
            actor_id=photographer_user.id,
            payload=_delivery_payload("delivery-no-revision-0001"),
        )

        with pytest.raises(HTTPException) as exc:
            transition_order(
                db,
                order=order,
                action=OrderAction.REQUEST_REVISION,
                actor_id=customer_user.id,
                payload={
                    "instructions": "申请额外修改",
                    "idempotency_key": "revision-over-quota-0001",
                },
            )
        assert exc.value.status_code == 409

    def test_manual_acceptance_completes_order_and_review_is_optional(self, db, customer_user, photographer_user):
        order = _in_progress_order(db, customer_user, photographer_user)
        transition_order(
            db,
            order=order,
            action=OrderAction.SUBMIT_DELIVERY,
            actor_id=photographer_user.id,
            payload=_delivery_payload("delivery-accept-0001"),
        )
        transition_order(db, order=order, action=OrderAction.ACCEPT_DELIVERY, actor_id=customer_user.id)

        assert order.status == OrderStatus.COMPLETED
        assert order.completion_type == "manual"
        assert order.completed_at is not None
        assert order.rating is None

        transition_order(
            db,
            order=order,
            action=OrderAction.SUBMIT_REVIEW,
            actor_id=customer_user.id,
            payload={"rating": 9, "review_text": "交付质量很好"},
        )
        assert order.status == OrderStatus.COMPLETED
        assert order.rating == 9

    def test_auto_acceptance_pauses_for_revision_and_is_idempotent(self, db, customer_user, photographer_user):
        order = _in_progress_order(db, customer_user, photographer_user)
        transition_order(
            db,
            order=order,
            action=OrderAction.SUBMIT_DELIVERY,
            actor_id=photographer_user.id,
            payload=_delivery_payload("delivery-auto-0001"),
        )
        order.acceptance_deadline_at = _now() - timedelta(minutes=1)
        order.after_sales_status = "revision_requested"
        db.commit()
        assert expire_acceptance_orders(db, order.id) == []

        order.after_sales_status = "none"
        db.commit()
        assert expire_acceptance_orders(db, order.id) == [order.id]
        db.refresh(order)
        assert order.status == OrderStatus.COMPLETED
        assert order.completion_type == "automatic"
        assert expire_acceptance_orders(db, order.id) == []

    def test_delivery_and_revision_idempotency_do_not_duplicate_records(self, db, customer_user, photographer_user):
        order = _in_progress_order(db, customer_user, photographer_user)
        payload = _delivery_payload("delivery-idempotent-0001")
        transition_order(db, order=order, action=OrderAction.SUBMIT_DELIVERY, actor_id=photographer_user.id, payload=payload)
        transition_order(db, order=order, action=OrderAction.SUBMIT_DELIVERY, actor_id=photographer_user.id, payload=payload)
        assert db.query(OrderDelivery).filter(OrderDelivery.order_id == order.id).count() == 1

        revision_payload = {
            "instructions": "统一调整肤色",
            "idempotency_key": "revision-idempotent-0001",
        }
        transition_order(db, order=order, action=OrderAction.REQUEST_REVISION, actor_id=customer_user.id, payload=revision_payload)
        transition_order(db, order=order, action=OrderAction.REQUEST_REVISION, actor_id=customer_user.id, payload=revision_payload)
        assert db.query(OrderRevisionRequest).filter(OrderRevisionRequest.order_id == order.id).count() == 1
        assert order.revision_used_count == 1


class TestDeliveryAPI:
    def test_delivery_and_revision_endpoints_return_version_history(
        self,
        client,
        db,
        customer_user,
        photographer_user,
        customer_headers,
        photographer_headers,
    ):
        order = _in_progress_order(db, customer_user, photographer_user)
        delivery_response = client.post(
            f"/api/v1/orders/{order.id}/deliver",
            data={"description": "API V1", "idempotency_key": "delivery-api-stage-d-0001"},
            files={"files": ("v1.jpg", b"stage-d-image", "image/jpeg")},
            headers=photographer_headers,
        )
        assert delivery_response.status_code == 200
        assert delivery_response.json()["status"] == "delivered"

        revision_response = client.post(
            f"/api/v1/orders/{order.id}/revision",
            data={"instructions": "请降低对比度", "idempotency_key": "revision-api-stage-d-0001"},
            files={"files": ("reference.jpg", b"reference-image", "image/jpeg")},
            headers=customer_headers,
        )
        assert revision_response.status_code == 200
        assert revision_response.json()["after_sales_status"] == "revision_requested"

        revision_id = db.query(OrderRevisionRequest).filter(OrderRevisionRequest.order_id == order.id).one().id
        acknowledge_response = client.put(
            f"/api/v1/orders/{order.id}/revision/{revision_id}/acknowledge",
            json={"expected_redelivery_at": (_now() + timedelta(days=2)).isoformat()},
            headers=photographer_headers,
        )
        assert acknowledge_response.status_code == 200

        detail = client.get(f"/api/v1/orders/{order.id}/detail", headers=customer_headers)
        assert detail.status_code == 200
        payload = detail.json()
        assert payload["deliveries"][0]["version"] == 1
        assert len(payload["deliveries"][0]["files"][0]["checksum"]) == 64
        assert payload["revision_requests"][0]["reference_files"][0]["file_name"] == "reference.jpg"
        assert payload["revision_requests"][0]["expected_redelivery_at"] is not None
