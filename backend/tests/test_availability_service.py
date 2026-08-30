from datetime import date, datetime, time, timedelta
from types import SimpleNamespace

from sqlalchemy import event

from backend.app.services.availability_service import batch_list_bookable_slots, compute_bookable_slots


def _future_saturday() -> date:
    today = date.today()
    return today + timedelta(days=(5 - today.weekday()) % 7 + 14)


def test_compute_bookable_slots_returns_date_level_availability(photographer_profile):
    target = _future_saturday()
    result = compute_bookable_slots(photographer_profile, target, 1, 120, [])
    day = result["days"][0]
    assert day["bookable"] is True
    assert day["slots"] == [{"date": target.isoformat(), "label": "可预约"}]
    assert all("start_at" not in slot and "end_at" not in slot for slot in day["slots"])


def test_batch_availability_loads_orders_once(db, photographer_profile):
    target = _future_saturday()
    db.commit()
    order_selects = 0

    def count_orders(_conn, _cursor, statement, _parameters, _context, _executemany):
        nonlocal order_selects
        if statement.lstrip().upper().startswith("SELECT") and "FROM orders" in statement:
            order_selects += 1

    event.listen(db.get_bind(), "before_cursor_execute", count_orders)
    try:
        results = batch_list_bookable_slots(db, [
            {"key": "short", "profile": photographer_profile, "start_date": target, "duration_minutes": 60},
            {"key": "long", "profile": photographer_profile, "start_date": target, "duration_minutes": 180},
        ])
    finally:
        event.remove(db.get_bind(), "before_cursor_execute", count_orders)
    assert order_selects == 1
    assert results["short"]["days"][0]["bookable"] is True
    assert results["long"]["days"][0]["bookable"] is True
    assert results["short"]["days"][0]["slots"] == results["long"]["days"][0]["slots"]


def test_compute_bookable_slots_marks_busy_date(photographer_profile):
    target = _future_saturday()
    photographer_profile.availability_exceptions = [
        {"date": target.isoformat(), "status": "busy"},
    ]

    day = compute_bookable_slots(photographer_profile, target, 1, 120, [])["days"][0]

    assert day["bookable"] is False
    assert day["slots"] == []
    assert day["unavailable_reason"] == "摄影师已标记全天不可预约"


def test_compute_bookable_slots_uses_daily_booking_limit(photographer_profile):
    target = _future_saturday()
    photographer_profile.max_daily_bookings = 1
    order = SimpleNamespace(
        appointment_time=datetime.combine(target, time(12)),
        duration_minutes=120,
    )

    day = compute_bookable_slots(photographer_profile, target, 1, 120, [order])["days"][0]

    assert day["bookable"] is False
    assert day["unavailable_reason"] == "当日预约数量已满"
