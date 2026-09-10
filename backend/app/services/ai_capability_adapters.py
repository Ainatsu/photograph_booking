"""Agent 统一能力适配层（workflow 阶段 A）。

把现有视觉 skill、检索工具和灵感草稿工具包装成统一的能力协议：
adapter 只负责调用既有 service 并返回 data，信封组装、schema 校验、
错误捕获与 provenance 由 ai_capability_registry.execute_capability 统一执行。

现有 service 不重写：视觉 provider 调用复刻 ai_service.py 的内联分支
（同 skill prompt、同消息构建），检索直接复用 run_search_tool，
灵感草稿直接复用 ai_agent_tool_service.create_inspiration_draft。
"""

from __future__ import annotations

from time import perf_counter
from typing import Any

from sqlalchemy.orm import Session

from backend.app.services.ai_provider import get_ai_provider
from backend.app.services.ai_vision_service import (
    APPRECIATION_SYSTEM_PROMPT,
    STYLE_ANALYSIS_SYSTEM_PROMPT,
    VISION_SYSTEM_PROMPT,
    build_vision_search_text,
    normalize_vision_analysis,
)
from backend.app.services.ai_search_tool_service import run_search_tool
from backend.app.services.ai_agent_tool_service import create_inspiration_draft as create_inspiration_draft_tool

# VisionSkillInput 等契约模型由 registry 负责校验，这里只做类型提示。
from backend.app.services.ai_capability_contracts import VisionSkillInput


def _provider_messages(
    db: Session,
    conversation_id: int,
    extra_system_prompts: list[str],
) -> list[dict]:
    """构建发送给 provider 的历史消息（含图片附件）。

    惰性导入避免 ai_service → registry → adapters → ai_service 的循环导入；
    阶段 E 再考虑把消息构建抽到共享模块。
    """
    from backend.app.services.ai_service import _build_provider_messages

    return _build_provider_messages(
        db,
        conversation_id,
        extra_system_prompts=extra_system_prompts,
    )


async def _run_vision_provider(
    db: Session,
    skill_input: VisionSkillInput,
    *,
    system_prompt: str,
) -> dict[str, Any]:
    """调用视觉 skill 的底层 LLM provider 并返回原始结果。"""
    provider_messages = _provider_messages(
        db,
        skill_input.conversation_id,
        extra_system_prompts=[system_prompt],
    )
    provider = get_ai_provider()
    return await provider.chat(provider_messages)


async def vision_analyze_image(
    db: Session,
    skill_input: VisionSkillInput,
    *,
    context: dict[str, Any],
) -> dict[str, Any]:
    """结构化图片分析：normalize_vision_analysis + 派生 search_query。"""
    provider_result = await _run_vision_provider(
        db,
        skill_input,
        system_prompt=VISION_SYSTEM_PROMPT,
    )
    analysis = normalize_vision_analysis(
        provider_result,
        content=skill_input.content,
        attachments=[item.model_dump() for item in skill_input.attachments],
    )
    return {
        **analysis,
        "search_query": build_vision_search_text(skill_input.content, analysis),
        "provider_metadata": dict(provider_result.get("metadata") or {}),
    }


async def vision_appreciate_image(
    db: Session,
    skill_input: VisionSkillInput,
    *,
    context: dict[str, Any],
) -> dict[str, Any]:
    """作品赏析：自由文本输出，不做结构化解析。"""
    provider_result = await _run_vision_provider(
        db,
        skill_input,
        system_prompt=APPRECIATION_SYSTEM_PROMPT,
    )
    return {
        "schema_version": "work_appreciation_v1",
        "reply": (provider_result.get("content") or "").strip(),
        "provider_metadata": dict(provider_result.get("metadata") or {}),
    }


async def vision_analyze_style(
    db: Session,
    skill_input: VisionSkillInput,
    *,
    context: dict[str, Any],
) -> dict[str, Any]:
    """风格分析：自由文本输出（视觉事实→风格 DNA 逐层结论）。"""
    provider_result = await _run_vision_provider(
        db,
        skill_input,
        system_prompt=STYLE_ANALYSIS_SYSTEM_PROMPT,
    )
    return {
        "schema_version": "style_analysis_v1",
        "reply": (provider_result.get("content") or "").strip(),
        "provider_metadata": dict(provider_result.get("metadata") or {}),
    }


# ── 检索能力 ─────────────────────────────────────────────────────────────────


_SEARCH_TOOL_NAMES: dict[str, str] = {
    "photographer.search": "search_photographers",
    "portfolio.search": "search_portfolio_items",
    "package.search": "search_packages",
}


