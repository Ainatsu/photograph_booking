from backend.app.models.ai_conversation import AIConversationTaskLink, AIMessage
from backend.app.models.agent_task import AgentTaskDraft


def test_fork_copies_history_but_creates_independent_task(client, db, customer_headers, customer_user):
    source = client.post("/api/v1/ai/conversations", json={"title": "香港婚礼"}, headers=customer_headers).json()
    first = AIMessage(conversation_id=source["id"], role="user", content="找香港婚礼摄影师")
    second = AIMessage(conversation_id=source["id"], role="assistant", content="推荐维港夜景团队")
    task = AgentTaskDraft(
        id="source-task", conversation_id=source["id"], user_id=customer_user.id,
        task_type="create_project", status="collecting", schema_version=2, revision=2,
        target={}, fields={"city": "香港"}, field_sources={}, media_assets=[],
    )
    db.add_all([first, second, task])
    db.commit()

    response = client.post(
        f"/api/v1/ai/conversations/{source['id']}/fork",
        json={"task_id": task.id}, headers=customer_headers,
    )
    assert response.status_code == 201
    child = response.json()
    assert child["forked_from_conversation_id"] == source["id"]
    assert child["root_conversation_id"] == source["id"]
    assert child["active_task_id"] != task.id
    messages = client.get(f"/api/v1/ai/conversations/{child['id']}/messages", headers=customer_headers).json()
    assert [item["content"] for item in messages] == [first.content, second.content]
    copied = db.query(AgentTaskDraft).filter_by(id=child["active_task_id"]).one()
    assert copied.conversation_id == child["id"]
    assert copied.fields == {"city": "香港"}
    assert db.query(AIConversationTaskLink).filter_by(source_task_id=task.id, target_task_id=copied.id).one()


def test_turn_fork_stops_at_requested_message(client, db, customer_headers):
    source = client.post("/api/v1/ai/conversations", json={}, headers=customer_headers).json()
    messages = [AIMessage(conversation_id=source["id"], role="user", content=value) for value in ("一", "二", "三")]
    db.add_all(messages)
    db.commit()
    response = client.post(f"/api/v1/ai/conversations/{source['id']}/fork", json={"turn_id": messages[1].id}, headers=customer_headers)
    copied = client.get(f"/api/v1/ai/conversations/{response.json()['id']}/messages", headers=customer_headers).json()
    assert [item["content"] for item in copied] == ["一", "二"]


def test_folders_are_user_owned(client, customer_headers, photographer_headers):
    folder = client.post("/api/v1/ai/conversation-folders", json={"name": "婚礼", "sort_order": 2}, headers=customer_headers).json()
    conversation = client.post("/api/v1/ai/conversations", json={}, headers=customer_headers).json()
    assigned = client.post(f"/api/v1/ai/conversations/{conversation['id']}/folder?folder_id={folder['id']}", headers=customer_headers)
    assert assigned.status_code == 200
    assert assigned.json()["folder_id"] == folder["id"]
    foreign = client.post("/api/v1/ai/conversations", json={}, headers=photographer_headers).json()
    denied = client.post(f"/api/v1/ai/conversations/{foreign['id']}/folder?folder_id={folder['id']}", headers=photographer_headers)
    assert denied.status_code == 404


def test_search_matches_metadata_task_and_resource_names(client, db, customer_headers, customer_user):
    city = client.post("/api/v1/ai/conversations", json={"title": "香港婚礼"}, headers=customer_headers).json()
    resource = client.post("/api/v1/ai/conversations", json={"title": "候选"}, headers=customer_headers).json()
    task = client.post("/api/v1/ai/conversations", json={"title": "工作流"}, headers=customer_headers).json()
    db.add(AIMessage(conversation_id=resource["id"], role="assistant", content="结果", message_metadata={"references": {"packages": [{"name": "维港夜景套餐"}]}}))
    db.add(AgentTaskDraft(id="search-task", conversation_id=task["id"], user_id=customer_user.id, task_type="create_booking", status="completed", schema_version=2, revision=0, target={}, fields={}, field_sources={}, media_assets=[]))
    db.commit()
    assert client.get("/api/v1/ai/conversations/search?q=香港", headers=customer_headers).json()[0]["id"] == city["id"]
    assert client.get("/api/v1/ai/conversations/search?q=维港夜景套餐", headers=customer_headers).json()[0]["id"] == resource["id"]
    assert client.get("/api/v1/ai/conversations/search?q=create_booking", headers=customer_headers).json()[0]["id"] == task["id"]
