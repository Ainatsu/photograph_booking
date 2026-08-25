from backend.app.models.analytics import AnalyticsEvent
from backend.app.models.like import Like
from backend.app.models.recommendation import RecommendationExposure, RecommendationItemStats
from backend.app.services.photographer_service import _fix_missing_ids


def test_recommendation_works_returns_ranked_unique_items(client, photographer_profile):
    response = client.get("/api/v1/recommendations/works", params={"limit": 10, "session_id": "test-session"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["algorithm_version"] == "work_hybrid_v1"
    assert payload["recommendation_id"]
    ids = [item["id"] for item in payload["items"]]
    assert len(ids) == len(set(ids))
    assert all(item["recommendation_reason"] for item in payload["items"])


def test_recommendation_uses_positive_tag_history(client, db, customer_user, customer_headers, photographer_profile):
    _fix_missing_ids(db)
    db.refresh(photographer_profile)
    works = photographer_profile.portfolio
    liked_id = works[0]["id"]
    db.add(Like(user_id=customer_user.id, target_type="portfolio", target_id=liked_id))
    db.commit()

    response = client.get("/api/v1/recommendations/works", headers=customer_headers, params={"limit": 10})
    assert response.status_code == 200
    items = response.json()["items"]
    assert any(item["candidate_source"] in {"content_similarity", "followed_author"} for item in items)


def test_batch_events_uses_authenticated_viewer(client, db, customer_user, customer_headers, photographer_profile):
    _fix_missing_ids(db)
    db.refresh(photographer_profile)
    work_id = photographer_profile.portfolio[0]["id"]
    payload = {"events": [{"event_type": "portfolio_impression", "target_id": work_id, "owner_user_id": photographer_profile.user_id, "recommendation_id": "rec-test", "session_id": "session-test", "scene": "gallery_for_you", "position": 0, "algorithm_version": "work_hybrid_v1", "candidate_source": "trending"}]}
    response = client.post("/api/v1/recommendations/events/batch", headers=customer_headers, json=payload)
    assert response.status_code == 200
    assert response.json()["accepted"] == 1
    event = db.query(AnalyticsEvent).filter_by(target_id=work_id).one()
    exposure = db.query(RecommendationExposure).filter_by(target_id=work_id).one()
    assert event.actor_id == customer_user.id
    assert exposure.viewer_user_id == customer_user.id


def test_recommendation_creates_item_stats(client, db, photographer_profile):
    response = client.get("/api/v1/recommendations/works", params={"session_id": "stats-session"})
    assert response.status_code == 200
    assert db.query(RecommendationItemStats).count() == len(photographer_profile.portfolio)
