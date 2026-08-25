from datetime import date, datetime, timedelta, timezone

import pytest

from backend.app.models.notification import OrderNotification, OutboxEvent
from backend.app.models.order import Order, OrderStatus
from backend.app.models.order_event import OrderEvent
from backend.app.services.automation_service import (
    expire_unconfirmed_orders,
    process_order_reminders,
    refresh_order_action_metadata,
)
from backend.app.services.availability_service import DAY_NAMES_EN, list_bookable_slots, platform_today
from backend.app.services.notification_service import process_outbox_events
from backend.app.services.order_service import record_order_event


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _order(db, customer_user, photographer_user, status=OrderStatus.PENDING):
    item = Order(
        customer_id=customer_user.id,
        photographer_id=photographer_user.id,
        package_snapshot="阶段 F 自动化测试",
        appointment_time=_now() + timedelta(days=5),
        duration_minutes=60,
        status=status,
        payment_status="paid_in_escrow" if status != OrderStatus.PENDING else "unpaid",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def test_confirmation_timeout_closes_order_and_creates_outbox(db, customer_user, photographer_user):
    order = _order(db, customer_user, photographer_user)
    order.action_deadline_at = _now() - timedelta(minutes=1)
    db.commit()

    assert expire_unconfirmed_orders(db) == [order.id]
    db.refresh(order)
    assert order.status == OrderStatus.CANCELLED
    assert order.cancelled_by == "system"
    assert db.query(OrderEvent).filter(OrderEvent.event_type == "order_confirmation_expired").count() == 1
    assert db.query(OutboxEvent).filter(OutboxEvent.event_type == "order_confirmation_expired").count() == 1


@pytest.mark.asyncio
async def test_reminder_outbox_creates_notifications_once(db, customer_user, photographer_user):
    order = _order(db, customer_user, photographer_user, OrderStatus.DELIVERED)
    order.after_sales_status = "none"
    order.acceptance_deadline_at = _now() + timedelta(hours=24)
    refresh_order_action_metadata(db, order)
    db.commit()

    assert process_order_reminders(db) == [order.id]
    result = await process_outbox_events(db)
    assert result["sent"] == 1
    assert db.query(OrderNotification).filter(OrderNotification.order_id == order.id).count() == 2

    second = await process_outbox_events(db)
    assert second["processed"] == 0
    assert db.query(OrderNotification).filter(OrderNotification.order_id == order.id).count() == 2


@pytest.mark.asyncio
async def test_outbox_failure_is_retried(db, customer_user, photographer_user, monkeypatch):
    order = _order(db, customer_user, photographer_user, OrderStatus.CONFIRMED)
    event = record_order_event(db, order.id, None, "system", "order_reminder_sent", order.status, "请处理订单")
    db.commit()

    async def fail_send(*_args, **_kwargs):
        raise RuntimeError("websocket unavailable")

    monkeypatch.setattr("backend.app.services.notification_service.manager.send_personal_message", fail_send)
    failed = await process_outbox_events(db)
    assert failed["failed"] == 1
    outbox = db.query(OutboxEvent).filter(OutboxEvent.event_key == f"order-event:{event.id}").one()
    assert outbox.status == "failed"
    assert outbox.attempts == 1

    async def success_send(*_args, **_kwargs):
        return None

    monkeypatch.setattr("backend.app.services.notification_service.manager.send_personal_message", success_send)
    outbox.next_attempt_at = _now() - timedelta(seconds=1)
    db.commit()
    retried = await process_outbox_events(db)
    assert retried["sent"] == 1
    assert db.query(OrderNotification).filter(OrderNotification.order_id == order.id).count() == 2


@pytest.mark.asyncio
async def test_notification_api_lists_counts_and_marks_items_read(
    client,
    db,
    customer_user,
    photographer_user,
    customer_headers,
    photographer_headers,
):
    order = _order(db, customer_user, photographer_user, OrderStatus.CONFIRMED)
    record_order_event(
        db,
        order.id,
        photographer_user.id,
        "photographer",
        "confirmed",
        order.status,
        "Booking confirmed",
    )
    db.commit()
    result = await process_outbox_events(db)
    assert result["sent"] == 1

    count_response = client.get("/api/v1/notifications/unread-count", headers=customer_headers)
    assert count_response.status_code == 200
    assert count_response.json() == {"count": 1}

    list_response = client.get("/api/v1/notifications/?unread_only=true", headers=customer_headers)
    assert list_response.status_code == 200
    notifications = list_response.json()
    assert len(notifications) == 1
    assert notifications[0]["order_id"] == order.id
    assert notifications[0]["is_read"] is False

    notification_id = notifications[0]["id"]
    read_response = client.put(
        f"/api/v1/notifications/{notification_id}/read",
        headers=customer_headers,
    )
    assert read_response.status_code == 200
    assert read_response.json() == {"updated": 1}
    assert client.get(
        "/api/v1/notifications/unread-count",
        headers=customer_headers,
    ).json() == {"count": 0}

    photographer_count = client.get(
        "/api/v1/notifications/unread-count",
        headers=photographer_headers,
    )
    assert photographer_count.json() == {"count": 1}
    assert client.put(
        "/api/v1/notifications/read-all",
        headers=photographer_headers,
    ).json() == {"updated": 1}


def test_available_slots_api_uses_real_profile_schedule(
    client,
    db,
    photographer_user,
    photographer_profile,
):
    target_date = platform_today() + timedelta(days=7)
    photographer_profile.available_hours = [
        {"day": DAY_NAMES_EN[target_date.weekday()], "slots": ["09:00-12:00"]}
    ]
    photographer_profile.advance_notice = 0
    db.commit()

    response = client.get(
        f"/api/v1/photographers/{photographer_user.id}/available-slots",
        params={
            "start_date": target_date.isoformat(),
            "days": 1,
            "duration_minutes": 60,
            "buffer_minutes": 30,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["timezone"] == "Asia/Hong_Kong"
    assert body["days"][0]["date"] == target_date.isoformat()
    assert body["days"][0]["slots"]
    assert all(slot["start_at"].endswith("Z") for slot in body["days"][0]["slots"])


def test_order_chat_api_filters_by_order_and_rejects_outsiders(
    client,
    db,
    customer_user,
    photographer_user,
    customer_headers,
    admin_headers,
):
    selected_order = _order(db, customer_user, photographer_user, OrderStatus.CONFIRMED)
    other_order = _order(db, customer_user, photographer_user, OrderStatus.CONFIRMED)

    selected_response = client.post(
        "/api/v1/messages/",
        json={
            "receiver_id": photographer_user.id,
            "content": "Selected order message",
            "order_id": selected_order.id,
        },
        headers=customer_headers,
    )
    other_response = client.post(
        "/api/v1/messages/",
        json={
            "receiver_id": photographer_user.id,
            "content": "Other order message",
            "order_id": other_order.id,
        },
        headers=customer_headers,
    )
    assert selected_response.status_code == 201
    assert other_response.status_code == 201

    timeline_response = client.get(
        f"/api/v1/messages/conversation/{photographer_user.id}",
        params={"order_id": selected_order.id},
        headers=customer_headers,
    )
    assert timeline_response.status_code == 200
    timeline = timeline_response.json()
    assert [item["content"] for item in timeline if item["item_type"] == "message"] == [
        "Selected order message"
    ]
    assert all(item["order_id"] == selected_order.id for item in timeline)

    outsider_send = client.post(
        "/api/v1/messages/",
        json={
            "receiver_id": photographer_user.id,
            "content": "Unauthorized order message",
            "order_id": selected_order.id,
        },
        headers=admin_headers,
    )
    assert outsider_send.status_code == 403
    outsider_read = client.get(
        f"/api/v1/messages/conversation/{photographer_user.id}",
        params={"order_id": selected_order.id},
        headers=admin_headers,
    )
    assert outsider_read.status_code == 403


def test_created_order_response_contains_action_deadline(
    client,
    db,
    customer_headers,
    photographer_user,
    photographer_profile,
):
    appointment_time = (_now() + timedelta(days=20)).replace(second=0, microsecond=0)
    response = client.post(
        "/api/v1/orders/",
        json={
            "package_id": "package-test-1",
            "photographer_id": photographer_user.id,
            "appointment_time": appointment_time.isoformat(),
        },
        headers=customer_headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["action_required_by"] == "photographer"
    assert body["next_action_code"] == "confirm_booking"
    assert body["auto_action_code"] == "cancel_unconfirmed"
    assert body["action_deadline_at"] is not None

    order = db.query(Order).filter(Order.id == body["id"]).one()
    assert order.action_deadline_at - order.created_at == timedelta(hours=24)


def test_real_availability_excludes_existing_order_and_returns_timezone(
    db, customer_user, photographer_user, photographer_profile
):
    photographer_profile.available_hours = [{"day": "Monday", "slots": ["09:00-14:00"]}]
    photographer_profile.advance_notice = 0
    db.add(Order(
        customer_id=customer_user.id,
        photographer_id=photographer_user.id,
        package_snapshot="占用档期",
        appointment_time=datetime(2026, 7, 20, 2, 0),  # 香港时间 10:00
        duration_minutes=60,
        status=OrderStatus.CONFIRMED,
    ))
    db.commit()

    result = list_bookable_slots(
        db,
        photographer_profile,
        date(2026, 7, 20),
        days=1,
        duration_minutes=60,
        buffer_minutes=30,
    )
    labels = [slot["label"] for slot in result["days"][0]["slots"]]
    assert result["timezone"] == "Asia/Hong_Kong"
    assert "10:00–11:00" not in labels
    assert "12:00–13:00" in labels
