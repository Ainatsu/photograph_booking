from datetime import date, timedelta

from backend.app.services.ai_orchestrator_service import recognize_intent_by_rules
from backend.app.services.ai_service import _joint_booking_search_result
from backend.app.models.ai_conversation import AIConversation, AIMessage
from backend.app.services.ai_booking_service import _latest_referenced_package


def test_booking_rules_extract_relative_date_time_window_and_constraints():
    intent = recognize_intent_by_rules("下周六下午在成都太古里拍日系人像，预算1500以内，30公里内，推荐有空且离得近的摄影师")
    assert intent.intent == "booking_flow"
    assert intent.slots["date"]
    assert intent.slots["time_start"] == "14:00"
    assert intent.slots["time_end"] == "18:00"
    assert intent.slots["budget_strict"] is True
    assert intent.slots["max_distance_km"] == 30
    assert intent.slots["availability_required"] is True
    assert intent.slots["sort_mode"] == "nearest"


def test_joint_booking_result_returns_bookable_package_references(db, photographer_profile, photographer_user):
    photographer_profile.available_hours = [{"day": "周六", "slots": ["09:00-18:00"]}]
    photographer_profile.service_city = "北京"
    photographer_profile.service_latitude = 39.9042
    photographer_profile.service_longitude = 116.4074
    db.commit()
    target = date.today() + timedelta(days=(5 - date.today().weekday()) % 7 + 14)
    from backend.app.services.ai_agent_contracts import AgentIntent
    intent = AgentIntent(
        intent="booking_flow",
        sub_intents=["search_package", "create_booking"],
        slots={"date": target.strftime("%m-%d"), "time_start": "14:00", "time_end": "18:00", "city": "北京"},
        route="booking",
        requires_confirmation=True,
    )
    result = _joint_booking_search_result(db, user_id=photographer_user.id, intent=intent, session_id="joint-flow")
    assert result["metadata"]["task_state"]["status"] == "presenting_options"
    assert result["metadata"]["references"]["packages"]
    item = result["metadata"]["references"]["packages"][0]
    assert item["availability"]["matching_slots"]


def test_historical_package_reference_supports_ordinal_nearest_and_cheapest(db, customer_user):
    conversation = AIConversation(user_id=customer_user.id, title="联合推荐")
    db.add(conversation)
    db.flush()
    packages = [
        {"id": "a", "package_name": "远一点", "price": 500, "distance_km": 12.0},
        {"id": "b", "package_name": "近一点", "price": 900, "distance_km": 2.0},
    ]
    db.add(AIMessage(conversation_id=conversation.id, role="assistant", content="推荐结果", message_metadata={"references": {"packages": packages}}))
    db.commit()
    assert _latest_referenced_package(db, conversation.id, "第二个")["id"] == "b"
    assert _latest_referenced_package(db, conversation.id, "最近的")["id"] == "b"
    assert _latest_referenced_package(db, conversation.id, "便宜一点")["id"] == "a"
