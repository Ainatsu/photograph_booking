import json
from datetime import date

import pytest
from pydantic import ValidationError

from backend.app.core.config import Settings
from backend.app.models.ai_conversation import AIMessage
from backend.app.services import ai_agent_decision_service, ai_service
from backend.app.services.ai_agent_decision_contracts import GetShootContextInput, AgentDecision
from backend.app.services.ai_agent_decision_service import (
    AgentDecisionOutcome,
    build_decision_input,
    infer_shoot_context_decision,
    resolve_decision_plan,
)
from backend.app.services.ai_service import _shoot_context_error_result
from backend.app.services.ai_tool_policy_service import authorize_tool_call
from backend.app.services.geocoding_service import PlaceCandidate
from backend.app.services.shoot_context_service import ShootContextService
from backend.app.services.weather_service import WeatherProviderError


class FakeGeocoder:
    def __init__(self, candidates):
        self.candidates = candidates
        self.calls = 0

    async def search(self, _query):
        self.calls += 1
        return self.candidates


class FakeWeather:
    def __init__(self, payload=None, error=None):
        self.payload = payload or {}
        self.error = error
        self.calls = 0

    async def forecast(self, _latitude, _longitude, _shoot_date):
        self.calls += 1
        if self.error:
            raise self.error
        return self.payload


def place(name="香港石澳泳滩"):
    return PlaceCandidate(name=name, address=f"香港, {name}", latitude=22.2301, longitude=114.2510)


def weather_payload():
    return {
        "timezone": "Asia/Hong_Kong",
        "hourly": {
            "time": ["2026-08-08T16:00", "2026-08-08T17:00"],
            "temperature_2m": [33, 31],
            "precipitation_probability": [60, 30],
            "cloud_cover": [70, 50],
            "wind_speed_10m": [26, 18],
            "visibility": [10000, 12000],
        },
        "daily": {"sunrise": ["2026-08-08T05:55"], "sunset": ["2026-08-08T18:58"]},
        "provider": "open_meteo",
    }


@pytest.mark.asyncio
async def test_success_returns_normalized_weather_sunlight_and_threshold_advice(monkeypatch):
    monkeypatch.setattr("backend.app.services.shoot_context_service.cache_get", lambda _key: None, raising=False)
    geo = FakeGeocoder([place()])
    weather = FakeWeather(weather_payload())
    service = ShootContextService(
        geocoding=__import__("backend.app.services.geocoding_service", fromlist=["GeocodingService"]).GeocodingService(geo),
        weather=__import__("backend.app.services.weather_service", fromlist=["WeatherService"]).WeatherService(weather),
    )

    result = await service.get_context({
        "location_text": "香港石澳泳滩",
        "shoot_date": date.today(),
        "start_time": "16:00",
        "duration_minutes": 120,
    })

    assert result["status"] == "success"
    assert result["place"]["coordinate_system"] == "WGS84"
    assert result["weather"]["hourly"][0]["wind_kph"] == 26
    assert result["sunlight"] == {
        "sunrise": "05:55",
        "sunset": "18:58",
        "golden_hour_start": "18:13",
        "golden_hour_end": "18:58",
        "blue_hour_end": "19:25",
    }
    codes = {item["code"] for item in result["recommendations"]}
    assert {"rain_backup", "wind_safety", "heat_breaks", "golden_hour"} <= codes
    json.dumps(result, ensure_ascii=False)


@pytest.mark.asyncio
async def test_ambiguous_location_does_not_call_weather(monkeypatch):
    monkeypatch.setattr("backend.app.services.shoot_context_service.cache_get", lambda _key: None, raising=False)
    geo = FakeGeocoder([place("石澳泳滩"), place("石澳村")])
    weather = FakeWeather(weather_payload())
    service = ShootContextService(
        geocoding=__import__("backend.app.services.geocoding_service", fromlist=["GeocodingService"]).GeocodingService(geo),
        weather=__import__("backend.app.services.weather_service", fromlist=["WeatherService"]).WeatherService(weather),
    )

    result = await service.get_context({"location_text": "石澳", "shoot_date": date.today()})

    assert result["status"] == "ambiguous"
    assert result["error_code"] == "ambiguous_location"
    assert len(result["place_candidates"]) == 2
    assert weather.calls == 0


