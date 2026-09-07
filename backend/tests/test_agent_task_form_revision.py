from uuid import uuid4

import pytest
from fastapi import HTTPException

from backend.app.services import ai_service
from backend.app.services.agent_form_revision_service import append_form_revision, list_form_revisions


def test_form_revisions_are_monotonic_and_auditable(db, customer_user):
    conversation = ai_service.create_conversation(db, customer_user.id)
    task_id = str(uuid4())
    first = append_form_revision(
        db, task_id=task_id, conversation_id=conversation.id, user_id=customer_user.id,
        revision=1, operations=[{"field": "city", "op": "set", "value": "香港", "confidence": .9, "evidence": "chat"}],
        resulting_form={"city": "香港"}, source="chat_extraction", source_message_id=None,
    )
    second = append_form_revision(
        db, task_id=task_id, conversation_id=conversation.id, user_id=customer_user.id,
        revision=2, operations=[{"field": "budget_max", "op": "set", "value": 3000}],
        resulting_form={"city": "香港", "budget_max": 3000}, source="page", created_by="user",
    )
    db.commit()
    rows = list_form_revisions(db, task_id=task_id, user_id=customer_user.id, conversation_id=conversation.id)
    assert [row.revision for row in rows] == [1, 2]
    assert first.source == "chat_extraction"
    assert second.created_by == "user"


def test_duplicate_idempotency_replays_without_new_revision(db, customer_user):
    conversation = ai_service.create_conversation(db, customer_user.id)
    task_id = str(uuid4())
    key = str(uuid4())
    first = append_form_revision(
        db, task_id=task_id, conversation_id=conversation.id, user_id=customer_user.id,
        revision=1, operations=[], resulting_form={"title": "A"}, source="page", idempotency_key=key,
    )
    replay = append_form_revision(
        db, task_id=task_id, conversation_id=conversation.id, user_id=customer_user.id,
        revision=1, operations=[], resulting_form={"title": "A"}, source="page", idempotency_key=key,
    )
    assert replay.id == first.id
    assert len(list_form_revisions(db, task_id=task_id, user_id=customer_user.id, conversation_id=conversation.id)) == 1


def test_old_revision_is_rejected_with_latest_snapshot(db, customer_user):
    conversation = ai_service.create_conversation(db, customer_user.id)
    task_id = str(uuid4())
    append_form_revision(
        db, task_id=task_id, conversation_id=conversation.id, user_id=customer_user.id,
        revision=1, operations=[], resulting_form={"title": "A"}, source="page",
    )
    with pytest.raises(HTTPException) as exc:
        append_form_revision(
            db, task_id=task_id, conversation_id=conversation.id, user_id=customer_user.id,
            revision=3, operations=[], resulting_form={"title": "B"}, source="page",
        )
    assert exc.value.status_code == 409
    assert exc.value.detail["latest_revision"] == 1
