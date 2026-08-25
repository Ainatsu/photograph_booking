from backend.app.models.agent_task_session import AgentTaskSession
from backend.app.services import ai_service
from backend.app.services.agent_long_term_memory_service import finalize_task_memory
from backend.app.services.agent_task_memory_retrieval_service import (
    list_recent_task_episodes,
    resume_task,
    search_task_episodes,
    task_memory_mode,
)
from backend.app.services.agent_task_session_service import apply_task_workspace_update


def _paused_task(db, user_id, conversation_id, task_type, slots):
    task, _, _ = apply_task_workspace_update(
        db,
        user_id=user_id,
        conversation_id=conversation_id,
        task_type=task_type,
        slots=slots,
    )
    task.status = "paused"
    finalize_task_memory(db, task=task, outcome="paused")
    db.flush()
    return task


def test_history_is_disabled_without_explicit_intent():
    assert task_memory_mode("大理今天有什么新闻") == "none"
    assert task_memory_mode("我之前做过什么任务") == "summary"
    assert task_memory_mode("继续之前的大理方案") == "resume"


def test_episode_search_matches_city_without_returning_other_task(db, customer_user):
    conversation = ai_service.create_conversation(db, customer_user.id)
    dali = _paused_task(
        db, customer_user.id, conversation.id, "package_search", {"city": "大理"},
    )
    chongqing = _paused_task(
        db, customer_user.id, conversation.id, "photographer_search", {"city": "重庆"},
    )
    db.commit()

    results = search_task_episodes(
        db, user_id=customer_user.id, query="继续之前的大理方案", limit=5,
    )

    assert [item["task_id"] for item in results] == [dali.id]
    assert chongqing.id not in {item["task_id"] for item in results}
    assert len(list_recent_task_episodes(db, user_id=customer_user.id)) == 2


def test_resume_reuses_task_id_and_pauses_current_task(db, customer_user):
    conversation = ai_service.create_conversation(db, customer_user.id)
    dali = _paused_task(
        db, customer_user.id, conversation.id, "package_search", {"city": "大理"},
    )
    current, _, _ = apply_task_workspace_update(
        db,
        user_id=customer_user.id,
        conversation_id=conversation.id,
        task_type="photographer_search",
        slots={"city": "重庆"},
    )

    resumed, memory = resume_task(
        db,
        user_id=customer_user.id,
        conversation_id=conversation.id,
        task_id=dali.id,
    )
    db.commit()

    assert resumed.id == dali.id
    assert memory["task_id"] == dali.id
    assert memory["slots"] == {"city": "大理"}
    assert current.status == "paused"
    assert db.query(AgentTaskSession).filter_by(status="active").one().id == dali.id