@pytest.mark.asyncio
async def test_primary_administrative_city_wins_over_same_name_localities(monkeypatch):
    monkeypatch.setattr("backend.app.services.shoot_context_service.cache_get", lambda _key: None, raising=False)
    city = PlaceCandidate(
        name="成都",
        address="成都, 成都市, 四川, 中国",
        latitude=30.66667,
        longitude=104.06667,
        feature_code="PPLA",
        population=13_568_357,
    )
    village = PlaceCandidate(
        name="成都",
        address="成都, 吉安市, 江西, 中国",
        latitude=26.983,
        longitude=114.207,
        feature_code="PPL",
        population=2_000,
    )
    geo = FakeGeocoder([city, village])
    weather = FakeWeather(weather_payload())
    service = ShootContextService(
        geocoding=__import__("backend.app.services.geocoding_service", fromlist=["GeocodingService"]).GeocodingService(geo),
        weather=__import__("backend.app.services.weather_service", fromlist=["WeatherService"]).WeatherService(weather),
    )

    result = await service.get_context({"location_text": "成都", "shoot_date": date.today()})

    assert result["status"] == "success"
    assert result["place"]["address"] == "成都, 成都市, 四川, 中国"
    assert weather.calls == 1


@pytest.mark.asyncio
async def test_weather_failure_degrades_to_partial(monkeypatch):
    monkeypatch.setattr("backend.app.services.shoot_context_service.cache_get", lambda _key: None, raising=False)
    geo = FakeGeocoder([place()])
    weather = FakeWeather(error=WeatherProviderError())
    service = ShootContextService(
        geocoding=__import__("backend.app.services.geocoding_service", fromlist=["GeocodingService"]).GeocodingService(geo),
        weather=__import__("backend.app.services.weather_service", fromlist=["WeatherService"]).WeatherService(weather),
    )

    result = await service.get_context({"location_text": "石澳泳滩", "shoot_date": date.today()})

    assert result["status"] == "partial"
    assert result["place"]["name"] == "香港石澳泳滩"
    assert result["weather"] is None
    assert result["sunlight"]["sunrise"]


@pytest.mark.asyncio
async def test_forecast_out_of_range_is_explicit(monkeypatch):
    monkeypatch.setattr("backend.app.services.shoot_context_service.cache_get", lambda _key: None, raising=False)
    geo = FakeGeocoder([place()])
    weather = FakeWeather(weather_payload())
    service = ShootContextService(
        geocoding=__import__("backend.app.services.geocoding_service", fromlist=["GeocodingService"]).GeocodingService(geo),
        weather=__import__("backend.app.services.weather_service", fromlist=["WeatherService"]).WeatherService(weather),
    )

    result = await service.get_context({"location_text": "石澳泳滩", "shoot_date": "2099-08-08"})

    assert result["status"] == "partial"
    assert result["error_code"] == "forecast_unavailable"
    assert weather.calls == 0


def test_contract_rejects_partial_coordinates_and_invalid_time():
    with pytest.raises(ValidationError):
        GetShootContextInput(location_text="石澳", shoot_date="2026-08-08", latitude=22.2)
    with pytest.raises(ValidationError):
        GetShootContextInput(location_text="石澳", shoot_date="2026-08-08", start_time="25:00")
    with pytest.raises(ValidationError):
        GetShootContextInput(location_text="石澳", shoot_date="2026-08-08", unknown=True)


def test_tool_is_read_only_and_plan_is_read_tool():
    authorization = authorize_tool_call(
        "get_shoot_context",
        arguments={"location_text": "石澳", "shoot_date": "2026-08-08"},
        user_role="customer",
    )
    assert authorization.allowed is True
    assert authorization.spec.risk_level.value == "read_only"
    assert authorization.requires_confirmation is False

    outcome = AgentDecisionOutcome(
        decision=AgentDecision(
            mode="tool_call",
            tool="get_shoot_context",
            arguments={"location_text": "石澳", "shoot_date": "2026-08-08"},
            confidence=0.99,
        ),
        parser="model",
    )
    plan = resolve_decision_plan(outcome, legacy_intent_name="chat", user_role="customer")
    assert plan.applied is True
    assert plan.action == "read_tool"


def test_tool_routing_is_enabled_by_default():
    assert Settings.model_fields["AGENT_ROUTING_MODE"].default == "tool_loop"


def test_yearless_weather_query_uses_current_year_and_current_message_place():
    decision = infer_shoot_context_decision(
        "八月十八号阿坝的天气如何？",
        today=date(2026, 8, 16),
    )
    assert decision is not None
    assert decision.tool == "get_shoot_context"
    assert decision.arguments == {"location_text": "阿坝", "shoot_date": "2026-08-18"}


def test_decision_input_exposes_platform_date_and_timezone():
    payload = json.loads(build_decision_input(content="明天天气", history=[]))
    assert payload["current_date"]
    assert payload["timezone"] == "Asia/Hong_Kong"


