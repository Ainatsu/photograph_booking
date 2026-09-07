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
    assert res.json()["status"] == "active"
    assert res.json()["source"] == "assistant"


def test_conversation_metadata_and_message_preview(client, customer_headers, monkeypatch):
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: StaticProvider())
    created = client.post("/api/v1/ai/conversations", json={}, headers=customer_headers)
    conversation_id = created.json()["id"]
    updated = client.patch(
        f"/api/v1/ai/conversations/{conversation_id}",
        json={"summary": "  生日写真咨询  ", "source": "web"},
        headers=customer_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["summary"] == "生日写真咨询"
    assert updated.json()["source"] == "web"

    sent = client.post(
        f"/api/v1/ai/conversations/{conversation_id}/messages",
        json={"content": "  生日写真怎么选风格？  "},
        headers=customer_headers,
    )
    assert sent.status_code == 200
    refreshed = client.get("/api/v1/ai/conversations", headers=customer_headers).json()[0]
    assert refreshed["last_message_preview"] == "生日写真怎么选风格？"
    assert refreshed["last_message_at"]


def test_invalid_conversation_status_is_rejected(client, customer_headers):
    created = client.post("/api/v1/ai/conversations", json={}, headers=customer_headers)
    response = client.patch(
        f"/api/v1/ai/conversations/{created.json()['id']}",
        json={"status": "deleted"},
        headers=customer_headers,
    )
    assert response.status_code == 422


def test_conversations_are_archived_without_losing_history(client, customer_headers):
    first = client.post("/api/v1/ai/conversations", json={"title": "保留记录"}, headers=customer_headers)
    second = client.post("/api/v1/ai/conversations", json={"title": "当前工作"}, headers=customer_headers)
    first_id = first.json()["id"]

    archived = client.patch(
        f"/api/v1/ai/conversations/{first_id}",
        json={"archived": True},
        headers=customer_headers,
    )
    assert archived.status_code == 200
    assert archived.json()["archived_at"]

    visible = client.get("/api/v1/ai/conversations", headers=customer_headers)
    assert [item["id"] for item in visible.json()] == [second.json()["id"]]

    all_conversations = client.get(
        "/api/v1/ai/conversations?include_archived=true",
        headers=customer_headers,
    )
    archived_item = next(item for item in all_conversations.json() if item["id"] == first_id)
    assert archived_item["archived_at"]

    restored = client.patch(
        f"/api/v1/ai/conversations/{first_id}",
        json={"archived": False, "title": "已恢复"},
        headers=customer_headers,
    )
    assert restored.status_code == 200
    assert restored.json()["archived_at"] is None
    assert restored.json()["title"] == "已恢复"


def test_user_cannot_read_other_user_conversation(client, customer_headers, photographer_headers):
    created = client.post("/api/v1/ai/conversations", json={}, headers=customer_headers)
    conversation_id = created.json()["id"]

    res = client.get(f"/api/v1/ai/conversations/{conversation_id}/messages", headers=photographer_headers)

    assert res.status_code == 404


def test_get_conversation_metadata(client, customer_headers):
    created = client.post("/api/v1/ai/conversations", json={"title": "详情"}, headers=customer_headers)
    response = client.get(
        f"/api/v1/ai/conversations/{created.json()['id']}",
        headers=customer_headers,
    )
    assert response.status_code == 200
    assert response.json()["title"] == "详情"
    assert response.json()["status"] == "active"


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
