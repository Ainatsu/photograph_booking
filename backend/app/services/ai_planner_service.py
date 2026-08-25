"""AI 预约规划：为预订流程生成任务计划与工具调用记录。"""

from copy import deepcopy
from typing import Any


TASK_PLAN_SCHEMA_VERSION = "agent_task_plan_v1"
DEFAULT_BOOKING_TIME = "12:00"

BOOKING_PLAN_STEP_IDS = (
    "vision_analysis",
    "search_packages",
    "select_package",
    "select_time",
    "confirm_booking",
    "create_booking",
)


def should_run_booking_plan(intent, retrieval: dict[str, Any] | None) -> bool:
    """判断是否应启动预订流程的任务计划。"""
    if intent.intent != "booking_flow":
        return False
    if intent.slots.get("date") or intent.slots.get("time"):
        return False
    references = (retrieval or {}).get("references") or {}
    return bool(references.get("packages"))


def booking_plan_result(
    *,
    intent,
    retrieval: dict[str, Any],
    vision_analysis: dict[str, Any] | None = None,
    vision_reused_context: bool = False,
) -> dict[str, Any]:
    """生成预订流程的规划结果（含任务计划与工具调用）。"""
    packages = ((retrieval or {}).get("references") or {}).get("packages") or []
    selected_package = packages[0] if packages else None
    if not selected_package:
        return _booking_plan_no_package_result(intent, retrieval, vision_analysis, vision_reused_context)

    photographer_id = selected_package.get("photographer_id")
    photographer_name = selected_package.get("photographer_name") or (
        f"摄影师 {photographer_id}" if photographer_id else "待确认摄影师"
    )
    package_name = selected_package.get("package_name") or selected_package.get("name") or "摄影套餐"
    normalized_package = _package_from_reference(selected_package)
    package_display = _format_package_for_display(normalized_package, photographer_name)
    duration_minutes = normalized_package.get("duration") or 120

    plan = _booking_plan(
        selected_package=selected_package,
        retrieval=retrieval,
        vision_analysis=vision_analysis,
        vision_reused_context=vision_reused_context,
        status="awaiting_date",
    )
    tool_calls = _planner_tool_calls(retrieval, vision_analysis, vision_reused_context)

    content = (
        "我先把这次拍摄拆成几个步骤：参考图分析、套餐筛选、确认拍摄时间，最后创建预约。\n\n"
        f"目前先选到一个匹配方案：{package_display}。\n"
        f"你想约哪一天？如果不指定具体时间，我会默认按 {DEFAULT_BOOKING_TIME} 帮你整理确认信息。"
    )

    return {
        "content": content,
        "metadata": {
            "model": {
                "provider": "platform_orchestrator",
                "model": "complex-task-planner",
            },
            **_vision_metadata(vision_analysis, vision_reused_context, retrieval),
            "task_plan": plan,
            "tool_calls": tool_calls,
            "suggested_actions": [],
            "task_state": {
                "task_type": "create_booking",
                "status": "awaiting_date",
                "slots": {
                    **intent.slots,
                    "resource_types": ["packages"],
                    "photographer_id": photographer_id,
                    "photographer_name": photographer_name,
                    "package_name": package_name,
                    "package_display": package_display,
                    "duration_minutes": duration_minutes,
                    "selected_package": selected_package,
                    "vision_context": "previous_turn" if vision_reused_context else (
                        "current_image" if vision_analysis else None
                    ),
                },
                "missing_slots": ["date"],
                "pending_action": None,
                "task_plan": plan,
            },
        },
    }


def advance_booking_plan(
    task_state: dict[str, Any] | None,
    *,
    status: str,
    completed_step_ids: tuple[str, ...] = (),
    current_step_id: str | None = None,
    failed_step_id: str | None = None,
) -> dict[str, Any] | None:
    """按完成/失败/进行中步骤推进任务计划状态。"""
    source = (task_state or {}).get("task_plan") or {}
    if source.get("schema_version") != TASK_PLAN_SCHEMA_VERSION:
        return None

    plan = deepcopy(source)
    plan["status"] = status
    completed = set(completed_step_ids)

    for step in plan.get("steps") or []:
        step_id = step.get("id")
        if failed_step_id and step_id == failed_step_id:
            step["status"] = "failed"
        elif step_id in completed:
            step["status"] = "completed"
        elif current_step_id and step_id == current_step_id:
            step["status"] = "in_progress"
        elif step.get("status") == "in_progress":
            step["status"] = "pending"

    return plan


def _booking_plan(
    *,
    selected_package: dict[str, Any] | None,
    retrieval: dict[str, Any],
    vision_analysis: dict[str, Any] | None,
    vision_reused_context: bool,
    status: str,
) -> dict[str, Any]:
    """构建预订流程的步骤计划字典。"""
    steps = []
    if vision_analysis:
        steps.append({
            "id": "vision_analysis",
            "agent": "vision",
            "status": "completed",
            "summary": "已复用上一轮参考图分析" if vision_reused_context else "已分析参考图风格",
        })
    steps.extend([
        {
            "id": "search_packages",
            "agent": "retrieval",
            "status": "completed" if selected_package else "failed",
            "summary": "已检索匹配套餐" if selected_package else "未找到匹配套餐",
        },
        {
            "id": "select_package",
            "agent": "booking",
            "status": "completed" if selected_package else "pending",
            "summary": selected_package.get("package_name") if selected_package else "等待用户补充条件",
        },
        {
            "id": "select_time",
            "agent": "booking",
            "status": "pending" if selected_package else "blocked",
            "summary": f"等待用户选择日期；未指定具体时间时默认 {DEFAULT_BOOKING_TIME}",
        },
        {
            "id": "confirm_booking",
            "agent": "booking",
            "status": "pending",
            "summary": "生成预约确认信息",
        },
        {
            "id": "create_booking",
            "agent": "booking",
            "status": "pending",
            "summary": "用户确认后创建预约",
            "requires_confirmation": True,
        },
    ])
    return {
        "schema_version": TASK_PLAN_SCHEMA_VERSION,
        "task_type": "booking_flow",
        "status": status,
        "steps": steps,
        "retrieval": {
            "criteria": (retrieval or {}).get("criteria") or {},
        },
    }


