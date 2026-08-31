from datetime import datetime

import pytest

from backend.app.models.ai_conversation import AIConversation, AIMessage
from backend.app.models.ai_production import AgentTrace, AIIndexJob
from backend.app.models.order import Order, OrderStatus
from backend.app.services import ai_multimodal_embedding_service
from backend.app.services.ai_index_job_service import enqueue_index_job, process_index_jobs
from backend.app.services.ai_provider import ResilientAIProvider
from backend.app.services.ai_retrieval_service import _owner_conversion_scores
from backend.app.services.ai_trace_service import agent_quality_dashboard, record_agent_trace


class FailingProvider:
    async def chat(self, messages, *, temperature=None, response_format=None):
        raise RuntimeError("primary unavailable")


class StaticProvider:
    async def chat(self, messages, *, temperature=None, response_format=None):
        return {
            "content": "fallback response",
            "metadata": {"model": {"provider": "fallback", "model": "static"}},
        }


@pytest.mark.asyncio
async def test_resilient_provider_falls_back_and_records_reason():
    provider = ResilientAIProvider(FailingProvider(), StaticProvider())
    result = await provider.chat([{"role": "user", "content": "hello"}])

    assert result["content"] == "fallback response"
    assert result["metadata"]["fallback"]["used"] is True
    assert result["metadata"]["fallback"]["reason"] == "RuntimeError"


def test_index_job_is_coalesced_and_processed(db, photographer_profile, monkeypatch):
    monkeypatch.setattr(ai_multimodal_embedding_service.settings, "AI_IMAGE_EMBEDDING_PROVIDER", "mock")
    photographer_profile.portfolio = [{
        "id": "production-work",
        "url": "/static/production-work.jpg",
        "media_type": "image",
        "title": "production portrait",
        "description": "natural light portrait",
        "tags": ["natural light"],
    }]
    db.commit()

    first = enqueue_index_job(
        db,
        owner_user_id=photographer_profile.user_id,
        reason="profile_changed",
    )
    second = enqueue_index_job(
        db,
        owner_user_id=photographer_profile.user_id,
        reason="portfolio_changed",
    )
    assert first.id == second.id

    result = process_index_jobs(db)
    db.refresh(first)
    assert result == {"processed": 1, "completed": 1, "failed": 0}
    assert first.status == "completed"
    assert first.result["documents"] > 0
    assert first.result["text_embeddings"]["embedded"] > 0
    assert first.result["image_embeddings"]["embedded"] == 2


def test_agent_trace_and_quality_dashboard(db, customer_user):
    conversation = AIConversation(user_id=customer_user.id, title="trace")
    db.add(conversation)
    db.flush()
    user_message = AIMessage(conversation_id=conversation.id, role="user", content="find a photographer")
    assistant_message = AIMessage(conversation_id=conversation.id, role="assistant", content="result")
    db.add_all([user_message, assistant_message])
    db.commit()

    trace = record_agent_trace(
        db,
        user_id=customer_user.id,
        conversation_id=conversation.id,
        user_message_id=user_message.id,
        assistant_message_id=assistant_message.id,
        intent={"intent": "resource_search", "route": "retrieval"},
        metadata={
            "model": {"provider": "mock", "model": "mock", "input_tokens": 20, "output_tokens": 10},
            "retrieval": {"diagnostics": {"latency_ms": 12}},
            "citation_policy": {"allowed_resource_ids": {"photographers": [1]}},
        },
        total_latency_ms=25,
    )
    dashboard = agent_quality_dashboard(db)

    assert isinstance(trace, AgentTrace)
    assert dashboard["traces"]["total"] == 1
    assert dashboard["traces"]["citation_failure_rate"] == 0
    assert dashboard["traces"]["avg_total_latency_ms"] == 25


def test_conversion_feedback_uses_smoothed_booking_rate(db, customer_user, photographer_user):
    for index, status in enumerate((OrderStatus.COMPLETED, OrderStatus.CONFIRMED, OrderStatus.CANCELLED)):
        db.add(Order(
            customer_id=customer_user.id,
            photographer_id=photographer_user.id,
            package_snapshot=f"package-{index}",
            appointment_time=datetime(2026, 8, index + 1, 10, 0),
            duration_minutes=60,
            status=status,
        ))
    db.commit()

    scores = _owner_conversion_scores(db)
    assert photographer_user.id in scores
    assert 0.1 < scores[photographer_user.id] < (2 / 3)
