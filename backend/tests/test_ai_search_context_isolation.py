from types import SimpleNamespace

from backend.app.services.ai_search_context_service import (
    build_search_context,
    resolve_refinement,
)


def test_search_context_records_task_identity():
    context = build_search_context(
        retrieval={
            "criteria": {"resource_types": ["packages"], "city": "大理", "style_terms": ["写真"]},
            "references": {"packages": [{"package_id": "p1", "package_name": "大理方案"}]},
            "diagnostics": {},
        },
        intent=SimpleNamespace(intent="resource_search", slots={}),
        task_id="task-package-1",
        task_type="package_search",
        revision=2,
    )

    assert context["task_id"] == "task-package-1"
    assert context["task_type"] == "package_search"
    assert context["revision"] == 2


def test_refinement_can_be_rejected_when_context_identity_is_stale():
    previous = {
        "task_id": "old-task",
        "task_type": "portfolio_item_search",
        "slots": {"resource_types": ["portfolio_items"], "styles": ["胶片"]},
        "recommended_resource_ids": ["w1"],
    }
    current_task = {"task_id": "new-task", "task_type": "package_search", "status": "active"}

    usable = previous if previous["task_id"] == current_task["task_id"] else None

    assert resolve_refinement("换一个", usable) is None
