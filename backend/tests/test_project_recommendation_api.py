from datetime import datetime

from backend.app.models.analytics import AnalyticsEvent
from backend.app.models.project import ProjectApplication
from backend.app.models.recommendation import RecommendationExposure
from backend.app.schemas.project import ProjectApplicationCreate, ProjectCreate
from backend.app.services.project_service import apply_project, create_project
from sqlalchemy.orm.attributes import flag_modified


def _create_open_project(db, customer_user, **overrides):
    values = {
        "title": "北京日系人像拍摄",
        "description": "需要自然光日系人像摄影师，交付精修照片和全部底片。",
        "category": "人像",
        "style_tags": ["日系", "自然光"],
        "city": "北京",
        "shoot_date_start": datetime(2026, 8, 20, 10, 0),
        "shoot_date_end": datetime(2026, 8, 20, 12, 0),
        "duration_minutes": 120,
        "budget_min": 500,
        "budget_max": 1000,
        "deliverables": {"retouched": 20, "raw": True},
        "visibility": "public",
        "expires_at": datetime(2026, 8, 10, 0, 0),
        "publish": True,
    }
    values.update(overrides)
    return create_project(db, customer_user.id, ProjectCreate(**values))


def test_project_recommendation_matches_photographer_profile(client, db, customer_user, photographer_profile, photographer_headers):
    project = _create_open_project(db, customer_user)
    response = client.get("/api/v1/recommendations/projects", headers=photographer_headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["algorithm_version"] == "project_match_v1"
    assert [item["id"] for item in payload["items"]] == [project.id]
    assert payload["items"][0]["candidate_source"] == "style_match"
    assert payload["items"][0]["match_reason"]


def test_project_recommendation_treats_city_as_soft_signal_but_filters_budget_conflict(client, db, customer_user, photographer_profile, photographer_headers):
    remote = _create_open_project(db, customer_user, city="上海")
    _create_open_project(db, customer_user, title="超低预算", budget_min=50, budget_max=100)
    response = client.get("/api/v1/recommendations/projects", headers=photographer_headers)
    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [remote.id]


def test_project_recommendation_excludes_existing_application(client, db, customer_user, photographer_user, photographer_profile, photographer_headers):
    project = _create_open_project(db, customer_user)
    apply_project(db, project, photographer_user.id, ProjectApplicationCreate(proposal_text="我可以完成", price_quote=800))
    response = client.get("/api/v1/recommendations/projects", headers=photographer_headers)
    assert response.status_code == 200
    assert response.json()["items"] == []
    assert db.query(ProjectApplication).filter_by(project_id=project.id, photographer_id=photographer_user.id).count() == 1


def test_project_recommendation_treats_busy_date_as_soft_signal(client, db, customer_user, photographer_profile, photographer_headers):
    project = _create_open_project(db, customer_user)
    photographer_profile.availability_exceptions = [{"date": "2026-08-20", "status": "busy"}]
    flag_modified(photographer_profile, "availability_exceptions")
    db.commit()
    response = client.get("/api/v1/recommendations/projects", headers=photographer_headers)
    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [project.id]


def test_project_recommendation_rejects_customer(client, customer_headers):
    response = client.get("/api/v1/recommendations/projects", headers=customer_headers)
    assert response.status_code == 403


def test_project_impression_tracks_viewer(client, db, customer_user, photographer_user, photographer_profile, photographer_headers):
    project = _create_open_project(db, customer_user)
    payload = {"events": [{"event_type": "project_impression", "target_type": "shoot_project", "target_id": str(project.id), "owner_user_id": customer_user.id, "recommendation_id": "project-rec", "session_id": "project-session", "scene": "photographer_project_feed", "position": 0, "algorithm_version": "project_match_v1", "candidate_source": "style_match"}]}
    response = client.post("/api/v1/recommendations/events/batch", headers=photographer_headers, json=payload)
    assert response.status_code == 200
    event = db.query(AnalyticsEvent).filter_by(target_type="shoot_project", target_id=str(project.id)).one()
    exposure = db.query(RecommendationExposure).filter_by(target_type="shoot_project", target_id=str(project.id)).one()
    assert event.actor_id == photographer_user.id
    assert exposure.viewer_user_id == photographer_user.id


def test_project_click_accepts_integer_target_id(client, db, customer_user, photographer_headers):
    project = _create_open_project(db, customer_user)
    payload = {"events": [{"event_type": "project_click", "target_type": "shoot_project", "target_id": project.id, "owner_user_id": customer_user.id, "position": 0, "scene": "showcase"}]}
    response = client.post("/api/v1/recommendations/events/batch", headers=photographer_headers, json=payload)
    assert response.status_code == 200
    assert response.json()["accepted"] == 1
    event = db.query(AnalyticsEvent).filter_by(event_type="project_click", target_type="shoot_project", target_id=str(project.id)).one()
    assert event.event_metadata["scene"] == "showcase"


def test_project_click_from_anonymous_viewer_uses_owner_from_payload(client, db, customer_user):
    project = _create_open_project(db, customer_user)
    payload = {"events": [{"event_type": "project_click", "target_type": "shoot_project", "target_id": project.id, "owner_user_id": customer_user.id, "position": 0, "scene": "showcase"}]}
    response = client.post("/api/v1/recommendations/events/batch", json=payload)
    assert response.status_code == 200
    assert response.json()["accepted"] == 1
    event = db.query(AnalyticsEvent).filter_by(event_type="project_click", target_id=str(project.id)).one()
    assert event.user_id == customer_user.id
    assert event.actor_id is None
