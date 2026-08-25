from datetime import date, timedelta

from backend.app.services.ai_agent_tool_service import search_bookable_packages
from backend.app.services.ai_tool_policy_service import ConfirmationPolicy, ToolRiskLevel, get_tool_spec


def test_joint_recommendation_tool_is_registered_as_read_only():
    spec = get_tool_spec("search_bookable_packages")
    assert spec.risk_level == ToolRiskLevel.READ_ONLY
    assert spec.confirmation_policy == ConfirmationPolicy.NONE
    assert spec.retryable is True
    assert spec.idempotent is True


def test_joint_recommendation_tool_returns_structured_references(db, photographer_profile):
    photographer_profile.available_hours = [{"day": "周六", "slots": ["09:00-18:00"]}]
    photographer_profile.service_latitude = 39.9042
    photographer_profile.service_longitude = 116.4074
    db.commit()
    today = date.today()
    target = today + timedelta(days=(5 - today.weekday()) % 7 + 14)
    response = search_bookable_packages(db, query_payload={
        "shoot_date": target.isoformat(),
        "time_start": "14:00",
        "time_end": "18:00",
        "latitude": 39.9042,
        "longitude": 116.4074,
        "require_exact_availability": True,
    }, session_id="agent-joint-test")
    assert response["status"] == "success"
    assert response["policy"]["confirmation_policy"] == "none"
    assert response["result"]["items"][0]["availability"]["matching_slots"]
