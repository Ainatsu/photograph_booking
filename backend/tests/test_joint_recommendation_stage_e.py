from copy import deepcopy
from datetime import date, datetime, timedelta
from time import perf_counter

import pytest
from fastapi import HTTPException
from sqlalchemy import event

from backend.app.core.cache import cache_get, cache_set, distributed_lock
from backend.app.core.config import settings
from backend.app.schemas.order import OrderCreateRequest
from backend.app.schemas.recommendation import PackageRecommendationQuery
from backend.app.services.joint_recommendation_gate import is_joint_recommendation_enabled
from backend.app.services.order_service import create_order
from backend.app.services.package_recommendation_service import recommend_packages
from backend.app.services.recommendation_metrics_service import algorithm_funnel_metrics
from backend.app.services.photographer_service import create_or_update_profile
from backend.app.models.analytics import AnalyticsEvent


def _future_saturday() -> date:
    return date.today() + timedelta(days=(5 - date.today().weekday()) % 7 + 14)


def test_joint_ranking_rollout_gate_is_deterministic(monkeypatch):
    monkeypatch.setattr(settings, "JOINT_RECOMMENDATION_ENABLED", True)
    monkeypatch.setattr(settings, "JOINT_RECOMMENDATION_ROLLOUT_PERCENT", 35)
    first = is_joint_recommendation_enabled("viewer-42")
    assert is_joint_recommendation_enabled("viewer-42") is first
    monkeypatch.setattr(settings, "JOINT_RECOMMENDATION_ROLLOUT_PERCENT", 0)
    assert is_joint_recommendation_enabled("viewer-42") is False
    monkeypatch.setattr(settings, "JOINT_RECOMMENDATION_ROLLOUT_PERCENT", 100)
    assert is_joint_recommendation_enabled("viewer-42") is True


def test_joint_recommendation_query_count_and_latency_budget(db, photographer_profile):
    template = deepcopy(photographer_profile.packages[0])
    photographer_profile.packages = [
        {**deepcopy(template), "id": f"benchmark-{index}", "name": f"基准套餐 {index}", "price": 500 + index}
        for index in range(120)
    ]
    photographer_profile.available_hours = [{"day": "周六", "slots": ["09:00-18:00"]}]
    db.commit()
    statements = 0

    def count_statements(*_args):
        nonlocal statements
        statements += 1

    event.listen(db.bind, "before_cursor_execute", count_statements)
    started = perf_counter()
    try:
        result = recommend_packages(
            db, None, None, 20,
            PackageRecommendationQuery(
                shoot_date=_future_saturday(), duration_minutes=120,
                require_exact_availability=True, styles=["日系"],
            ),
            "stage-e-benchmark",
        )
    finally:
        event.remove(db.bind, "before_cursor_execute", count_statements)
    elapsed_ms = (perf_counter() - started) * 1000
    assert result["items"]
    assert statements < 30
    assert elapsed_ms < 800
    assert result["observability"]["candidate_count_before_filters"] == 120
    assert result["observability"]["availability_query_ms"] >= 0
    assert result["observability"]["ranking_ms"] >= result["observability"]["availability_query_ms"]


def test_order_creation_invalidates_joint_recommendation_cache(db, customer_user, photographer_user):
    cache_set("rec:packages:test-order-invalidation", {"stale": True}, ttl=300)
    assert cache_get("rec:packages:test-order-invalidation") == {"stale": True}
    create_order(db, customer_user.id, OrderCreateRequest(
        photographer_id=photographer_user.id,
        package_description="缓存失效测试",
        appointment_time=datetime(2026, 8, 1, 10, 0),
        duration_minutes=60,
    ))
    assert cache_get("rec:packages:test-order-invalidation") is None


def test_schedule_update_invalidates_joint_recommendation_cache(db, photographer_profile):
    cache_set("rec:packages:test-schedule-invalidation", {"stale": True}, ttl=300)
    create_or_update_profile(db, photographer_profile.user_id, {
        "available_hours": [{"day": "周六", "slots": ["10:00-16:00"]}],
    })
    assert cache_get("rec:packages:test-schedule-invalidation") is None


def test_competing_booking_is_rejected_while_photographer_lock_is_held(db, customer_user, photographer_user):
    payload = OrderCreateRequest(
        photographer_id=photographer_user.id,
        package_description="并发预约测试",
        appointment_time=datetime(2026, 8, 2, 10, 0),
        duration_minutes=60,
    )
    with distributed_lock(f"booking-create:{photographer_user.id}") as acquired:
        assert acquired is True
        with pytest.raises(HTTPException) as exc:
            create_order(db, customer_user.id, payload)
        assert exc.value.status_code == 409
    assert create_order(db, customer_user.id, payload).id is not None


def test_algorithm_funnel_metrics_compare_legacy_and_joint(db, customer_user, photographer_user):
    for event_type in ("joint_rec_impression", "joint_rec_open", "joint_rec_booking_start", "joint_rec_booking_success"):
        db.add(AnalyticsEvent(
            user_id=photographer_user.id, actor_id=customer_user.id, event_type=event_type,
            target_type="package", target_id="joint-package",
            event_metadata={"algorithm_version": "package_rec_v2_joint_availability"},
        ))
    for event_type in ("package_impression", "package_click", "package_booking_intent"):
        db.add(AnalyticsEvent(
            user_id=photographer_user.id, actor_id=customer_user.id, event_type=event_type,
            target_type="package", target_id="legacy-package",
            event_metadata={"algorithm_version": "package_hybrid_v1"},
        ))
    db.commit()
    metrics = {item["algorithm_version"]: item for item in algorithm_funnel_metrics(db)}
    assert metrics["package_rec_v2_joint_availability"]["open_rate"] == 1.0
    assert metrics["package_rec_v2_joint_availability"]["booking_success_rate"] == 1.0
    assert metrics["package_hybrid_v1"]["booking_start_rate"] == 1.0
