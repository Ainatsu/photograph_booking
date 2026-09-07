from types import SimpleNamespace

from backend.app.services.agent_context_envelope_service import build_context_envelope


def test_context_envelope_bounds_dialogue_and_labels_retained_context():
    envelope = build_context_envelope(
        conversation=SimpleNamespace(id=1, user_id=2, status="active", title="x"),
        current_request={"content": "当前条件"},
        active_task={"task_id": "t1"},
        recent_dialogue=[{"role": "user", "content": "x" * 1000} for _ in range(20)],
        retained_context={"summary_version": 1, "summary": "历史背景", "retained_facts": ["北京"]},
        max_context_chars=2500,
    )
    assert len(str(envelope["recent_dialogue"])) < 2500
    assert envelope["retained_context"]["summary"] == "历史背景"
    assert {item["source"] for item in envelope["provenance"]} >= {"history_compression", "current_message"}

