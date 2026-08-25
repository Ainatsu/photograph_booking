from uuid import uuid4

from backend.app.models.ai_conversation import AIMessage
from backend.app.models.project import ShootProject
from backend.app.services import ai_service
from backend.app.services.agent_form_task_service import initial_form_result


class StaticProvider:
    async def chat(self, messages):
        return {
            "content": "可以先选清新、胶片或棚拍质感，再按预算筛选。",
            "metadata": {"model": {"provider": "test", "model": "test-model"}},
        }


def test_ai_api_requires_login(client):
    res = client.get("/api/v1/ai/conversations")

    assert res.status_code == 401


def test_create_conversation(client, customer_headers):
    res = client.post("/api/v1/ai/conversations", json={"title": "AI 咨询"}, headers=customer_headers)

    assert res.status_code == 201
    assert res.json()["title"] == "AI 咨询"


def test_user_cannot_read_other_user_conversation(client, customer_headers, photographer_headers):
    created = client.post("/api/v1/ai/conversations", json={}, headers=customer_headers)
    conversation_id = created.json()["id"]

    res = client.get(f"/api/v1/ai/conversations/{conversation_id}/messages", headers=photographer_headers)

    assert res.status_code == 404


def test_send_message_returns_user_and_assistant(monkeypatch, client, customer_headers):
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: StaticProvider())
    created = client.post("/api/v1/ai/conversations", json={}, headers=customer_headers)
    conversation_id = created.json()["id"]

    res = client.post(
        f"/api/v1/ai/conversations/{conversation_id}/messages",
        json={"content": "生日写真怎么选风格？"},
        headers=customer_headers,
    )

    assert res.status_code == 200
    data = res.json()
    assert data["user_message"]["role"] == "user"
    assert data["assistant_message"]["role"] == "assistant"
    assert data["assistant_message"]["content"] == "可以先选清新、胶片或棚拍质感，再按预算筛选。"
    assert data["assistant_message"]["metadata"]["model"]["provider"] == "test"

    messages = client.get(f"/api/v1/ai/conversations/{conversation_id}/messages", headers=customer_headers)
    assert [message["role"] for message in messages.json()] == ["user", "assistant"]


def test_cancel_embedded_form_with_uuid_metadata(monkeypatch, client, db, customer_headers):
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: StaticProvider())
    created = client.post("/api/v1/ai/conversations", json={}, headers=customer_headers)
    conversation_id = created.json()["id"]

    form = initial_form_result("create_project", {})
    db.add(
        AIMessage(
            conversation_id=conversation_id,
            role="assistant",
            content=form["content"],
            message_metadata=form["metadata"],
        )
    )
    db.commit()
    card = form["metadata"]["agent_form_card"]
    task_id = card["task_id"]
    idempotency_key = str(uuid4())

    cancelled = client.post(
        f"/api/v1/ai/conversations/{conversation_id}/messages",
        json={
            "content": None,
            "task_submission": {
                "task_id": task_id,
                "task_type": "create_project",
                "action": "cancel",
                "revision": card["revision"],
                "idempotency_key": idempotency_key,
            },
        },
        headers=customer_headers,
    )

    assert cancelled.status_code == 200
    data = cancelled.json()
    assert data["assistant_message"]["metadata"]["task_state"]["status"] == "cancelled"
    assert data["user_message"]["metadata"]["task_submission"]["task_id"] == task_id
    assert data["user_message"]["metadata"]["task_submission"]["idempotency_key"] == idempotency_key
    assert db.query(ShootProject).count() == 0