def _search_artifacts(resource_type: str, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """把检索结果条目转换为 artifact 列表（真实资源引用）。"""
    return [
        {
            "resource_type": resource_type,
            "resource_id": item.get("id") or item.get("user_id") or item.get("package_id"),
        }
        for item in items
    ]


async def run_resource_search(
    db: Session,
    search_input: Any,
    *,
    context: dict[str, Any],
) -> dict[str, Any]:
    """检索能力 adapter：复用 run_search_tool 并映射为 adapter 协议。

    search_input 是经 spec.input_model 校验后的 Pydantic 实例（含可能新增的
    extra 字段），这里只取 model_dump 的 JSON 安全形态传给 run_search_tool。
    """
    capability_name = context["capability_name"]
    tool_name = _SEARCH_TOOL_NAMES[capability_name]
    arguments = search_input.model_dump(mode="json", exclude_none=True)
    tool_call = run_search_tool(
        db,
        tool_name=tool_name,
        arguments=arguments,
        user=context.get("user"),
        vision_analysis=context.get("vision_analysis"),
        image_attachments=context.get("image_attachments"),
        request_content=context.get("request_content"),
    )
    result = tool_call.get("result") or {}
    items = result.get("items") or []
    return {
        **result,
        "status": tool_call.get("status"),
        "artifacts": _search_artifacts(result.get("resource_type") or "", items),
        "retrieval": tool_call.get("retrieval"),
        "payload": tool_call.get("payload"),
    }


async def compose_response_adapter(
    db: Session,
    compose_input: Any,
    *,
    context: dict[str, Any],
) -> dict[str, Any]:
    """最终回复组装 adapter：复用阶段 D workflow 模块的纯代码 compose 逻辑。"""
    from backend.app.services.agent_workflow_appreciation_search import (
        compose_appreciation_search,
    )

    return compose_appreciation_search(
        user_request=compose_input.user_request,
        appreciation=compose_input.appreciation,
        analysis=compose_input.analysis,
        search=compose_input.search,
    )


# ── 灵感草稿能力 ─────────────────────────────────────────────────────────────


async def create_inspiration_draft_adapter(
    db: Session,
    tool_input: Any,
    *,
    context: dict[str, Any],
) -> dict[str, Any]:
    """灵感草稿 adapter：直接复用既有工具（policy 校验、action log、幂等 replay）。"""
    started_at = perf_counter()
    payload = tool_input.model_dump(mode="json", exclude_none=True)
    images = payload.pop("images", []) or []
    inspiration_payload: dict[str, Any] = {
        "title": "拍摄灵感",
        "summary": (payload.get("reference_text") or "参考图片灵感")[:300] or "参考图片灵感",
        "tags": [],
        "content": [],
        "cover_url": images[0].get("url") if images else None,
    }
    tool_call = create_inspiration_draft_tool(
        db,
        user_id=context["user_id"],
        conversation_id=context["conversation_id"],
        message_id=context.get("message_id"),
        inspiration_payload=inspiration_payload,
        idempotency_key=context.get("idempotency_key"),
        commit=context.get("commit", True),
    )
    replayed = bool((tool_call.get("policy") or {}).get("replayed"))
    return {
        **(tool_call.get("result") or {}),
        "status": tool_call.get("status"),
        "replayed": replayed,
        "tool_input": tool_call.get("input"),
        "duration_ms": round((perf_counter() - started_at) * 1000),
    }


# ── 灵感生成能力（workflow 阶段 E：search_then_inspire） ─────────────────────


# 与 legacy compound_workflow 分支一致的可用参考图上限。
_MAX_INSPIRATION_IMAGES = 12

_NO_USABLE_IMAGES_MESSAGE = "没有找到包含可用静态图片的匹配作品，请调整风格、城市或预算后重试。"


def _usable_inspiration_images(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """从 search 步骤的真实 items 里过滤可用静态图（复刻 legacy compound 分支）。

    跳过视频条目和无 url 条目；provider_image_url 经惰性导入复用
    ai_service._image_url_for_provider（同 _provider_messages 的防循环导入模式）。
    """
    from backend.app.services.ai_service import _image_url_for_provider

    trusted_images: list[dict[str, Any]] = []
    for item in items[:_MAX_INSPIRATION_IMAGES]:
        payload = item if isinstance(item, dict) else {}
        media_type = payload.get("media_type") or "image"
        url = payload.get("url") or payload.get("thumbnail_url")
        if media_type == "video" or not isinstance(url, str) or not url.strip():
            continue
        trusted_images.append({
            "attachment_index": len(trusted_images),
            "url": url,
            "thumb_url": payload.get("thumbnail_url"),
            "mime_type": "image/jpeg",
            "provider_image_url": _image_url_for_provider(
                {"url": url, "mime_type": "image/jpeg"},
                max_edge=1280,
                jpeg_quality=82,
            ),
        })
    return trusted_images


async def inspiration_generate(
    db: Session,
    skill_input: Any,
    *,
    context: dict[str, Any],
) -> dict[str, Any]:
    """灵感生成 adapter：包装 create_inspiration_workflow（任务草稿 + 异步生成 job）。

    无可用静态图是合法完成（与 legacy 文案一致），不作为步骤失败。
    """
    from backend.app.services.inspiration_agent_workflow_service import (
        create_inspiration_workflow,
    )

    reference_text = (skill_input.reference_text or "").strip()
    trusted_images = _usable_inspiration_images(skill_input.items or [])
    if not trusted_images:
        return {
            "schema_version": "inspiration_generate_v1",
            "flow_status": "failed",
            "content": _NO_USABLE_IMAGES_MESSAGE,
            "error": {"code": "no_usable_images"},
            "inspiration_flow": {"status": "failed", "error": "no_usable_images"},
            "active_task": None,
        }

    result = await create_inspiration_workflow(
        db,
        user_id=context["user_id"],
        conversation_id=context["conversation_id"],
        message_id=context.get("message_id"),
        reference_text=reference_text,
        images=trusted_images,
    )
    metadata = result.get("metadata") or {}
    flow = metadata.get("inspiration_flow") or {}
    flow_status = flow.get("status") or "failed"
    return {
        "schema_version": "inspiration_generate_v1",
        "flow_status": flow_status,
        "content": result.get("content") or "",
        "inspiration_id": flow.get("inspiration_id"),
        "entry": flow.get("entry"),
        "inspiration_flow": flow,
        "active_task": metadata.get("active_task"),
        "error": {"code": flow.get("error")} if flow.get("status") == "failed" else None,
    }


# ── 预订创建能力（workflow 阶段 E：booking_flow 拆解 + waiting_user） ────────


class _IntentSlotsShim:
    """给 booking_plan_result 提供只含 slots 的最小 intent 形状。"""

    def __init__(self, slots: dict[str, Any]):
        self.slots = slots or {}


def _pick_package_from_items(
    content: str | None,
    items: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """从本轮 search 步骤的套餐 items 里按 legacy 规则挑选（名称→索引→兜底）。"""
    if not items:
        return None
    from backend.app.services.ai_booking_service import (
        _match_package_by_name,
        _requested_reference_index,
    )

    named = _match_package_by_name(content, items)
    if named:
        return named
    index = _requested_reference_index(content)
    if index is not None and 0 <= index < len(items):
        return items[index]
    text = (content or "").strip()
    if any(term in text for term in ("便宜", "价格低", "最低价")):
        return min(items, key=lambda pkg: float(pkg.get("price") or 0))
    return items[0]


def _booking_envelope(envelope_status: str, result: dict[str, Any]) -> dict[str, Any]:
    """把 legacy 结果构造器的输出映射为 capability data + 信封状态。"""
    metadata = result.get("metadata") or {}
    task_state = metadata.get("task_state") or {}
    return {
        "status": envelope_status,
        "schema_version": "booking_create_v1",
        "stage": task_state.get("status") or "failed",
        "content": result.get("content") or "",
        "metadata": metadata,
    }


async def booking_create(
    db: Session,
    tool_input: Any,
    *,
    context: dict[str, Any],
) -> dict[str, Any]:
    """预订创建 adapter：复刻 booking_agent_result 的阶段分支。

    与 legacy 的差异只有两点：状态来源从「最近 assistant 消息 task_state」
    换成 run.input 注入的 slots/task_state；确认标志由调用方完成
    _is_explicit_task_confirmation 校验后经 confirmed 传入。回复正文、
    task_state、pending_action、task_plan 全部复用 legacy 构造器，
    保证新旧执行结果与审计记录一致。
    """
    from backend.app.services import ai_planner_service
    from backend.app.services.ai_booking_service import (
        _attach_booking_plan,
        _ask_for_date_result,
        _confirmation_result,
        _execute_booking_result,
        _find_package_in_profile,
        _format_package_for_display,
        _latest_referenced_package,
        _missing_photographer_or_package_result,
        _normalize_package,
        _preserve_booking_slots,
        _resolve_photographer,
    )

    conversation_id = context["conversation_id"]
    content = tool_input.user_request
    slots = dict(tool_input.slots or {})
    items = [dict(item) for item in (tool_input.items or []) if isinstance(item, dict)]

    # 摄影师：slots → 本轮检索 items → 历史 references（同 legacy 顺序扩展）。
    photographer = _resolve_photographer(db, conversation_id, content, slots)
    if photographer is None:
        item = _pick_package_from_items(content, items)
        if item and item.get("photographer_id"):
            photographer = {
                "user_id": item["photographer_id"],
                "user_display_name": item.get("photographer_name") or f"摄影师 {item['photographer_id']}",
            }

    # 套餐：selected_package → package_id 档案 → 本轮 items → 历史 references → 档案检索。
    package_info = None
    selected_package = slots.get("selected_package")
    if isinstance(selected_package, dict):
        package_info = {"package": _normalize_package(selected_package)}
    if package_info is None and photographer and slots.get("package_id"):
        from backend.app.services.ai_booking_service import _resolve_package

        package_info = _resolve_package(db, conversation_id, content, slots, photographer)
    if package_info is None:
        item = _pick_package_from_items(content, items)
        if item:
            package_info = {"package": _normalize_package(item)}
    if package_info is None:
        pkg = _latest_referenced_package(db, conversation_id, content)
        if pkg:
            package_info = {"package": _normalize_package(pkg)}
    if package_info is None and photographer:
        package_hint = slots.get("package_name") or content
        found = _find_package_in_profile(db, photographer["user_id"], package_hint)
        if found:
            package_info = {"package": found}

    if not photographer or not package_info:
        return _booking_envelope(
            "waiting_user",
            _missing_photographer_or_package_result(),
        )

    photographer_name = photographer.get("user_display_name") or f"摄影师 {photographer['user_id']}"
    pkg = package_info["package"]
    pkg_display = _format_package_for_display(pkg, photographer_name)
    photographer_id = photographer["user_id"]
    duration_minutes = pkg.get("duration") or 120
    slots.update({
        "photographer_id": photographer_id,
        "photographer_name": photographer_name,
        "package_id": pkg.get("id"),
        "package_name": pkg.get("name"),
        "package_display": pkg_display,
        "selected_package": pkg,
        "duration_minutes": duration_minutes,
    })

    appointment_date = slots.get("date")

    # 阶段 0：首轮缺日期 -> legacy booking_plan_result 的规划回复（含 agent_task_plan_v1）。
    if not appointment_date and tool_input.first_turn:
        return _booking_envelope(
            "waiting_user",
            ai_planner_service.booking_plan_result(
                intent=_IntentSlotsShim(tool_input.intent_slots or {}),
                retrieval={
                    "criteria": dict(tool_input.search_criteria or {}),
                    "references": {"packages": items},
                },
                vision_analysis=tool_input.vision_analysis or None,
                vision_reused_context=bool(tool_input.vision_reused_context),
            ),
        )

    # 阶段 1：缺日期 -> 询问日期 + 展示可预约日期。
    if not appointment_date:
        result = _ask_for_date_result(
            db=db,
            photographer_id=photographer_id,
            package_duration=duration_minutes,
            pkg_display=pkg_display,
            slots_data=slots,
        )
        result = _preserve_booking_slots(result, slots)
        return _booking_envelope(
            "waiting_user",
            _attach_booking_plan(
                result,
                tool_input.task_state,
                status="awaiting_date",
                completed_step_ids=("vision_analysis", "search_packages", "select_package"),
                current_step_id="select_date",
            ),
        )

    # 阶段 2：信息齐全但未显式确认 -> 等待用户确认（waiting_user）。
    if not tool_input.confirmed:
        result = _confirmation_result(
            photographer_name=photographer_name,
            pkg_display=pkg_display,
            appointment_date=appointment_date,
            slots_data=slots,
        )
        result = _preserve_booking_slots(result, slots)
        return _booking_envelope(
            "waiting_user",
            _attach_booking_plan(
                result,
                tool_input.task_state,
                status="awaiting_confirmation",
                completed_step_ids=(
                    "vision_analysis", "search_packages", "select_package",
                    "select_date", "confirm_booking",
                ),
            ),
        )

    # 阶段 3：显式确认 -> 调用 create_booking 工具（policy 校验、action log、幂等）。
    result = _execute_booking_result(
        db=db,
        user_id=context["user_id"],
        conversation_id=conversation_id,
        message_id=context.get("message_id"),
        photographer_id=photographer_id,
        package_display=pkg_display,
        appointment_date=appointment_date,
        duration_minutes=duration_minutes,
        photographer_name=photographer_name,
        slots_data=slots,
    )
    result = _preserve_booking_slots(result, slots)
    task_status = ((result.get("metadata") or {}).get("task_state") or {}).get("status")
    return _booking_envelope(
        "success",
        _attach_booking_plan(
            result,
            tool_input.task_state,
            status=task_status or "completed",
            completed_step_ids=(
                "vision_analysis", "search_packages", "select_package",
                "select_date", "confirm_booking", "create_booking",
            ) if task_status == "completed" else (
                "vision_analysis", "search_packages", "select_package",
                "select_date", "confirm_booking",
            ),
            failed_step_id="create_booking" if task_status == "failed" else None,
        ),
    )
