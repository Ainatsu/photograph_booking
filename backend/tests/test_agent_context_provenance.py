from backend.app.services.ai_trace_service import record_agent_trace


def test_trace_persists_context_provenance(db, customer_user):
    from backend.app.services.ai_service import create_conversation

    conversation = create_conversation(db, customer_user.id)
    trace = record_agent_trace(
        db,
        user_id=customer_user.id,
        conversation_id=conversation.id,
        user_message_id=1,
        assistant_message_id=None,
        intent={"intent": "resource_search", "route": "search"},
        metadata={
            "context_provenance": {
                "active_task_id": "task-1",
                "active_task_type": "package_search",
                "workspace_source": "database",
                "workspace_revision": 3,
                "previous_search_task_id": "old-task",
                "task_transition": "replace",
                "stale_workspace_discarded": True,
                "task_type_mismatch": True,
                "cross_task_slots_blocked": ["styles"],
                "context_sources": ["current_message", "active_task"],
            },
            "model": {"provider": "test", "model": "test"},
        },
        total_latency_ms=1,
    )

    flags = trace.quality_flags
    assert flags["active_task_id"] == "task-1"
    assert flags["workspace_source"] == "database"
    assert flags["task_transition"] == "replace"
    assert flags["stale_workspace_discarded"] is True
    assert flags["cross_task_slots_blocked"] == ["styles"]