def _planner_tool_calls(
    retrieval: dict[str, Any],
    vision_analysis: dict[str, Any] | None,
    vision_reused_context: bool,
) -> list[dict[str, Any]]:
    """汇总规划过程中已执行工具的结果记录。"""
    calls = []
    if vision_analysis:
        calls.append({
            "tool": "reuse_vision_analysis" if vision_reused_context else "analyze_image",
            "status": "success",
            "input": {
                "source": "previous_turn" if vision_reused_context else "current_image",
            },
            "result": {
                "schema_version": vision_analysis.get("schema_version"),
                "style": vision_analysis.get("style") or [],
                "search_terms": vision_analysis.get("search_terms") or [],
            },
        })

    references = (retrieval or {}).get("references") or {}
    calls.append({
        "tool": "search_packages",
        "status": "success" if references.get("packages") else "empty",
        "input": (retrieval or {}).get("criteria") or {},
        "result": {
            "result_count": len(references.get("packages") or []),
        },
    })
    return calls


def _booking_plan_no_package_result(
    intent,
    retrieval: dict[str, Any] | None,
    vision_analysis: dict[str, Any] | None,
    vision_reused_context: bool,
) -> dict[str, Any]:
    """无匹配套餐时的预订规划兜底结果。"""
    plan = _booking_plan(
        selected_package=None,
        retrieval=retrieval or {},
        vision_analysis=vision_analysis,
        vision_reused_context=vision_reused_context,
        status="blocked",
    )
    return {
        "content": (
            "我已经分析了需求，但暂时没找到可以进入预约的套餐。"
            "你可以补充城市、预算或换一个风格，我再继续筛选。"
        ),
        "metadata": {
            "model": {
                "provider": "platform_orchestrator",
                "model": "complex-task-planner",
            },
            **_vision_metadata(vision_analysis, vision_reused_context, retrieval or {}),
            "task_plan": plan,
            "tool_calls": _planner_tool_calls(retrieval or {}, vision_analysis, vision_reused_context),
            "suggested_actions": [],
            "task_state": {
                "task_type": "create_booking",
                "status": "awaiting_package",
                "slots": {
                    **intent.slots,
                    "resource_types": ["packages"],
                },
                "pending_action": None,
                "task_plan": plan,
            },
        },
    }


def _package_from_reference(package: dict[str, Any]) -> dict[str, Any]:
    """从检索引用中提取套餐展示字段。"""
    return {
        "name": package.get("package_name") or package.get("name") or "",
        "price": package.get("price") or 0,
        "duration": package.get("duration") or package.get("duration_minutes") or 120,
        "image_count": package.get("image_count") or 0,
        "includes": package.get("includes") or [],
        "styles": package.get("styles") or [],
    }


def _format_package_for_display(package: dict[str, Any], photographer_name: str | None = None) -> str:
    """将套餐格式化为展示文本。"""
    parts = []
    if package.get("name"):
        parts.append(str(package["name"]))
    if package.get("price"):
        parts.append(f"{_format_number(package['price'])} 元")
    if package.get("duration"):
        parts.append(f"时长 {package['duration']} 分钟")
    if package.get("image_count"):
        parts.append(f"精修 {package['image_count']} 张")
    includes = package.get("includes") or []
    if includes:
        parts.append(f"包含：{'、'.join(includes[:3])}")

    package_text = " ".join(parts) if parts else "摄影套餐"
    if photographer_name:
        return f"{photographer_name} 的{package_text}"
    return package_text


def _format_number(value: Any) -> str:
    """格式化数字：整数省略小数位。"""
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return str(value)
    if numeric.is_integer():
        return str(int(numeric))
    return str(numeric)


def _vision_metadata(
    vision_analysis: dict[str, Any] | None,
    vision_reused_context: bool,
    retrieval: dict[str, Any],
) -> dict[str, Any]:
    """构建视觉分析的元数据（含检索条件）。"""
    if not vision_analysis:
        return {}
    return {
        "vision_analysis": vision_analysis,
        "vision_context": {
            "source": "previous_turn" if vision_reused_context else "current_image",
        },
        "vision_search": {
            "schema_version": "vision_search_v1",
            "search_text": ((retrieval or {}).get("criteria") or {}).get("text"),
            "resource_types": ((retrieval or {}).get("criteria") or {}).get("resource_types") or [],
            "filters": {
                "style": vision_analysis.get("style") or [],
                "scene": vision_analysis.get("scene") or [],
                "mood": vision_analysis.get("mood") or [],
                "makeup": vision_analysis.get("makeup") or [],
                "search_terms": vision_analysis.get("search_terms") or [],
            },
        },
    }
