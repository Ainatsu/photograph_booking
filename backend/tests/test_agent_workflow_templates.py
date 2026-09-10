"""Workflow 输入模板解析测试（workflow 阶段 C）。

覆盖文档 §6 的白名单规则：
- ``$input`` / ``$context`` / ``$steps.<key>.result`` 的命中与深路径；
- 整值替换、非 ``$`` 字符串与嵌套容器透传；
- fail closed：未知根、越权步骤字段、未完成步骤、缺失路径、畸形引用全部拒绝。
"""

import pytest

from backend.app.models.agent_workflow import AgentWorkflowStep
from backend.app.services.agent_workflow_templates import (
    TemplateResolutionError,
    build_step_view,
    resolve_input_template,
)


def _resolve(template, *, run_input=None, run_context=None, step_view=None):
    return resolve_input_template(
        template,
        run_input=run_input or {},
        run_context=run_context or {},
        step_view=step_view or {},
    )


def _reject(template, *, code, run_input=None, run_context=None, step_view=None):
    with pytest.raises(TemplateResolutionError) as exc_info:
        _resolve(template, run_input=run_input, run_context=run_context, step_view=step_view)
    assert exc_info.value.code == code


def _row(key: str, status: str, result: dict | None = None) -> AgentWorkflowStep:
    return AgentWorkflowStep(step_key=key, status=status, result=result)


def _completed_view(key: str, data: dict) -> dict:
    return build_step_view([_row(key, "completed", {"data": data})])


# ── 命中路径 ──────────────────────────────────────────────────────────────────


def test_input_and_context_deep_paths():
    out = _resolve(
        {"attachments": "$input.request.attachments", "query": "$context.image_analysis.search_query"},
        run_input={"request": {"attachments": ["/static/ai/1/reference.jpg"]}},
        run_context={"image_analysis": {"search_query": "日系 窗边 低饱和"}},
    )
    assert out == {
        "attachments": ["/static/ai/1/reference.jpg"],
        "query": "日系 窗边 低饱和",
    }


def test_list_index_and_whole_container_reference():
    out = _resolve(
        {"first": "$input.tags.0", "all": "$context.image_analysis"},
        run_input={"tags": ["日系", "低饱和"]},
        run_context={"image_analysis": {"summary": "窗边人像"}},
    )
    assert out == {"first": "日系", "all": {"summary": "窗边人像"}}


def test_steps_result_reference_and_deep_path():
    view = _completed_view("analyze", {"summary": "窗边低饱和", "search_terms": ["日系", "低饱和"]})
    out = _resolve(
        {
            "analysis": "$steps.analyze.result",
            "first_term": "$steps.analyze.result.search_terms.0",
        },
        step_view=view,
    )
    assert out["analysis"] == {"summary": "窗边低饱和", "search_terms": ["日系", "低饱和"]}
    assert out["first_term"] == "日系"


def test_non_template_values_pass_through_unchanged():
    out = _resolve(
        {"limit": 6, "enabled": True, "text": "日系 低饱和", "none": None, "nested": ["keep", {"k": "v"}]},
    )
    assert out == {
        "limit": 6,
        "enabled": True,
        "text": "日系 低饱和",
        "none": None,
        "nested": ["keep", {"k": "v"}],
    }


def test_resolve_empty_template_returns_empty_dict():
    assert _resolve({}) == {}
    assert _resolve(None) == {}


# ── build_step_view ──────────────────────────────────────────────────────────


def test_build_step_view_only_exposes_completed_results():
    steps = [
        _row("analyze", "completed", {"data": {"summary": "窗边人像"}}),
        _row("search", "running", None),
        _row("compose", "pending", None),
        _row("legacy", "failed", {"data": {"summary": "不应可见"}}),
    ]
    view = build_step_view(steps)
    assert view["analyze"]["result"] == {"summary": "窗边人像"}
    # 未完成/失败步骤的结果不可引用。
    with pytest.raises(TemplateResolutionError) as exc_info:
        _resolve({"v": "$steps.search.result"}, step_view=view)
    assert exc_info.value.code == "missing_step"
    with pytest.raises(TemplateResolutionError) as exc_info:
        _resolve({"v": "$steps.legacy.result"}, step_view=view)
    assert exc_info.value.code == "missing_step"


def test_build_step_view_completed_step_without_result_envelope():
    view = build_step_view([_row("analyze", "completed", None)])
    with pytest.raises(TemplateResolutionError) as exc_info:
        _resolve({"v": "$steps.analyze.result"}, step_view=view)
    assert exc_info.value.code == "missing_step"


# ── fail closed 拒绝分支 ─────────────────────────────────────────────────────


def test_reject_unknown_root():
    _reject({"v": "$env.PASSWORD"}, code="invalid_root")
    _reject({"v": "$system.info.user_id"}, code="invalid_root")
    _reject({"v": "$.path"}, code="invalid_root")


def test_reject_malformed_references():
    _reject({"v": "$"}, code="invalid_template")
    _reject({"v": "$input"}, code="invalid_template")
    _reject({"v": "$context"}, code="invalid_template")


def test_reject_forbidden_step_field():
    view = _completed_view("analyze", {"summary": "x"})
    _reject({"v": "$steps.analyze.error"}, code="forbidden_step_field", step_view=view)
    _reject({"v": "$steps.analyze.idempotency_key"}, code="forbidden_step_field", step_view=view)
    _reject({"v": "$steps.analyze"}, code="forbidden_step_field", step_view=view)


def test_reject_missing_step():
    view = _completed_view("analyze", {"summary": "x"})
    _reject({"v": "$steps.search.result"}, code="missing_step", step_view=view)
    # 未完成步骤同样按 missing_step 拒绝。
    view = build_step_view([_row("analyze", "completed", {"data": {}}), _row("search", "running", None)])
    _reject({"v": "$steps.search.result"}, code="missing_step", step_view=view)


def test_reject_missing_path():
    _reject({"v": "$input.nope"}, code="missing_path", run_input={"other": 1})
    _reject({"v": "$context.image.nope"}, code="missing_path", run_context={"image": {}})
    view = _completed_view("analyze", {"summary": "x"})
    _reject({"v": "$steps.analyze.result.nope"}, code="missing_path", step_view=view)
    # 列表越界同样报 missing_path。
    _reject({"v": "$input.tags.5"}, code="missing_path", run_input={"tags": ["a"]})


def test_reject_traversable_mismatch():
    # list 上用非数字键不可遍历（dict 的数字字符串键是合法命中）。
    _reject({"v": "$input.tags.abc"}, code="missing_path", run_input={"tags": ["a"]})
    # 标量上继续取路径同样不可遍历。
    _reject({"v": "$input.count.unit"}, code="missing_path", run_input={"count": 3})


def test_reject_template_disguised_as_partial_string():
    # 以 $ 开头但整体不是合法引用的字符串一律 fail closed，不做内插。
    _reject({"v": "$input.attachments extra"}, code="missing_path", run_input={"attachments": []})
