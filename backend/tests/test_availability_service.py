from datetime import date, timedelta

from sqlalchemy import event

from backend.app.services.availability_service import batch_list_bookable_slots, compute_bookable_slots


def _future_saturday() -> date:
    today = date.today()
    return today + timedelta(days=(5 - today.weekday()) % 7 + 14)


def test_compute_bookable_slots_respects_weekly_hours(photographer_profile):
    target = _future_saturday()
    photographer_profile.available_hours = [{"day": "周六", "slots": ["14:00-18:00"]}]
    result = compute_bookable_slots(photographer_profile, target, 1, 120, [])
    labels = [slot["label"] for slot in result["days"][0]["slots"]]
    assert "14:00–16:00" in labels
    assert all(not label.startswith("09:") for label in labels)


def test_batch_availability_loads_orders_once(db, photographer_profile):
    target = _future_saturday()
    photographer_profile.available_hours = [{"day": "周六", "slots": ["09:00-18:00"]}]
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
    assert len(results["short"]["days"][0]["slots"]) > len(results["long"]["days"][0]["slots"])
