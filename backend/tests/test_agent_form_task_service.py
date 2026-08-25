"""Embedded Agent form contract regression tests."""

from uuid import uuid4

import pytest

from backend.app.schemas.ai import AITaskSubmission
from backend.app.services import ai_service
from backend.app.services.agent_form_task_service import (
    infer_initial_task_type,
    make_form_card,
    normalize_submission,
)


class UnexpectedProvider:
    async def chat(self, *_args, **_kwargs):
        raise AssertionError("the form contract test must not call the language model")


def test_submission_accepts_new_protocol_and_normalizes_payload():
    task_id = uuid4()
    idempotency_key = uuid4()
    submission = AITaskSubmission(
        task_id=task_id,
        task_type="create_booking",
        action="publish",
        revision=3,
        form_data={"package_id": "pkg-1", "photographer_id": 8, "appointment_time": "2099-08-01T10:00:00"},
        media_refs=[],
        idempotency_key=idempotency_key,
    )

    normalized = normalize_submission(submission.model_dump())
    assert normalized["task_id"] == str(task_id)
    assert normalized["revision"] == 3
    assert normalized["form_data"]["package_id"] == "pkg-1"
    assert normalized["idempotency_key"] == str(idempotency_key)


def test_form_card_uses_ordinary_project_payload_names():
    card = make_form_card(
        "create_project",
        values={"title": "城市人像", "style": "胶片, 纪实", "city": "香港"},
    )

    assert card["schema_version"] == 1
    assert card["initial_fields"]["style_tags"] == ["胶片", "纪实"]
    assert card["initial_fields"]["title"] == "城市人像"
    assert set(card["actions"]) == {"publish", "save_draft", "cancel"}


def test_project_application_is_not_opened_by_page_entry_regex():
    page_context = {"resource_type": "project", "resource_id": 42, "title": "测试企划"}
    assert infer_initial_task_type("我想应邀这个企划，你有没有什么建议", page_context) is None


@pytest.mark.asyncio
async def test_new_project_form_submission_writes_once_and_replays(
    monkeypatch,
    db,
    customer_user,
):
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: UnexpectedProvider())
    conversation = ai_service.create_conversation(db, customer_user.id)
    _, first = await ai_service.send_ai_message(db, customer_user.id, conversation.id, "帮我发布一个企划")
    card = first.message_metadata["agent_form_card"]
    key = str(uuid4())
    form_data = {
        "title": "新协议企划",
        "description": "测试 Agent 表单直写",
        "category": "portrait",
        "style_tags": ["纪实"],
        "city": "香港",
        "shoot_date_start": "2099-08-01T10:00:00",
        "reference_images": [],
        "visibility": "public",
    }

    _, completed = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        None,
        task_submission={
            "task_id": card["task_id"],
            "task_type": "create_project",
            "action": "publish",
            "revision": card["revision"],
            "form_data": form_data,
            "media_refs": [],
            "idempotency_key": key,
        },
    )
    assert completed.message_metadata["agent_form_card"]["status"] == "published"

    _, replay = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        None,
        task_submission={
            "task_id": card["task_id"],
            "task_type": "create_project",
            "action": "publish",
            "revision": card["revision"],
            "form_data": form_data,
            "media_refs": [],
            "idempotency_key": key,
        },
    )
    assert replay.message_metadata["agent_form_card"]["status"] == "published"
    from backend.app.models.project import ShootProject
    assert db.query(ShootProject).filter_by(customer_id=customer_user.id, title="新协议企划").count() == 1
