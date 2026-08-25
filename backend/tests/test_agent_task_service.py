"""Persistent Agent task draft and explicit commit regression tests."""

from uuid import uuid4

import pytest
from fastapi import HTTPException

from backend.app.models.project import ShootProject
from backend.app.services import ai_service
from backend.app.services.agent_task_extraction_service import extract_task_patch
from backend.app.services.agent_task_service import commit_task, ensure_task, patch_task, serialize_task


class UnexpectedProvider:
    async def chat(self, *_args, **_kwargs):
        raise AssertionError("an active Agent task must not call the language model for task progress")


def _apply_fields(db, conversation_id, user_id, task, fields):
    return patch_task(
        db,
        user_id=user_id,
        conversation_id=conversation_id,
        task_id=task.id,
        revision=task.revision,
        operations=[
            {"field": field, "op": "set", "value": value, "confidence": 1, "evidence": "test"}
            for field, value in fields.items()
        ],
    )


def test_one_answer_extracts_every_explicit_task_field():
    patch = extract_task_patch(
        "create_project",
        "标题：港岛暮色；城市：香港；预算：3000；风格：胶片、自然光；描述：两人情侣写真",
    )

    values = {item["field"]: item["value"] for item in patch["operations"]}
    assert values == {
        "title": "港岛暮色",
        "city": "香港",
        "style_tags": ["胶片", "自然光"],
        "budget_max": 3000,
        "description": "两人情侣写真",
    }


def test_booking_date_and_followup_time_are_merged():
    date_patch = extract_task_patch("create_booking", "预约日期是2099-08-01")
    date_values = {item["field"]: item["value"] for item in date_patch["operations"]}
    assert date_values == {"appointment_date": "2099-08-01"}

    time_patch = extract_task_patch(
        "create_booking",
        "下午3点",
        existing_fields=date_values,
    )
    time_values = {item["field"]: item["value"] for item in time_patch["operations"]}
    assert time_values["appointment_date"] == "2099-08-01"
    assert time_values["appointment_time"] == "2099-08-01T15:00:00"


@pytest.mark.asyncio
async def test_generic_confirmation_does_not_publish_active_task(monkeypatch, db, customer_user):
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: UnexpectedProvider())
    conversation = ai_service.create_conversation(db, customer_user.id)
    task = ensure_task(
        db,
        user_id=customer_user.id,
        conversation_id=conversation.id,
        task_type="create_project",
    )
    _apply_fields(db, conversation.id, customer_user.id, task, {
        "title": "不会误发布",
        "description": "普通确认词只能继续任务",
        "city": "香港",
    })
    db.commit()

    _, assistant = await ai_service.send_ai_message(db, customer_user.id, conversation.id, "可以")

    assert db.query(ShootProject).filter_by(customer_id=customer_user.id).count() == 0
    assert "发布" not in assistant.content or "明确点击提交" in assistant.content
    assert assistant.message_metadata["active_task"]["summary"]["can_commit"] is True


def test_incomplete_task_commit_returns_missing_fields(db, customer_user):
    conversation = ai_service.create_conversation(db, customer_user.id)
    task = ensure_task(
        db,
        user_id=customer_user.id,
        conversation_id=conversation.id,
        task_type="create_project",
    )

    with pytest.raises(HTTPException) as exc_info:
        commit_task(
            db,
            user_id=customer_user.id,
            conversation_id=conversation.id,
            task_id=task.id,
            revision=task.revision,
            idempotency_key=str(uuid4()),
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail["code"] == "task_incomplete"
    assert exc_info.value.detail["missing_fields"] == ["title", "description", "city"]


def test_publish_work_commit_requires_original_editor(db, photographer_user):
    conversation = ai_service.create_conversation(db, photographer_user.id)
    task = ensure_task(
        db,
        user_id=photographer_user.id,
        conversation_id=conversation.id,
        task_type="publish_work",
    )
    task.media_assets = ["/static/ai/work.jpg"]
    db.flush()

    with pytest.raises(HTTPException) as exc_info:
        commit_task(
            db,
            user_id=photographer_user.id,
            conversation_id=conversation.id,
            task_id=task.id,
            revision=task.revision,
            idempotency_key=str(uuid4()),
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "editor_required"


def test_structured_project_commit_writes_exactly_once(db, customer_user):
    conversation = ai_service.create_conversation(db, customer_user.id)
    task = ensure_task(
        db,
        user_id=customer_user.id,
        conversation_id=conversation.id,
        task_type="create_project",
    )
    task = _apply_fields(db, conversation.id, customer_user.id, task, {
        "title": "结构化提交企划",
        "description": "只允许显式按钮提交一次",
        "city": "香港",
    })
    key = str(uuid4())

    completed, first_receipt = commit_task(
        db,
        user_id=customer_user.id,
        conversation_id=conversation.id,
        task_id=task.id,
        revision=task.revision,
        idempotency_key=key,
    )
    replayed, second_receipt = commit_task(
        db,
        user_id=customer_user.id,
        conversation_id=conversation.id,
        task_id=task.id,
        revision=task.revision,
        idempotency_key=key,
    )

    assert completed.status == replayed.status == "completed"
    assert first_receipt["status"] == second_receipt["status"] == "success"
    assert db.query(ShootProject).filter_by(customer_id=customer_user.id, title="结构化提交企划").count() == 1


def test_booking_receipt_describes_request_not_success(monkeypatch, db, customer_user):
    from backend.app.services import ai_agent_tool_service

    monkeypatch.setattr(ai_agent_tool_service, "create_booking", lambda *_args, **_kwargs: {
        "status": "success",
        "result": {"order_id": 88, "status": "pending_photographer_confirmation"},
    })
    conversation = ai_service.create_conversation(db, customer_user.id)
    task = ensure_task(
        db,
        user_id=customer_user.id,
        conversation_id=conversation.id,
        task_type="create_booking",
        target={"photographer_id": 9, "package_id": "pkg-9"},
    )
    task = _apply_fields(db, conversation.id, customer_user.id, task, {
        "appointment_time": "2099-08-01T15:00:00",
    })

    completed, receipt = commit_task(
        db,
        user_id=customer_user.id,
        conversation_id=conversation.id,
        task_id=task.id,
        revision=task.revision,
        idempotency_key=str(uuid4()),
    )

    assert completed.status == "completed"
    assert "预约申请已提交" in receipt["content"]
    assert "预约成功" not in receipt["content"]
    assert serialize_task(completed)["summary"]["can_commit"] is False
