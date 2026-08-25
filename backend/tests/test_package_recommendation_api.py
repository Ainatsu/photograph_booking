from backend.app.models.analytics import AnalyticsEvent
from backend.app.models.like import Like
from backend.app.models.recommendation import RecommendationExposure, RecommendationItemStats
from backend.app.services.photographer_service import _fix_missing_ids
from datetime import date, timedelta


def _package_id(db, photographer_profile):
    _fix_missing_ids(db)
    db.refresh(photographer_profile)
    return photographer_profile.packages[0]["id"]


def test_package_recommendation_returns_valid_packages(client, db, photographer_profile):
    package_id = _package_id(db, photographer_profile)
    response = client.get("/api/v1/recommendations/packages", params={"session_id": "package-session"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["algorithm_version"] == "package_hybrid_v1"
    assert [item["id"] for item in payload["items"]] == [package_id]
    assert payload["items"][0]["recommendation_reason"]
    assert payload["items"][0]["distance_km"] is None
    assert payload["items"][0]["distance_confidence"] == "unknown"
    assert db.query(RecommendationItemStats).filter_by(target_type="package").count() == 1


def test_package_recommendation_filters_city_and_budget(client, photographer_profile):
    matched = client.get("/api/v1/recommendations/packages", params={"city": "北京", "budget_min": 500, "budget_max": 900, "styles": "日系", "session_id": "matched"})
    assert matched.status_code == 200
    assert len(matched.json()["items"]) == 1
    assert matched.json()["items"][0]["candidate_source"] == "requirement_match"

    excluded = client.get("/api/v1/recommendations/packages", params={"city": "上海", "budget_max": 300, "session_id": "excluded"})
    assert excluded.status_code == 200
    assert excluded.json()["items"] == []


def test_package_recommendation_requires_paired_time_window(client):
    response = client.get("/api/v1/recommendations/packages", params={"time_start": "14:00"})
    assert response.status_code == 422


def test_package_recommendation_strict_budget_is_a_hard_limit(client, photographer_profile):
    response = client.get("/api/v1/recommendations/packages", params={"budget_max": 600, "budget_strict": "true"})
    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["no_result"] is True


def test_joint_recommendation_relaxes_style_first(client, photographer_profile):
    target = date.today() + timedelta(days=14)
    response = client.get("/api/v1/recommendations/packages", params={
        "shoot_date": target.isoformat(), "styles": "水下超现实", "budget_max": 800,
        "session_id": "style-fallback",
    })
    assert response.status_code == 200
    payload = response.json()
    assert payload["items"]
    assert payload["fallback_level"] == 1
    assert payload["relaxations"] == [{"code": "style_similarity", "label": "已放宽风格相似度"}]


def test_joint_recommendation_only_relaxes_budget_when_not_strict(client, photographer_profile):
    target = date.today() + timedelta(days=14)
    response = client.get("/api/v1/recommendations/packages", params={
        "shoot_date": target.isoformat(), "date_strict": "true", "budget_max": 650,
        "session_id": "budget-fallback",
    })
    assert response.status_code == 200
    payload = response.json()
    assert payload["fallback_level"] == 5
    assert payload["items"][0]["warnings"] == ["超出预算 49 元"]

    strict = client.get("/api/v1/recommendations/packages", params={
        "shoot_date": target.isoformat(), "date_strict": "true", "budget_max": 650,
        "budget_strict": "true", "session_id": "budget-strict-fallback",
    })
    assert strict.status_code == 200
    assert strict.json()["items"] == []
    assert strict.json()["fallback_level"] == 0


def test_joint_recommendation_relaxations_are_cumulative(client, db, photographer_profile):
    photographer_profile.service_latitude = 39.9042
    photographer_profile.service_longitude = 116.4074
    db.commit()
    target = date.today() + timedelta(days=14)
    response = client.get("/api/v1/recommendations/packages", params={
        "shoot_date": target.isoformat(), "styles": "水下超现实", "max_distance_km": 5,
        "latitude": 39.98, "longitude": 116.4074, "session_id": "cumulative-fallback",
    })
    assert response.status_code == 200
    payload = response.json()
    assert payload["fallback_level"] == 2
    assert [item["code"] for item in payload["relaxations"]] == ["style_similarity", "max_distance_km"]


def test_package_recommendation_returns_exact_availability_and_distance(client, db, photographer_profile):
    photographer_profile.service_city = "北京"
    photographer_profile.service_latitude = 39.9042
    photographer_profile.service_longitude = 116.4074
    photographer_profile.available_hours = [{"day": "周六", "slots": ["09:00-18:00"]}]
    db.commit()
    # Use a future Saturday so the default advance notice does not remove the slots.
    from datetime import date, timedelta
    target = date.today() + timedelta(days=(5 - date.today().weekday()) % 7 + 14)
    response = client.get("/api/v1/recommendations/packages", params={
        "shoot_date": target.isoformat(), "time_start": "14:00", "time_end": "18:00",
        "duration_minutes": 120, "latitude": 39.9042, "longitude": 116.4074,
        "require_exact_availability": "true", "session_id": "exact",
    })
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["distance_km"] == 0
    assert item["distance_confidence"] == "exact"
    assert item["availability"]["matching_slots"]
    assert item["match"]["overall_score"] <= 1


def test_package_recommendation_uses_work_style_history(client, db, customer_user, customer_headers, photographer_profile):
    _fix_missing_ids(db)
    db.refresh(photographer_profile)
    db.add(Like(user_id=customer_user.id, target_type="portfolio", target_id=photographer_profile.portfolio[0]["id"]))
    db.commit()
    response = client.get("/api/v1/recommendations/packages", headers=customer_headers)
    assert response.status_code == 200
    assert response.json()["items"][0]["candidate_source"] in {"style_affinity", "photographer_affinity"}


def test_package_impression_tracks_authenticated_viewer(client, db, customer_user, customer_headers, photographer_profile):
    package_id = _package_id(db, photographer_profile)
    payload = {"events": [{"event_type": "package_impression", "target_type": "package", "target_id": package_id, "owner_user_id": photographer_profile.user_id, "recommendation_id": "package-rec", "session_id": "package-session", "scene": "gallery_packages", "position": 0, "algorithm_version": "package_hybrid_v1", "candidate_source": "popular_package"}]}
    response = client.post("/api/v1/recommendations/events/batch", headers=customer_headers, json=payload)
    assert response.status_code == 200
    event = db.query(AnalyticsEvent).filter_by(target_type="package", target_id=package_id).one()
    exposure = db.query(RecommendationExposure).filter_by(target_type="package", target_id=package_id).one()
    assert event.actor_id == customer_user.id
    assert exposure.viewer_user_id == customer_user.id


def test_joint_recommendation_events_are_accepted(client, db, customer_headers, photographer_profile):
    package_id = _package_id(db, photographer_profile)
    event_types = [
        "joint_rec_impression", "joint_rec_open", "joint_rec_filter_change", "joint_rec_select_slot",
        "joint_rec_booking_start", "joint_rec_booking_success", "joint_rec_no_result",
    ]
    payload = {"events": [{
        "event_type": event_type, "target_type": "package", "target_id": package_id,
        "owner_user_id": photographer_profile.user_id, "recommendation_id": f"joint-{index}",
        "position": 0, "algorithm_version": "package_rec_v2_joint_availability",
    } for index, event_type in enumerate(event_types)]}
    response = client.post("/api/v1/recommendations/events/batch", headers=customer_headers, json=payload)
    assert response.status_code == 200
    assert response.json()["accepted"] == len(event_types)
    recorded = {event.event_type for event in db.query(AnalyticsEvent).filter(AnalyticsEvent.event_type.in_(event_types)).all()}
    assert recorded == set(event_types)