def test_location_failure_reply_does_not_claim_the_date_is_too_far():
    result = _shoot_context_error_result(
        {"status": "failed", "error_code": "location_not_found", "place_candidates": []},
        {"location_text": "阿坝", "shoot_date": "2026-08-18"},
    )
    assert "未能识别地点“阿坝”" in result["content"]
    assert "距离" not in result["content"]
    assert "预报范围" not in result["content"]


@pytest.mark.asyncio
async def test_weather_message_uses_current_place_instead_of_project_history(
    db, customer_user, monkeypatch
):
    class UnexpectedProvider:
        async def chat(self, *_args, **_kwargs):
            raise AssertionError("weather routing should not call an LLM on this failure path")

    captured = {}

    async def fake_get_context(_service, arguments):
        captured.update(arguments)
        return {
            "schema_version": "shoot_context_v1",
            "status": "failed",
            "place": None,
            "weather": None,
            "sunlight": None,
            "recommendations": [],
            "place_candidates": [],
            "error_code": "location_not_found",
        }

    monkeypatch.setattr(ai_service.settings, "AGENT_ROUTING_MODE", "tool_loop")
    monkeypatch.setattr(ai_service.settings, "AGENT_ROUTING_ROLLOUT_PERCENT", 100)
    monkeypatch.setattr(ai_service.settings, "AI_INTENT_CLASSIFIER_MODE", "rules")
    monkeypatch.setattr(ai_agent_decision_service, "platform_today", lambda: date(2026, 8, 16))
    monkeypatch.setattr(
        ai_agent_decision_service,
        "get_text_provider",
        lambda: UnexpectedProvider(),
    )
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: UnexpectedProvider())
    monkeypatch.setattr(ShootContextService, "get_context", fake_get_context)

    conversation = ai_service.create_conversation(db, customer_user.id)
    db.add(
        AIMessage(
            conversation_id=conversation.id,
            role="assistant",
            content="阿坝州研学跟拍项目",
        )
    )
    db.commit()

    _, message = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "八月十八号阿坝的天气如何？",
    )

    assert captured["location_text"] == "阿坝"
    assert captured["shoot_date"] == "2026-08-18"
    assert "未能识别地点“阿坝”" in message.content
    assert "距离" not in message.content
    assert message.message_metadata["agent_decision"]["parser"] == "deterministic"
    assert message.message_metadata["shoot_context"]["error_code"] == "location_not_found"


@pytest.mark.asyncio
async def test_selected_ambiguous_candidate_reuses_coordinates_and_original_date(
    db, customer_user, monkeypatch
):
    class UnexpectedProvider:
        async def chat(self, *_args, **_kwargs):
            raise AssertionError("candidate selection should not need an LLM on the error path")

    captured = {}

    async def fake_get_context(_service, arguments):
        captured.update(arguments)
        return {
            "schema_version": "shoot_context_v1",
            "status": "failed",
            "place": None,
            "weather": None,
            "sunlight": None,
            "recommendations": [],
            "place_candidates": [],
            "error_code": "weather_unavailable",
        }

    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: UnexpectedProvider())
    monkeypatch.setattr(ShootContextService, "get_context", fake_get_context)
    conversation = ai_service.create_conversation(db, customer_user.id)
    source = AIMessage(
        conversation_id=conversation.id,
        role="assistant",
        content="请选择地点",
        message_metadata={
            "agent_decision": {
                "plan": {
                    "arguments": {
                        "location_text": "成都",
                        "shoot_date": "2026-08-18",
                        "duration_minutes": 120,
                    }
                }
            },
            "shoot_context": {
                "schema_version": "shoot_context_v1",
                "status": "ambiguous",
                "place_candidates": [
                    {
                        "name": "成都",
                        "address": "成都, 成都市, 四川, 中国",
                        "latitude": 30.66667,
                        "longitude": 104.06667,
                    }
                ],
            },
        },
    )
    db.add(source)
    db.commit()
    db.refresh(source)

    _, message = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "选择地点：成都, 成都市, 四川, 中国",
        shoot_context_selection={
            "source_message_id": source.id,
            "latitude": 30.66667,
            "longitude": 104.06667,
        },
    )

    assert captured["location_text"] == "成都"
    assert captured["location_address"] == "成都, 成都市, 四川, 中国"
    assert captured["shoot_date"] == "2026-08-18"
    assert captured["latitude"] == 30.66667
    assert message.message_metadata["agent_decision"]["parser"] == "deterministic"
