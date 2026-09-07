from backend.app.services import agent_working_memory_service as memory_service


def _fake_cache(monkeypatch):
    values = {}

    monkeypatch.setattr(memory_service, "cache_get", values.get)
    monkeypatch.setattr(
        memory_service,
        "cache_set",
        lambda key, value, ttl=None: values.__setitem__(key, value),
    )
    monkeypatch.setattr(
        memory_service,
        "cache_delete",
        lambda *keys: [values.pop(key, None) for key in keys],
    )
    return values


def test_new_task_type_gets_clean_workspace(monkeypatch):
    _fake_cache(monkeypatch)

    portfolio = memory_service.update_working_memory(
        18, 12, task_type="portfolio_item_search",
        slots={"styles": ["日系", "胶片"], "makeup": True},
    )
    package = memory_service.update_working_memory(
        18, 12, task_type="package_search", slots={"city": "大理"},
    )

    assert package["task_id"] != portfolio["task_id"]
    assert package["slots"] == {"city": "大理"}
    assert memory_service.get_active_task_id(18, 12) == package["task_id"]


def test_same_task_type_merges_inside_same_workspace(monkeypatch):
    _fake_cache(monkeypatch)

    first = memory_service.update_working_memory(
        18, 12, task_type="package_search", slots={"city": "大理"},
    )
    second = memory_service.update_working_memory(
        18, 12, task_type="package_search", slots={"budget": 2000},
    )

    assert second["task_id"] == first["task_id"]
    assert second["slots"] == {"city": "大理", "budget": 2000}


def test_paused_workspace_is_not_active_context(monkeypatch):
    _fake_cache(monkeypatch)
    active = memory_service.update_working_memory(
        18, 12, task_type="package_search", slots={"city": "大理"},
    )

    paused = memory_service.pause_working_memory(18, 12)

    assert paused["task_id"] == active["task_id"]
    assert memory_service.get_active_task_id(18, 12) is None
    assert memory_service.get_working_memory(18, 12) is None
    assert memory_service.active_task_context(paused) is None


def test_explicit_task_type_mismatch_is_rejected(monkeypatch):
    _fake_cache(monkeypatch)
    active = memory_service.update_working_memory(
        18, 12, task_type="portfolio_item_search", slots={"styles": ["日系"]},
    )

    try:
        memory_service.update_working_memory(
            18, 12, task_id=active["task_id"], task_type="package_search",
            slots={"city": "大理"},
        )
    except ValueError as exc:
        assert "task_type mismatch" in str(exc)
    else:
        raise AssertionError("cross-task workspace reuse must be rejected")


def test_resource_text_summary_keeps_package_facts():
    summary = memory_service.resource_text_summary({
        "package_name": "大理旅拍全程跟拍",
        "price_label": "¥1500起",
        "description": "服装由我提供，不包含交通。",
        "includes": ["全程跟拍"],
        "weather_policy": "恶劣天气时不接",
    })

    assert "大理旅拍全程跟拍" in summary
    assert "恶劣天气时不接" in summary


def test_workspace_key_and_payload_are_conversation_scoped(monkeypatch):
    values = _fake_cache(monkeypatch)
    memory = memory_service.update_working_memory(
        18, 12, task_type="package_search", slots={"city": "大理"},
    )

    assert memory_service.task_workspace_key(18, 12, memory["task_id"]) in values
    assert memory["schema_version"] == memory_service.WORKING_MEMORY_SCHEMA_VERSION
    assert memory["user_id"] == 18
    assert memory["conversation_id"] == 12
    assert memory_service.get_working_memory(18, 13, task_id=memory["task_id"]) is None


def test_tampered_workspace_identity_fails_closed(monkeypatch):
    values = _fake_cache(monkeypatch)
    memory = memory_service.update_working_memory(
        18, 12, task_type="package_search", slots={"city": "大理"},
    )
    key = memory_service.task_workspace_key(18, 12, memory["task_id"])
    values[key]["conversation_id"] = 99
    assert memory_service.get_working_memory(18, 12, task_id=memory["task_id"]) is None
