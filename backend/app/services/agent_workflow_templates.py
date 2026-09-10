"""Workflow 输入模板的白名单解析（workflow 阶段 C）。

按文档 §6/§7 解析 step.input_template 中的 `$` 引用，只允许三个根：
- ``$input.<path>``     run 级输入；
- ``$context.<path>``   已完成步骤合并出的 workflow context；
- ``$steps.<key>.result[.<path>]``  指定步骤通过 output schema 校验的 data。

其余一切以 ``$`` 开头的字符串（未知根、越权字段、未完成步骤、裸 ``$``）
一律抛 TemplateResolutionError，由 Runtime 转为步骤失败——fail closed，
防止计划注入任意读取。解析只做整值替换，不支持字符串内插。
"""

from __future__ import annotations

from typing import Any

from backend.app.models.agent_workflow import AgentWorkflowStep


class TemplateResolutionError(Exception):
    """模板解析失败，code 供 Runtime 映射到步骤 error。"""

    def __init__(self, code: str, message: str = ""):
        super().__init__(message or code)
        self.code = code
        self.message = message or code


_ALLOWED_ROOTS = frozenset({"input", "context", "steps"})

# build_step_view 中标记"步骤存在但结果尚未可用"的哨兵。
_UNSET = object()


def resolve_input_template(
    template: dict[str, Any] | None,
    *,
    run_input: dict[str, Any] | None,
    run_context: dict[str, Any] | None,
    step_view: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """递归解析 input_template，返回可执行的结构化输入。"""
    if not template:
        return {}
    resolved = _resolve_value(
        template,
        run_input=run_input or {},
        run_context=run_context or {},
        step_view=step_view or {},
    )
    return resolved


def build_step_view(steps: list[AgentWorkflowStep]) -> dict[str, Any]:
    """从 step rows 构造解析视图：{step_key: {"result": data | _UNSET}}。

    只有 completed 步骤的 result["data"]（已过 output schema 校验）可被
    引用；未完成步骤的 result 位置放哨兵，引用时报 missing_step。
    """
    view: dict[str, Any] = {}
    for step in steps:
        envelope = step.result if isinstance(step.result, dict) else None
        if step.status == "completed" and envelope is not None:
            view[step.step_key] = {"result": envelope.get("data") or {}}
        else:
            view[step.step_key] = {"result": _UNSET}
    return view


# ── 内部解析 ─────────────────────────────────────────────────────────────────


def _resolve_value(
    value: Any,
    *,
    run_input: dict[str, Any],
    run_context: dict[str, Any],
    step_view: dict[str, Any],
) -> Any:
    if isinstance(value, dict):
        return {
            key: _resolve_value(item, run_input=run_input, run_context=run_context, step_view=step_view)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            _resolve_value(item, run_input=run_input, run_context=run_context, step_view=step_view)
            for item in value
        ]
    if isinstance(value, str) and value.startswith("$"):
        return _resolve_reference(
            value,
            run_input=run_input,
            run_context=run_context,
            step_view=step_view,
        )
    return value


def _resolve_reference(
    reference: str,
    *,
    run_input: dict[str, Any],
    run_context: dict[str, Any],
    step_view: dict[str, Any],
) -> Any:
    segments = reference[1:].split(".")
    if len(segments) < 2:
        raise TemplateResolutionError(
            "invalid_template",
            f"template must be $<root>.<path>: {reference!r}",
        )
    root = segments[0]
    if not root or root not in _ALLOWED_ROOTS:
        raise TemplateResolutionError(
            "invalid_root",
            f"unknown template root: {root!r}",
        )
    if root == "steps":
        return _resolve_steps_reference(reference, segments, step_view=step_view)
    source = run_input if root == "input" else run_context
    return _walk_path(reference, segments[1:], source)


def _resolve_steps_reference(
    reference: str,
    segments: list[str],
    *,
    step_view: dict[str, Any],
) -> Any:
    step_key = segments[1]
    if step_key not in step_view:
        raise TemplateResolutionError(
            "missing_step",
            f"template references unknown step: {step_key!r}",
        )
    if len(segments) < 3:
        raise TemplateResolutionError(
            "forbidden_step_field",
            f"only $steps.<key>.result is allowed: {reference!r}",
        )
    if segments[2] != "result":
        raise TemplateResolutionError(
            "forbidden_step_field",
            f"step field {segments[2]!r} is not allowed, only result: {reference!r}",
        )
    data = step_view[step_key]["result"]
    if data is _UNSET:
        raise TemplateResolutionError(
            "missing_step",
            f"template references step {step_key!r} whose result is not available yet",
        )
    return _walk_path(reference, segments[3:], data)


def _walk_path(reference: str, segments: list[str], source: Any) -> Any:
    """按段遍历 dict 键与 list 整数下标；路径不存在即报 missing_path。"""
    current = source
    for segment in segments:
        if isinstance(current, dict):
            if segment not in current:
                raise TemplateResolutionError(
                    "missing_path",
                    f"path {segment!r} not found for template {reference!r}",
                )
            current = current[segment]
        elif isinstance(current, list) and segment.isdigit():
            index = int(segment)
            if index >= len(current):
                raise TemplateResolutionError(
                    "missing_path",
                    f"index {segment} out of range for template {reference!r}",
                )
            current = current[index]
        else:
            raise TemplateResolutionError(
                "missing_path",
                f"path {segment!r} not traversable for template {reference!r}",
            )
    return current
