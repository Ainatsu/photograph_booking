from types import SimpleNamespace

from backend.app.services.agent_context_envelope_service import (
    build_context_envelope,
    build_context_envelope_prompt,
)


def test_context_envelope_excludes_unsupplied_candidate_memories_and_labels_sources():
    envelope = build_context_envelope(
        conversation=SimpleNamespace(id=7, user_id=3, status="active", title="测试"),
        current_request={"content": "本轮明确选择北京"},
        active_task={"task_id": "task-1", "slots": {"city": "北京"}},
        recent_dialogue=[{"role": "user", "content": "上一轮"}],
        active_user_memories=[{"memory_type": "location_interest", "key": "香港", "value": {"name": "香港"}}],
    )
    assert envelope["active_user_memories"][0]["key"] == "香港"
    assert "candidate" not in envelope
    assert {item["source"] for item in envelope["provenance"]} == {
        "current_message", "active_task", "recent_dialogue", "active_long_term_memory",
    }


def test_context_prompt_states_current_request_precedence():
    prompt = build_context_envelope_prompt({"current_request": {"content": "北京"}})
    assert "current_request > active_task" in prompt
    assert "长期画像只能作为弱参考" in prompt
