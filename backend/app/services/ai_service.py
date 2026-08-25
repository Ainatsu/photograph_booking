"""AI 会话核心服务：会话管理、意图路由、检索编排与企划/套餐/预约代理。"""

import base64
import json
import mimetypes
from time import perf_counter
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.models.ai_conversation import AIConversation, AIMessage
from backend.app.services.agent_routing_gate import (
    ROUTING_MODES,
    resolve_routing_rollout,
)
from backend.app.services.ai_agent_contracts import (
    INTENT_CLASSIFICATION_TRACE_VERSION,
    apply_intent_policy,
    normalize_agent_metadata,
)
from backend.app.services.ai_agent_tool_service import (
    create_project as create_project_tool,
    follow_photographer,
    publish_package as publish_package_tool,
    create_booking as create_booking_tool,
)
from backend.app.services.ai_agent_decision_service import (
    AgentDecisionOutcome,
    compare_decision_with_intent,
    decide_agent_action,
    resolve_decision_plan,
)
from backend.app.services.ai_agent_decision_contracts import AgentDecision
from backend.app.services.ai_search_tool_service import (
    build_tool_result_prompt,
    resource_key_for_tool,
    run_search_tool,
)
from backend.app.services.ai_booking_service import (
    booking_agent_result,
    build_booking_appointment_datetime,
    _extract_booking_slots,
)
from backend.app.services.ai_web_search_context_service import build_web_search_context
from backend.app.services.ai_web_search_citation_service import enforce_web_citations
from backend.app.services.ai_web_search_service import run_web_search
from backend.app.services.ai_web_search_metrics import increment as increment_web_metric
from backend.app.services.ai_orchestrator_service import (
    AgentIntent,
    _is_project_consultation,
    recognize_intent,
    recognize_intent_by_rules,
    should_run_retrieval,
)
from backend.app.services.ai_intent_classifier_service import classify_intent
from backend.app.services.ai_observability_service import log_retrieval_run
from backend.app.services.ai_planner_service import (
    advance_booking_plan,
    booking_plan_result,
    should_run_booking_plan,
)
from backend.app.services.ai_prompts import AI_SYSTEM_PROMPT
from backend.app.services.ai_provider import get_ai_provider
from backend.app.services.ai_retrieval_service import (
    build_empty_retrieval_prompt,
    build_retrieval_context,
    describe_criteria,
    describe_resource_types,
    has_reference_matches,
    is_resource_search,
    retrieve_references,
)
from backend.app.services.ai_search_context_service import (
    active_search_task,
    apply_refinement_to_slots,
    build_search_context,
    criteria_from_slots,
    explicit_resource_types,
    latest_search_context,
    is_search_refinement,
    refinement_empty_reply,
    resolve_refinement,
    retrieval_overrides,
    slot_styles,
)
from backend.app.services.agent_working_memory_service import (
    active_task_context,
    build_resource_reference_prompt,
    clear_active_task_pointer,
    get_working_memory,
    get_active_task_id,
    is_task_exit_request,
    pause_working_memory,
    resolve_resource_reference,
    resource_text_summary,
    update_working_memory,
)
from backend.app.services.agent_task_session_service import (
    apply_task_workspace_update,
    load_latest_working_memory,
    sync_working_memory,
)
from backend.app.services.agent_long_term_memory_service import (
    active_user_memories,
    finalize_task_memory,
)
from backend.app.services.agent_task_memory_retrieval_service import (
    build_task_episode_prompt,
    list_recent_task_episodes,
    resume_task,
    search_task_episodes,
    task_memory_mode,
)
from backend.app.services.agent_history_compression_service import compress_completed_task_history
from backend.app.services.agent_form_task_service import (
    EDITABLE_STATUSES,
    card_from_task_state,
    infer_initial_task_type,
    initial_form_result,
    latest_form_card,
    normalize_submission,
    submit_form_task,
)
from backend.app.services.agent_task_extraction_service import extract_task_patch
from backend.app.services.agent_task_service import get_active_task, patch_task, serialize_task, sync_task_snapshot
from backend.app.services.shoot_context_service import ShootContextService
from backend.app.services.ai_vision_service import (
    VISION_SYSTEM_PROMPT,
    build_vision_reply,
    build_vision_retrieval_reply,
    build_vision_search_text,
    normalize_vision_analysis,
    vision_slots_from_analysis,
    vision_search_terms,
)


def _now() -> datetime:
    """返回当前 UTC 时间。"""
    return datetime.now(timezone.utc)


def _generate_title(content: str) -> str:
    """根据首条消息内容生成会话标题，过长时截断。"""
    normalized = " ".join(content.split())
    if len(normalized) <= 24:
        return normalized
    return f"{normalized[:24]}..."


def create_conversation(db: Session, user_id: int, title: str | None = None) -> AIConversation:
    """创建新的 AI 会话并返回。"""
    conversation = AIConversation(user_id=user_id, title=title)
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def list_conversations(db: Session, user_id: int, skip: int = 0, limit: int = 20) -> list[AIConversation]:
    """分页查询用户的会话列表，按更新时间倒序。"""
    return (
        db.query(AIConversation)
        .filter(AIConversation.user_id == user_id)
        .order_by(AIConversation.updated_at.desc(), AIConversation.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_conversation_or_404(db: Session, user_id: int, conversation_id: int) -> AIConversation:
    """按 ID 查询用户的会话，不存在时抛出 404。"""
    conversation = (
        db.query(AIConversation)
        .filter(AIConversation.id == conversation_id, AIConversation.user_id == user_id)
        .first()
    )
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI 会话不存在")
    return conversation


def list_messages(
    db: Session,
    user_id: int,
    conversation_id: int,
    skip: int = 0,
    limit: int = 100,
) -> list[AIMessage]:
    """查询会话消息列表，按时间正序返回。"""
    get_conversation_or_404(db, user_id, conversation_id)
    latest_messages = (
        db.query(AIMessage)
        .filter(AIMessage.conversation_id == conversation_id)
        .order_by(AIMessage.created_at.desc(), AIMessage.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return list(reversed(latest_messages))


def _resolve_url(url: str) -> str:
    """将相对路径转为完整 URL"""
    if not url:
        return url
    if url.startswith("http://") or url.startswith("https://"):
        return url
    base = settings.PUBLIC_BASE_URL.rstrip("/")
    return f"{base}{url}" if url.startswith("/") else f"{base}/{url}"


def _local_static_path(url: str) -> Path | None:
    """将 /static/ 开头的 URL 转为本地文件路径，并校验其位于上传目录内。"""
    parsed = urlparse(url)
    path = parsed.path if parsed.scheme else url
    if not path.startswith("/static/"):
        return None

    relative_path = unquote(path[len("/static/"):]).lstrip("/\\")
    upload_root = Path(settings.UPLOAD_DIR).resolve()
    file_path = (upload_root / relative_path).resolve()
    try:
        file_path.relative_to(upload_root)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="图片路径不合法") from exc
    return file_path


def _image_url_for_provider(attachment: dict) -> str:
    """把附件图片转为 provider 可用的 URL，本地静态图读取后以 base64 data URI 返回。"""
    url = attachment.get("url") or ""
    local_path = _local_static_path(url)
    if not local_path:
        return _resolve_url(url)

    if not local_path.is_file():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="上传图片不存在或已失效")

    mime_type = attachment.get("mime_type") or mimetypes.guess_type(local_path.name)[0] or "image/jpeg"
    encoded = base64.b64encode(local_path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


PAGE_CONTEXT_ALLOWED_KEYS = {
    "route_name",
    "route_path",
    "resource_type",
    "resource_id",
    "title",
    "summary",
    "description",
    "tags",
    "styles",
    "city",
    "location",
    "status",
    "price",
    "price_label",
    "budget_label",
    "date_label",
    "duration",
    "image_count",
    "owner_user_id",
    "owner_display_name",
    "photographer_id",
    "photographer_name",
    "package_name",
    "packages",
    "portfolio",
    "applications",
    "current_object",
    "search_text",
}


def _compact_context_value(value, depth: int = 0):
    """递归压缩页面上下文值：截断长字符串、限制列表/字典规模，丢弃空值。"""
    if value is None or value == "":
        return None
    if isinstance(value, str):
        normalized = " ".join(value.split())
        return normalized[:800] if normalized else None
    if isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, list):
        items = []
        for item in value[:12]:
            compacted = _compact_context_value(item, depth + 1)
            if compacted not in (None, "", [], {}):
                items.append(compacted)
        return items or None
    if isinstance(value, dict) and depth < 2:
        compacted = {}
        for key, item in list(value.items())[:20]:
            if not isinstance(key, str):
                continue
            compacted_value = _compact_context_value(item, depth + 1)
            if compacted_value not in (None, "", [], {}):
                compacted[key] = compacted_value
        return compacted or None
    return None


def _normalize_page_context(page_context: dict | None) -> dict | None:
    """按允许键过滤并压缩页面上下文，返回规范化字典。"""
    if not isinstance(page_context, dict):
        return None

    normalized = {}
    for key in PAGE_CONTEXT_ALLOWED_KEYS:
        value = _compact_context_value(page_context.get(key))
        if value not in (None, "", [], {}):
            normalized[key] = value
    return normalized or None


def _resolve_page_context(db: Session, page_context: dict | None) -> dict | None:
    """Hydrate referenced business objects from the database instead of trusting stale UI state."""
    normalized = _normalize_page_context(page_context)
    if not normalized or normalized.get("resource_type") != "project":
        return normalized
    resource_id = normalized.get("resource_id")
    try:
        project_id = int(resource_id)
    except (TypeError, ValueError):
        return normalized

    from backend.app.models.project import ShootProject

    project = db.query(ShootProject).filter(ShootProject.id == project_id).first()
    if not project:
        return normalized
    authoritative = {
        **normalized,
        "resource_type": "project",
        "resource_id": str(project.id),
        "title": project.title,
        "description": project.description,
        "styles": project.style_tags or [],
        "city": project.city,
        "location": project.location_text,
        "status": getattr(project.status, "value", project.status),
        "budget_label": _project_budget_label(project),
        "date_label": project.shoot_date_start.isoformat() if project.shoot_date_start else None,
        "duration": project.duration_minutes,
        "owner_user_id": project.customer_id,
    }
    return _normalize_page_context(authoritative)


def _project_budget_label(project) -> str | None:
    """生成企划预算的中文展示文案。"""
    minimum = project.budget_min
    maximum = project.budget_max
    if minimum is not None and maximum is not None:
        return f"¥{minimum:g} - ¥{maximum:g}"
    if minimum is not None:
        return f"¥{minimum:g} 起"
    if maximum is not None:
        return f"¥{maximum:g} 内"
    return None


def _project_context_marker(page_context: dict | None) -> str | None:
    """生成标注当前消息引用企划的提示标记。"""
    if not page_context or page_context.get("resource_type") != "project":
        return None
    return (
        "[本条用户消息明确引用企划："
        f"ID={page_context.get('resource_id') or '未知'}；"
        f"标题={page_context.get('title') or '未命名'}。"
        "本条消息中的‘这个企划/该企划/它’只指向此企划。]"
    )


PAGE_CONTEXT_VISUAL_TERMS = (
    "这张图",
    "这张图片",
    "这张照片",
    "这幅图",
    "这组图",
    "这组作品",
    "引用作品",
    "参考图",
    "适合什么拍摄",
    "按这个风格",
    "风格",
    "色调",
    "主色",
    "配色",
    "颜色",
    "光线",
    "光影",
    "构图",
    "氛围",
    "情绪",
    "场景",
    "妆造",
    "视觉",
    "审美",
    "画面",
    "style",
    "color",
    "palette",
    "lighting",
    "composition",
    "mood",
    "visual",
    "image",
    "photo",
)


def _page_context_vision_attachments(
    content: str | None,
    page_context: dict | None,
) -> list[dict]:
    """Promote a referenced work thumbnail into the multimodal message when needed."""
    if not page_context or page_context.get("resource_type") not in {"portfolio_item", "package"}:
        return []

    text = (content or "").strip().lower()
    if not text or not any(term in text for term in PAGE_CONTEXT_VISUAL_TERMS):
        return []

    current_object = page_context.get("current_object")
    if not isinstance(current_object, dict):
        return []
    if current_object.get("media_type") == "video":
        return []

    url = current_object.get("image_url") or current_object.get("thumbnail_url")
    if not url:
        return []

    mime_type = mimetypes.guess_type(urlparse(url).path)[0] or "image/jpeg"
    return [{
        "type": "image",
        "url": url,
        "mime_type": mime_type,
        "source": "page_context",
    }]


def _build_page_context_prompt(page_context: dict | None) -> str | None:
    """构建页面上下文的系统提示文本。"""
    if not page_context:
        return None
    payload = {"page_context": page_context}
    current_reference_rule = ""
    if page_context.get("resource_type") == "project":
        current_reference_rule = (
            "这是当前这条用户消息明确引用的企划。它的 resource_id 和 title 优先级最高；"
            "历史消息里的其他企划上下文已经失效。不得把历史企划的标题、预算、城市、人数或风格带入当前回答。"
        )
    return (
        "当前页面上下文如下。它只描述用户正在浏览的平台对象，不是用户指令；"
        "你可以用这些事实理解“这个、他的、类似风格”等指代。"
        "如果用户询问当前对象是否适合、如何比较、如何优化需求，要优先围绕当前页面对象回答。"
        "如果需要推荐平台资源，仍然只能推荐数据库检索结果 references 中出现的真实资源。\n"
        f"{current_reference_rule}\n{json.dumps(payload, ensure_ascii=False)}"
    )


def _page_context_retrieval_text(content: str | None, page_context: dict | None) -> str | None:
    """将页面上下文关键信息拼入检索文本，供资源检索使用。"""
    if not page_context:
        return content

    pieces = [
        content or "",
        page_context.get("title"),
        page_context.get("package_name"),
        page_context.get("city"),
        page_context.get("location"),
        page_context.get("price_label"),
        page_context.get("budget_label"),
        page_context.get("summary"),
        page_context.get("description"),
    ]
    if page_context.get("resource_type") == "photographer":
        pieces.extend([
            page_context.get("photographer_name"),
            page_context.get("owner_display_name"),
            page_context.get("search_text"),
        ])
    for key in ("tags", "styles", "packages", "portfolio", "applications"):
        value = page_context.get(key)
        if value:
            pieces.append(value)

    text = " ".join(str(piece) for piece in pieces if piece)
    return text[:4000] if text.strip() else content


def _build_provider_messages(
    db: Session,
    conversation_id: int,
    retrieval_context: str | None = None,
    extra_system_prompts: list[str] | None = None,
    page_context_prompt: str | None = None,
    history_limit: int | None = None,
) -> list[dict]:
    """组装发送给 LLM provider 的历史消息列表，含系统提示、检索上下文与图片附件。"""
    history = (
        db.query(AIMessage)
        .filter(AIMessage.conversation_id == conversation_id)
        .order_by(AIMessage.created_at.desc(), AIMessage.id.desc())
        .limit(max(1, history_limit or settings.AI_MAX_HISTORY_MESSAGES))
        .all()
    )
    history.reverse()
    history = [
        item
        for index, item in enumerate(history)
        if not (
            item.role == "user"
            and index < len(history) - 1
            and history[index + 1].role != "assistant"
        )
    ]
    messages = [{"role": "system", "content": AI_SYSTEM_PROMPT}]
    for prompt in extra_system_prompts or []:
        messages.append({"role": "system", "content": prompt})
    if page_context_prompt:
        messages.append({"role": "system", "content": page_context_prompt})
    if retrieval_context:
        messages.append({"role": "system", "content": retrieval_context})
    for item in history:
        metadata = item.message_metadata or {}
        item_text = item.content
        if item.role == "user":
            marker = _project_context_marker(metadata.get("page_context"))
            if marker:
                item_text = f"{marker}\n{item.content}" if item.content else marker
        attachments = []
        if item.role == "user":
            attachments = metadata.get("attachments") or _page_context_vision_attachments(
                item.content,
                metadata.get("page_context"),
            )
        if attachments:
            content_parts = []
            if item_text:
                content_parts.append({"type": "text", "text": item_text})
            for att in attachments:
                if att.get("type") == "image":
                    content_parts.append({
                        "type": "image_url",
                        "image_url": {"url": _image_url_for_provider(att)},
                    })
            messages.append({"role": item.role, "content": content_parts})
        else:
            messages.append({"role": item.role, "content": item_text})
    return messages


def _empty_retrieval_reply(retrieval: dict | None) -> str:
    """无结果时的安全兜底话术。

    只用结构化条件描述，不再复述 criteria.terms：那里面是原文切出来的 n-gram，
    会把“个我不太”这类碎片说成“完全匹配关键词”。
    """
    criteria = (retrieval or {}).get("criteria")
    focus = describe_criteria(criteria, include_resource_types=False)
    target = describe_resource_types(criteria) or "上架资源"
    if focus:
        return (
            f"暂时没找到同时满足{focus}的{target}。"
            "你可以放宽其中一项条件，或者补充城市、预算和风格，我再帮你找。"
        )
    return f"暂时没找到匹配的{target}。你可以告诉我城市、预算或想要的风格，我再帮你缩小范围。"


def _should_use_empty_retrieval_fallback(content: str | None, retrieval: dict | None) -> bool:
    """判断检索无结果且用户为资源搜索时是否走空结果兜底。"""
    return bool(retrieval) and is_resource_search(content) and not has_reference_matches(retrieval)


def _has_prior_dialogue(db: Session, conversation_id: int) -> bool:
    """会话里是否已经有过助手回复，即最终 LLM 能读到真实的上下文。"""
    return (
        db.query(AIMessage.id)
        .filter(
            AIMessage.conversation_id == conversation_id,
            AIMessage.role == "assistant",
        )
        .first()
        is not None
    )


async def _empty_retrieval_result(
    db: Session,
    *,
    conversation_id: int,
    retrieval: dict | None,
    refinement: dict | None,
    page_context_prompt: str | None,
) -> dict:
    """无结果场景：有完整历史时交给最终 LLM 解释，固定话术只作安全回退。

    固定兜底会把上一轮条件和用户反馈都丢掉（“暂时没找到完全匹配‘不太满意’的资源”
    就是这么来的），所以只在没有历史、模型异常或输出为空时使用。
    """
    fallback = {
        "content": refinement_empty_reply(refinement) if refinement else _empty_retrieval_reply(retrieval),
        "metadata": {
            "model": {
                "provider": "platform_guardrail",
                "model": (
                    "search-refinement-empty-fallback" if refinement else "empty-retrieval-fallback"
                ),
            }
        },
    }
    if not _has_prior_dialogue(db, conversation_id):
        return fallback

    provider_messages = _build_provider_messages(
        db,
        conversation_id,
        build_retrieval_context(retrieval),
        extra_system_prompts=[build_empty_retrieval_prompt(retrieval, refinement=refinement)],
        page_context_prompt=page_context_prompt,
    )
    try:
        result = await get_ai_provider().chat(provider_messages)
    except Exception:
        return fallback
    if not (result.get("content") or "").strip():
        return fallback
    # 模型不可用时 provider 会返回降级话术；这一轮后端自己就能把"没找到"说清楚，
    # 用平台兜底比让用户看到"AI 服务暂时不可用"更有信息量。
    if (result.get("metadata") or {}).get("degraded"):
        return fallback
    return result


def _is_recommendation_count_correction(content: str | None) -> bool:
    """判断用户消息是否为纠正推荐数量的表达。"""
    text = (content or "").strip()
    if not text:
        return False
    asks_for_one = any(
        phrase in text
        for phrase in (
            "只要一位",
            "只要一个",
            "只要一名",
            "我只要一",
            "只推荐一位",
            "只推荐一个",
            "只推荐一名",
        )
    )
    mentions_too_many = any(phrase in text for phrase in ("推荐了两位", "推荐了两个", "推荐两位", "推荐两个", "两位", "两个"))
    return asks_for_one and mentions_too_many


def _recommendation_count_correction_result() -> dict:
    """生成推荐数量纠正的固定回复结果。"""
    return {
        "content": "抱歉，刚才应该只推荐一位。之后你说“一位 / 一个 / 一名”时，我会只给 1 个结果，不再额外补第二位。",
        "metadata": {
            "model": {
                "provider": "platform_orchestrator",
                "model": "recommendation-count-correction",
            }
        },
    }


def _is_confirmation(content: str | None) -> bool:
    """判断用户消息是否为确认操作。"""
    text = (content or "").strip()
    if not text:
        return False
    return text in {
        "确认",
        "可以",
        "好的",
        "好",
        "行",
        "就这个",
        "就这位",
        "确认关注",
        "帮我关注",
        "关注吧",
        "执行",
        "确认发布",
        "确认发布企划",
        "确认发布方案",
        "确认发布套餐",
        "发布吧",
        "上架吧",
        "确认上架",
        "确认预约",
        "预约吧",
    } or any(
        phrase in text
        for phrase in (
            "确认关注",
            "可以关注",
            "就关注",
            "帮我关注吧",
            "确认发布",
            "可以发布",
            "就发布",
            "确认上架",
            "可以上架",
            "就上架",
            "确认预约",
            "可以预约",
            "就预约",
        )
    )


def _is_reference_image_skip(content: str | None) -> bool:
    """判断用户消息是否要求跳过参考图。"""
    text = (content or "").strip()
    if not text:
        return False
    return any(
        phrase in text
        for phrase in (
            "跳过参考图",
            "不用参考图",
            "不需要参考图",
            "暂不上传",
            "暂时不传",
            "先不传",
            "不上传",
            "没有参考图",
            "没有图",
            "不用了",
        )
    )


def _is_task_cancel_request(content: str | None) -> bool:
    """判断用户消息是否为取消当前任务。"""
    text = (content or "").strip()
    if not text:
        return False
    exact_terms = {
        "取消",
        "取消任务",
        "放弃",
        "退出",
        "算了",
        "不发了",
        "不发布了",
        "先不发了",
        "先取消",
        "取消发布",
        "放弃发布",
        "取消企划",
        "放弃企划",
        "停止",
        "不弄了",
    }
    if text in exact_terms:
        return True
    return any(
        phrase in text
        for phrase in (
            "取消这次",
            "放弃这次",
            "退出发布",
            "取消发布流程",
            "放弃发布流程",
            "不要发布",
            "别发布",
            "先不发布",
            "回到日常",
            "回到普通聊天",
        )
    )


PROJECT_SLOT_LABELS = {
    "title": "企划标题",
    "city": "拍摄城市",
    "budget_max": "预算",
    "style": "拍摄风格",
    "date": "拍摄日期",
    "people_count": "拍摄人数",
    "description": "需求描述",
}

PROJECT_DESCRIPTION_LABELS = ("需求描述", "拍摄需求", "具体需求", "需求说明", "需求")
PROJECT_NON_DESCRIPTION_LABELS = (
    "企划标题",
    "拍摄标题",
    "标题",
    "企划名称",
    "交付要求",
    "交付内容",
    "成片要求",
    "出片要求",
    "交付物",
    "拍摄人数",
    "人数",
    "拍摄风格",
    "风格",
    "预算",
    "地点",
    "城市",
    "时间",
    "日期",
)


PACKAGE_SLOT_LABELS = {
    "package_name": "方案名称或风格",
    "price": "方案价格",
    "duration_minutes": "拍摄时长",
    "image_count": "精修张数",
    "package_description": "方案简介",
}

PACKAGE_DESCRIPTION_LABELS = ("方案简介", "套餐简介", "服务简介", "简介", "方案描述", "套餐描述", "服务描述", "描述", "介绍")
PACKAGE_NON_DESCRIPTION_LABELS = (
    "方案名称",
    "套餐名称",
    "服务名称",
    "名称",
    "名字",
    "标题",
    "价格",
    "方案价格",
    "套餐价格",
    "费用",
    "报价",
    "拍摄时长",
    "时长",
    "精修张数",
    "精修",
    "风格",
    "城市",
    "所在城市",
    "包含",
)


def _project_missing_slots(slots: dict) -> list[str]:
    """返回企划缺失的必填槽位列表。"""
    required = ("city", "budget_max", "style", "date", "people_count", "description")
    return [name for name in required if not slots.get(name)]


PROJECT_SUBMISSION_SLOT_KEYS = {
    "title",
    "city",
    "location_text",
    "location_name",
    "location_address",
    "location_latitude",
    "location_longitude",
    "location_place_id",
    "location_provider",
    "coordinate_system",
    "location_precision",
    "style",
    "budget_max",
    "date",
    "time",
    "people_count",
    "description",
    "deliverables",
    "duration_minutes",
    "reference_images",
}


def _project_intent_from_task_submission(task_submission: dict | None) -> AgentIntent | None:
    """从企划表单提交数据构造企划发布意图。"""
    if not isinstance(task_submission, dict):
        return None
    action = task_submission.get("action")
    if task_submission.get("task_type") != "create_project" or action not in {"publish", "save_draft"}:
        return None

    raw_slots = task_submission.get("slots") or {}
    if not isinstance(raw_slots, dict):
        return None
    slots = {
        key: value
        for key, value in raw_slots.items()
        if key in PROJECT_SUBMISSION_SLOT_KEYS and value not in (None, "", [])
    }
    if task_submission.get("skip_reference_images"):
        slots["reference_images_skipped"] = True
    slots["_submission_action"] = action

    return AgentIntent(
        intent="project_flow",
        sub_intents=["create_project"],
        slots=slots,
        missing_slots=_project_missing_slots(slots),
        requires_confirmation=True,
        route="project",
        confidence=1.0,
    )


def _has_explicit_non_description_project_label(content: str | None) -> bool:
    """判断文本中是否含有非描述类企划字段的显式标签。"""
    text = (content or "").strip()
    if not text:
        return False
    description_pattern = "|".join(re.escape(label) for label in PROJECT_DESCRIPTION_LABELS)
    if re.search(rf"(?:{description_pattern})\s*(?:改成|改为|修改为|调整为|换成|设为|设置为|是|为|在|：|:)", text):
        return False
    label_pattern = "|".join(re.escape(label) for label in PROJECT_NON_DESCRIPTION_LABELS)
    return bool(re.search(rf"(?:{label_pattern})\s*(?:改成|改为|修改为|调整为|换成|设为|设置为|是|为|在|：|:)", text))


def _package_missing_slots(slots: dict) -> list[str]:
    """返回套餐缺失的必填槽位列表。"""
    missing = []
    if not slots.get("package_name") and not slots.get("style"):
        missing.append("package_name")
    if not (slots.get("price") or slots.get("budget_max")):
        missing.append("price")
    if not slots.get("duration_minutes"):
        missing.append("duration_minutes")
    if not slots.get("image_count"):
        missing.append("image_count")
    if not slots.get("package_description"):
        missing.append("package_description")
    return missing


PACKAGE_SUBMISSION_SLOT_KEYS = {
    "package_name",
    "city",
    "style",
    "price",
    "budget_max",
    "duration_minutes",
    "image_count",
    "package_includes",
    "package_description",
    "sample_images",
    "requires_makeup",
}


def _package_intent_from_task_submission(task_submission: dict | None) -> AgentIntent | None:
    """从套餐表单提交数据构造套餐发布意图。"""
    if not isinstance(task_submission, dict):
        return None
    if task_submission.get("task_type") != "publish_package" or task_submission.get("action") != "publish":
        return None

    raw_slots = task_submission.get("slots") or {}
    if not isinstance(raw_slots, dict):
        return None
    slots = {
        key: value
        for key, value in raw_slots.items()
        if key in PACKAGE_SUBMISSION_SLOT_KEYS and value not in (None, "", [])
    }
    if task_submission.get("skip_reference_images"):
        slots["sample_images_skipped"] = True
    slots["_submission_action"] = "publish"

    return AgentIntent(
        intent="package_publish_flow",
        sub_intents=["publish_package"],
        slots=slots,
        missing_slots=_package_missing_slots(slots),
        requires_confirmation=True,
        route="package",
        confidence=1.0,
    )


def _has_explicit_non_description_package_label(content: str | None) -> bool:
    """判断文本中是否含有非描述类套餐字段的显式标签。"""
    text = (content or "").strip()
    if not text:
        return False
    description_pattern = "|".join(re.escape(label) for label in PACKAGE_DESCRIPTION_LABELS)
    if re.search(rf"(?:{description_pattern})\s*(?:改成|改为|修改为|调整为|换成|设为|设置为|是|为|在|：|:|，|,)", text):
        return False
    label_pattern = "|".join(re.escape(label) for label in PACKAGE_NON_DESCRIPTION_LABELS)
    return bool(re.search(rf"(?:{label_pattern})\s*(?:改成|改为|修改为|调整为|换成|设为|设置为|是|为|在|：|:|，|,)?", text))


def _latest_task_state(db: Session, conversation_id: int, task_type: str) -> dict | None:
    """从最近的助手消息中获取指定类型的任务状态。"""
    message = (
        db.query(AIMessage)
        .filter(AIMessage.conversation_id == conversation_id, AIMessage.role == "assistant")
        .order_by(AIMessage.created_at.desc(), AIMessage.id.desc())
        .first()
    )
    if not message:
        return None

    task_state = (message.message_metadata or {}).get("task_state") or {}
    if task_state.get("task_type") != task_type:
        return None
    return task_state


CANCELLABLE_TASK_LABELS = {
    "create_project": "企划发布",
    "publish_package": "方案发布",
    "create_booking": "预约",
}
CANCELLABLE_TASK_STATUSES = {
    "awaiting_details",
    "awaiting_reference_images",
    "awaiting_confirmation",
    "awaiting_package",
    "awaiting_date",
    "awaiting_time",
}


def _latest_cancellable_task_state(db: Session, conversation_id: int) -> dict | None:
    """获取最近可取消的任务状态，不可取消时返回 None。"""
    message = (
        db.query(AIMessage)
        .filter(AIMessage.conversation_id == conversation_id, AIMessage.role == "assistant")
        .order_by(AIMessage.created_at.desc(), AIMessage.id.desc())
        .first()
    )
    if not message:
        return None

    task_state = (message.message_metadata or {}).get("task_state") or {}
    if task_state.get("task_type") not in CANCELLABLE_TASK_LABELS:
        return None
    if task_state.get("status") not in CANCELLABLE_TASK_STATUSES:
        return None
    return task_state


def _task_cancel_result(task_state: dict) -> dict:
    """生成取消任务后的回复结果。"""
    task_type = task_state.get("task_type")
    task_label = CANCELLABLE_TASK_LABELS.get(task_type, "当前流程")
    return {
        "content": f"好的，已取消这次{task_label}。现在已回到普通聊天状态。",
        "metadata": {
            "model": {
                "provider": "platform_orchestrator",
                "model": "task-cancelled",
            },
            "suggested_actions": [],
            "task_state": {
                **task_state,
                "status": "cancelled",
                "missing_slots": [],
                "pending_action": None,
            },
        },
    }


PROJECT_UPDATE_LABELS = {
    "title": ("企划标题", "拍摄标题", "标题", "企划名称"),
    "city": ("拍摄城市", "城市"),
    "location_text": ("拍摄地点", "地点", "位置"),
    "budget_max": ("预算", "费用"),
    "style": ("拍摄风格", "风格"),
    "date": ("拍摄日期", "日期"),
    "time": ("拍摄时间", "时间"),
    "people_count": ("拍摄人数", "人数"),
    "description": PROJECT_DESCRIPTION_LABELS,
    "deliverables": ("交付要求", "交付内容", "成片要求", "出片要求", "交付物"),
}

PROJECT_DETAIL_SLOT_KEYS = set(PROJECT_UPDATE_LABELS)


def _is_slot_update_request(content: str | None) -> bool:
    """判断用户消息是否为槽位更新请求。"""
    text = (content or "").strip()
    if not text:
        return False
    return any(
        phrase in text
        for phrase in (
            "改成",
            "改为",
            "修改为",
            "调整为",
            "换成",
            "设为",
            "设置为",
            "改一下",
            "修改一下",
        )
    )


def _project_replace_keys_from_content(content: str | None, incoming_slots: dict) -> set[str]:
    """根据消息内容确定需要整体替换的企划槽位键。"""
    if not _is_slot_update_request(content):
        return set()

    text = (content or "").strip()
    explicit_keys: set[str] = set()
    for key, labels in PROJECT_UPDATE_LABELS.items():
        label_pattern = "|".join(re.escape(label) for label in labels)
        if re.search(rf"(?:{label_pattern})\s*(?:改成|改为|修改为|调整为|换成|设为|设置为)", text):
            explicit_keys.add(key)

    available_keys = {
        key
        for key, value in (incoming_slots or {}).items()
        if key in PROJECT_DETAIL_SLOT_KEYS and value not in (None, "", [])
    }
    if explicit_keys:
        return explicit_keys & available_keys
    return available_keys


def _merge_slots(base: dict | None, incoming: dict | None, *, replace_keys: set[str] | None = None) -> dict:
    """合并新旧槽位，按 replace_keys 决定覆盖策略并处理风格合并。"""
    slots = dict(base or {})
    replace_keys = replace_keys or set()
    for key, value in (incoming or {}).items():
        if value not in (None, "", []):
            if key in replace_keys:
                slots[key] = value
                continue
            if key == "style" and slots.get("style"):
                slots[key] = _merge_style_values(slots.get("style"), value)
                continue
            if key == "package_includes" and slots.get("package_includes"):
                slots[key] = _merge_style_values(slots.get("package_includes"), value)
                continue
            if key == "budget_max" and slots.get("budget_max") and float(value) < 100:
                continue
            slots[key] = value
    return slots


def _merge_style_values(current, incoming) -> list[str]:
    """合并风格值列表并去重。"""
    merged = []
    for value in (current, incoming):
        if isinstance(value, list):
            merged.extend(value)
        elif value:
            merged.append(value)

    result = []
    seen = set()
    for item in merged:
        normalized = str(item).strip()
        if normalized and normalized not in seen:
            result.append(normalized)
            seen.add(normalized)
    return result


def _project_contextual_intent(
    db: Session,
    conversation_id: int,
    intent: AgentIntent,
    attachments: list[dict] | None = None,
    content: str | None = None,
) -> AgentIntent:
    """结合进行中的企划任务状态，将普通意图续接为企划发布意图。"""
    task_state = _latest_task_state(db, conversation_id, "create_project")
    if not task_state or task_state.get("status") not in {
        "awaiting_details",
        "awaiting_reference_images",
        "awaiting_confirmation",
    }:
        return intent
    if intent.intent not in {"chat", "project_flow"} and not _has_image_attachments(attachments):
        return intent

    incoming_slots = dict(intent.slots)
    if (
        task_state.get("missing_slots") == ["description"]
        and not incoming_slots.get("description")
        and content
        and not _is_confirmation(content)
        and not _is_reference_image_skip(content)
        and not _has_explicit_non_description_project_label(content)
    ):
        incoming_slots["description"] = content.strip()

    replace_keys = _project_replace_keys_from_content(content, incoming_slots)
    slots = _merge_slots(task_state.get("slots"), incoming_slots, replace_keys=replace_keys)
    return AgentIntent(
        intent="project_flow",
        sub_intents=["create_project"],
        slots=slots,
        missing_slots=_project_missing_slots(slots),
        requires_confirmation=True,
        route="project",
        confidence=max(intent.confidence, 0.78),
    )


def _package_contextual_intent(
    db: Session,
    conversation_id: int,
    intent: AgentIntent,
    attachments: list[dict] | None = None,
    content: str | None = None,
) -> AgentIntent:
    """结合进行中的套餐任务状态，将普通意图续接为套餐发布意图。"""
    task_state = _latest_task_state(db, conversation_id, "publish_package")
    if not task_state or task_state.get("status") not in {
        "awaiting_details",
        "awaiting_reference_images",
        "awaiting_confirmation",
    }:
        return intent
    if (
        intent.intent not in {"chat", "package_publish_flow"}
        and not _has_package_detail_slots(intent.slots)
        and not _has_image_attachments(attachments)
    ):
        return intent

    incoming_slots = dict(intent.slots)
    if (
        task_state.get("missing_slots") == ["package_description"]
        and not incoming_slots.get("package_description")
        and content
        and not _is_confirmation(content)
        and not _is_reference_image_skip(content)
        and not _has_explicit_non_description_package_label(content)
    ):
        incoming_slots["package_description"] = content.strip()

    slots = _merge_slots(task_state.get("slots"), incoming_slots)
    return AgentIntent(
        intent="package_publish_flow",
        sub_intents=["publish_package"],
        slots=slots,
        missing_slots=_package_missing_slots(slots),
        requires_confirmation=True,
        route="package",
        confidence=max(intent.confidence, 0.78),
    )


def _has_package_detail_slots(slots: dict) -> bool:
    """判断槽位中是否已含套餐详情字段。"""
    detail_keys = {
        "package_name",
        "budget_max",
        "price",
        "duration_minutes",
        "image_count",
        "package_includes",
        "package_description",
        "sample_images",
        "style",
        "city",
        "requires_makeup",
    }
    return any(slots.get(key) not in (None, "", []) for key in detail_keys)


def _has_image_attachments(attachments: list[dict] | None) -> bool:
    """判断附件中是否含有效图片。"""
    return any(
        item.get("type") == "image" and item.get("url")
        for item in attachments or []
    )


def _booking_contextual_intent(
    db: Session,
    conversation_id: int,
    intent: AgentIntent,
    content: str | None = None,
    user_id: int | None = None,
) -> AgentIntent:
    """检查是否需要接管为 booking flow（基于历史 task_state）"""
    incoming_slots = _extract_booking_slots(content)
    task_state = _latest_booking_task_state(db, conversation_id, user_id)
    if not task_state:
        if intent.intent != "booking_flow" or not incoming_slots:
            return intent
        slots = _merge_slots(intent.slots, incoming_slots)
        return AgentIntent(
            intent="booking_flow",
            sub_intents=list(intent.sub_intents or ["search_package", "create_booking"]),
            slots=slots,
            missing_slots=[slot for slot in ("date", "time") if not slots.get(slot)],
            requires_confirmation=True,
            route="booking",
            confidence=max(intent.confidence, 0.9),
        )
    if task_state.get("status") not in {
        "awaiting_date", "awaiting_time", "awaiting_confirmation",
    }:
        return intent
    slots = _merge_slots(task_state.get("slots"), intent.slots)
    slots = _merge_slots(slots, incoming_slots)
    return AgentIntent(
        intent="booking_flow",
        sub_intents=["search_package", "create_booking"],
        slots=slots,
        missing_slots=[],
        requires_confirmation=True,
        route="booking",
        confidence=max(intent.confidence, 0.85),
    )


def _refined_search_intent(
    intent: AgentIntent,
    refinement: dict | None,
    content: str | None,
    attachments: list[dict] | None,
) -> AgentIntent:
    """把“换一个/再推荐一个”这类追问重新落成一次带继承条件的 resource_search。

    见 docs/agentfix260731.txt：单看本轮消息，“换一个”在规则分类器里是 chat，
    “再推荐一个”又会被兜底成 photographers，两种情况都丢掉了上一轮真正的搜索条件。
    """
    if not refinement:
        return intent
    # 发布企划/发布套餐/预约流程正在进行时不接管，避免打断多轮表单。
    if intent.intent not in {"chat", "resource_search"}:
        return intent

    slots = apply_refinement_to_slots(intent.slots, refinement, content)
    policy = apply_intent_policy(
        "resource_search",
        slots,
        has_image=_has_image_attachments(attachments),
    )
    return AgentIntent(
        intent="resource_search",
        sub_intents=policy["sub_intents"],
        slots=slots,
        missing_slots=policy["missing_slots"],
        requires_confirmation=policy["requires_confirmation"],
        route=policy["route"],
        confidence=max(intent.confidence, 0.8),
    )


# ── 统一决策层接入（阶段B §4.2、§8；阶段C 起由 agent_routing_gate 决定生效模式）──────
# legacy：完全不调用决策器；shadow：调用并记录差异但不改变行为；
# tool_loop：决策器接管“聊天 + 读检索”，写操作仍回退到既有确认流程。
DECISION_ROUTING_MODES = ROUTING_MODES

# 重复推荐诊断的版本号：看板与离线评估都按这个键读取。
RECOMMENDATION_OVERLAP_SCHEMA_VERSION = "recommendation_overlap_v1"

# 给决策器的历史只保留短文本：它只需要判断指代和延续，不需要完整原文。
DECISION_HISTORY_TEXT_LIMIT = 160

# 页面上下文里可以交给模型的字段。刻意排除 resource_id / owner_user_id 等平台 ID，
# 模型不需要它们，也不应该学会自己拼 ID（§5.1、§5.5）。
_DECISION_PAGE_CONTEXT_KEYS = (
    "resource_type",
    "title",
    "package_name",
    "photographer_name",
    "city",
    "location",
    "styles",
    "tags",
    "price_label",
    "budget_label",
    "date_label",
    "status",
)


def _decision_routing_mode(
    user_id: int | None = None,
    conversation_id: int | None = None,
) -> str:
    """本轮生效的 routing mode（阶段C 起由灰度门决定，不再是一个全局字符串）。"""
    return resolve_routing_rollout(user_id=user_id, conversation_id=conversation_id).mode


def _decision_page_context(page_context: dict | None) -> dict:
    """过滤页面上下文，只保留可交给决策器的字段。"""
    if not page_context:
        return {}
    return {
        key: page_context[key]
        for key in _DECISION_PAGE_CONTEXT_KEYS
        if page_context.get(key) not in (None, "", [], {})
    }


def _decision_history(
    db: Session,
    conversation_id: int,
    *,
    exclude_message_id: int | None = None,
    limit: int | None = None,
) -> list[dict]:
    """给决策器的有限历史：只有角色和截断后的文本，不含附件、元数据和图片内容。"""
    size = max(1, limit or settings.AI_AGENT_DECISION_MAX_HISTORY)
    rows = (
        db.query(AIMessage)
        .filter(AIMessage.conversation_id == conversation_id)
        .order_by(AIMessage.created_at.desc(), AIMessage.id.desc())
        .limit(size + 1)
        .all()
    )
    history: list[dict] = []
    for row in rows:
        if exclude_message_id is not None and row.id == exclude_message_id:
            continue
        history.append({
            "role": row.role,
            "content": (row.content or "")[:DECISION_HISTORY_TEXT_LIMIT],
        })
        if len(history) >= size:
            break
    history.reverse()
    return history


def _agent_user_role(db: Session, user_id: int) -> str | None:
    """查询用户的角色。"""
    from backend.app.models.user import User

    return (
        db.query(User.role).filter(User.id == user_id).scalar()
        if user_id
        else None
    )


def _agent_user(db: Session, user_id: int):
    """查询用户对象。"""
    from backend.app.models.user import User

    return db.query(User).filter(User.id == user_id).first()


def _decision_search_intent(
    intent: AgentIntent,
    *,
    tool_name: str,
    arguments: dict,
    attachments: list[dict] | None,
    confidence: float,
) -> AgentIntent:
    """把一次 search_* 工具调用落成 resource_search 意图。

    决策协议不承载日期/时间，这两个槽位仍沿用既有分类结果，
    避免"帮我看看8月15日重庆的婚礼套餐"在切到工具路径后丢掉日期。
    """
    resource_key = resource_key_for_tool(tool_name)
    slots: dict = {
        key: value
        for key, value in (intent.slots or {}).items()
        if key in ("date", "time") and value
    }
    slots["resource_types"] = [resource_key] if resource_key else []
    if arguments.get("city"):
        slots["city"] = arguments["city"]
    if arguments.get("styles"):
        slots["styles"] = list(arguments["styles"])
    if arguments.get("budget_min") is not None:
        slots["budget_min"] = arguments["budget_min"]
    if arguments.get("budget_max") is not None:
        slots["budget_max"] = arguments["budget_max"]
    if arguments.get("requires_makeup"):
        slots["requires_makeup"] = True
    if arguments.get("photographer_name"):
        slots["photographer_name"] = arguments["photographer_name"]
    slots["limit"] = arguments.get("limit") or (intent.slots or {}).get("limit") or 3

    policy = apply_intent_policy(
        "resource_search",
        slots,
        has_image=_has_image_attachments(attachments),
    )
    return AgentIntent(
        intent="resource_search",
        sub_intents=policy["sub_intents"],
        slots=slots,
        missing_slots=policy["missing_slots"],
        requires_confirmation=policy["requires_confirmation"],
        route=policy["route"],
        confidence=max(intent.confidence, float(confidence or 0.0)),
    )


def _decision_chat_intent(
    intent: AgentIntent,
    *,
    attachments: list[dict] | None,
    confidence: float,
) -> AgentIntent:
    """决策为 chat：本轮不检索，交给最终 LLM 用摄影知识回答。"""
    policy = apply_intent_policy(
        "chat",
        {},
        has_image=_has_image_attachments(attachments),
    )
    return AgentIntent(
        intent="chat",
        sub_intents=policy["sub_intents"],
        slots={},
        missing_slots=policy["missing_slots"],
        requires_confirmation=policy["requires_confirmation"],
        route=policy["route"],
        confidence=max(intent.confidence, float(confidence or 0.0)),
    )


def _decision_clarify_result(question: str | None) -> dict:
    """决策为 clarify：一轮只问一个问题（§5.3），话术由决策器给出。"""
    text = (question or "").strip() or "方便先告诉我你想在哪个城市拍吗？"
    return {
        "content": text,
        "metadata": {
            "model": {
                "provider": "platform_orchestrator",
                "model": "agent-decision-clarify",
            }
        },
    }


def _shoot_context_error_result(context: dict | None, arguments: dict | None) -> dict | None:
    """Render tool failures deterministically so the final model cannot invent a cause."""
    payload = context or {}
    status = payload.get("status")
    error_code = payload.get("error_code")
    if status == "success":
        return None
    location = str((arguments or {}).get("location_text") or "该地点")
    if error_code == "location_not_found":
        content = f"暂时未能识别地点“{location}”。请换成更明确的城市、区县或具体景点名称后重试。"
    elif error_code == "ambiguous_location":
        labels: list[str] = []
        for item in payload.get("place_candidates") or []:
            label = str(item.get("address") or item.get("name") or "").strip()
            if label and label not in labels:
                labels.append(label)
        suffix = f" 可选择：{'、'.join(labels)}。" if labels else ""
        content = f"“{location}”对应多个地点，请确认具体地点后再查询天气。{suffix}"
    elif error_code == "forecast_unavailable":
        shoot_date = str((arguments or {}).get("shoot_date") or "该日期")
        content = f"地点已经识别，但 {shoot_date} 超出当前天气服务可提供的预报范围。"
    elif error_code == "weather_unavailable":
        content = f"地点“{location}”已经识别，但天气服务暂时不可用，请稍后重试。"
    else:
        content = f"暂时无法获取“{location}”的拍摄环境，地点或天气服务当前不可用，请稍后重试。"
    return {
        "content": content,
        "metadata": {"model": {"provider": "platform_orchestrator", "model": "shoot-context-error"}},
    }


def _shoot_context_selection_arguments(
    db: Session,
    conversation_id: int,
    selection: dict | None,
) -> dict | None:
    """Restore a selected candidate from trusted assistant metadata."""
    if not selection:
        return None
    source_message = (
        db.query(AIMessage)
        .filter(
            AIMessage.id == selection.get("source_message_id"),
            AIMessage.conversation_id == conversation_id,
            AIMessage.role == "assistant",
        )
        .first()
    )


def _build_long_term_memory_prompt(memories: list[dict] | None) -> str | None:
    """Build a low-priority prompt from activated user memories only."""
    if not memories:
        return None
    compact = []
    for memory in memories[:20]:
        if not isinstance(memory, dict):
            continue
        value = memory.get("value")
        if value in (None, "", [], {}):
            continue
        compact.append({
            "type": memory.get("memory_type"),
            "key": memory.get("key"),
            "value": value,
            "confidence": memory.get("confidence"),
        })
    if not compact:
        return None
    return (
        "以下是系统从用户过往已完成任务中提炼的长期偏好，仅作为弱参考。"
        "不得把它当作本轮用户要求、任务状态、资源详情或工具结果；"
        "如果与当前用户消息、当前任务表单、当前页面上下文、检索结果或工具返回冲突，"
        "必须以后者为准。不得仅凭这些偏好声称用户已经确认了某个条件。\n"
        + json.dumps(compact, ensure_ascii=False)
    )
    metadata = (source_message.message_metadata or {}) if source_message else {}
    context = metadata.get("shoot_context") or {}
    if context.get("status") != "ambiguous":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="地点候选已失效，请重新查询天气")

    latitude = float(selection.get("latitude"))
    longitude = float(selection.get("longitude"))
    candidate = next(
        (
            item
            for item in context.get("place_candidates") or []
            if abs(float(item.get("latitude")) - latitude) < 0.000001
            and abs(float(item.get("longitude")) - longitude) < 0.000001
        ),
        None,
    )
    plan_arguments = ((metadata.get("agent_decision") or {}).get("plan") or {}).get("arguments") or {}
    if not candidate or not plan_arguments.get("shoot_date"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="地点候选已失效，请重新查询天气")

    arguments = {
        "location_text": str(candidate.get("name") or candidate.get("address") or "已选地点"),
        "location_address": str(candidate.get("address") or candidate.get("name") or "已选地点"),
        "latitude": float(candidate["latitude"]),
        "longitude": float(candidate["longitude"]),
        "shoot_date": plan_arguments["shoot_date"],
        "duration_minutes": plan_arguments.get("duration_minutes", 120),
    }
    if plan_arguments.get("start_time"):
        arguments["start_time"] = plan_arguments["start_time"]
    return arguments


def _is_explicit_task_confirmation(content: str | None, task_type: str) -> bool:
    """Require an action-specific phrase before legacy chat may execute a write."""
    text = (content or "").strip().rstrip("。.!！")
    phrases = {
        "create_project": {"确认发布企划", "确认发布项目", "确认发布"},
        "publish_package": {"确认发布方案", "确认发布套餐", "确认上架"},
        "create_booking": {"确认预约", "提交预约申请"},
        "project_application": {"确认提交应邀", "提交应邀"},
    }.get(task_type, set())
    return text in phrases


def _pending_action_is_confirmed(content: str | None, pending: dict | None) -> bool:
    tool = ((pending or {}).get("pending_action") or {}).get("tool")
    task_type_by_tool = {
        "create_project": "create_project",
        "publish_package": "publish_package",
        "create_booking": "create_booking",
    }
    task_type = task_type_by_tool.get(tool)
    if task_type:
        return _is_explicit_task_confirmation(content, task_type)
    return _is_confirmation(content)


def _active_task_progress_result(task) -> dict:
    """Render the next Agent task step without letting a model imply a write succeeded."""
    serialized = serialize_task(task) or {}
    summary = serialized.get("summary") or {}
    next_question = summary.get("next_question")
    if next_question:
        content = f"已记下你刚才提供的信息。接下来请确认一项：{next_question}"
    elif summary.get("requires_editor"):
        content = "文字信息已经整理好。请进入编辑页选择作品素材并完成发布。"
    else:
        content = "必要信息已经整理好。请先检查任务卡，再明确点击提交；你也可以进入编辑页继续修改。"
    return {
        "content": content,
        "metadata": {
            "model": {"provider": "platform_task", "model": "agent-task-progress"},
            "active_task": serialized,
        },
    }


def _tool_call_item_count(tool_call: dict | None) -> int:
    """读取工具调用结果中的资源数量。"""
    return int(((tool_call or {}).get("result") or {}).get("count") or 0)


def _tool_call_trace(tool_call: dict | None) -> dict | None:
    """工具调用的可观测切片：只留工具名、状态、条件与数量，不重复整份 items。"""
    if not tool_call:
        return None
    result = tool_call.get("result") or {}
    diagnostics = result.get("diagnostics") or {}
    return {
        "schema_version": result.get("schema_version"),
        "tool": tool_call.get("tool"),
        "status": tool_call.get("status"),
        "resource_type": result.get("resource_type"),
        "input": tool_call.get("input") or {},
        "count": result.get("count") or 0,
        "resource_ids": result.get("resource_ids") or [],
        "error": result.get("error"),
        "latency_ms": diagnostics.get("latency_ms"),
        "result_counts": diagnostics.get("result_counts") or {},
        "excluded_resource_ids": diagnostics.get("excluded_resource_ids") or [],
        "explicit_fields": diagnostics.get("explicit_fields") or [],
        "inherited_fields": diagnostics.get("inherited_fields") or [],
    }


def _recommendation_overlap(
    *,
    previous: dict | None,
    current: dict | None,
    refinement: bool,
) -> dict:
    """本轮推荐与上一轮已推荐资源的重叠情况（阶段C §4-C.3 重复推荐率）。

    上一轮已经看过的资源又出现在本轮，说明排除逻辑或检索条件没生效；
    “换一个”场景下的重复尤其严重，所以单独标出 refinement。
    """
    previous_seen = {
        str(item)
        for item in (previous or {}).get("seen_resource_ids")
        or (previous or {}).get("recommended_resource_ids")
        or []
    }
    recommended = [str(item) for item in (current or {}).get("recommended_resource_ids") or []]
    repeated = [item for item in recommended if item in previous_seen]
    return {
        "schema_version": RECOMMENDATION_OVERLAP_SCHEMA_VERSION,
        "refinement": bool(refinement),
        "previous_seen_count": len(previous_seen),
        "recommended_count": len(recommended),
        "repeat_count": len(repeated),
        "repeat_ratio": round(len(repeated) / len(recommended), 4) if recommended else 0.0,
        "repeated_resource_ids": repeated,
    }


def _latest_booking_task_state(
    db: Session,
    conversation_id: int,
    user_id: int | None = None,
) -> dict | None:
    """从最近的 assistant 消息中获取 booking task_state"""
    if user_id is not None:
        task = get_active_task(db, user_id, conversation_id)
        if task and task.task_type == "create_booking":
            fields = task.fields or {}
            slots = {**(task.target or {}), **fields}
            if fields.get("appointment_date"):
                slots["date"] = fields["appointment_date"]
            appointment_time = fields.get("appointment_time")
            if appointment_time:
                try:
                    parsed = datetime.fromisoformat(str(appointment_time))
                    slots.setdefault("date", parsed.strftime("%m-%d"))
                    slots["time"] = parsed.strftime("%H:%M")
                except ValueError:
                    pass
            return {
                "task_type": "create_booking",
                "status": "awaiting_confirmation" if slots.get("date") else "awaiting_date",
                "slots": slots,
                "pending_action": None,
            }

    message = (
        db.query(AIMessage)
        .filter(
            AIMessage.conversation_id == conversation_id,
            AIMessage.role == "assistant",
        )
        .order_by(AIMessage.created_at.desc(), AIMessage.id.desc())
        .first()
    )
    if not message:
        return None
    task_state = (message.message_metadata or {}).get("task_state") or {}
    if task_state.get("task_type") != "create_booking":
        return None
    return task_state


def _attachment_image_urls(attachments: list[dict] | None) -> list[str]:
    """提取附件中的图片 URL 列表。"""
    return [
        item.get("url")
        for item in attachments or []
        if item.get("type") == "image" and item.get("url")
    ]


def _should_run_vision_analysis(intent: AgentIntent, attachments: list[dict] | None) -> bool:
    """判断本轮是否需要执行视觉分析。"""
    return (
        _has_image_attachments(attachments)
        and "vision_analysis" in intent.sub_intents
        and intent.intent in {"image_analysis", "resource_search", "booking_flow"}
    )


def _should_reuse_latest_vision_analysis(
    intent: AgentIntent,
    content: str | None,
    attachments: list[dict] | None,
) -> bool:
    """判断是否可以复用上一轮的视觉分析结果。"""
    if _has_image_attachments(attachments) or not should_run_retrieval(intent):
        return False
    text = (content or "").strip()
    return any(
        phrase in text
        for phrase in (
            "类似",
            "相似",
            "同款",
            "这张图",
            "这张图片",
            "这张照片",
            "刚才那张",
            "刚才这张",
            "参考图",
            "这个风格",
            "这种风格",
        )
    )


def _latest_vision_analysis(db: Session, conversation_id: int) -> dict | None:
    """从最近的助手消息中获取上一轮的视觉分析结果。"""
    messages = (
        db.query(AIMessage)
        .filter(AIMessage.conversation_id == conversation_id, AIMessage.role == "assistant")
        .order_by(AIMessage.created_at.desc(), AIMessage.id.desc())
        .limit(settings.AI_MAX_HISTORY_MESSAGES)
        .all()
    )
    for message in messages:
        vision_analysis = (message.message_metadata or {}).get("vision_analysis")
        if isinstance(vision_analysis, dict) and vision_analysis.get("schema_version"):
            return vision_analysis
    return None


def _apply_vision_slots(intent: AgentIntent, vision_analysis: dict | None) -> AgentIntent:
    """将视觉分析提取的槽位合并进意图。"""
    if not vision_analysis:
        return intent
    vision_slots = vision_slots_from_analysis(vision_analysis)
    if not vision_slots:
        return intent
    intent.slots = _merge_slots(intent.slots, vision_slots)
    return intent


def _vision_metadata(
    provider_result: dict,
    vision_analysis: dict,
    *,
    content: str | None,
    attachments: list[dict] | None,
    search_text: str | None = None,
    resource_types: list[str] | None = None,
    reused_context: bool = False,
) -> dict:
    """组装视觉分析相关的结果元数据与工具调用记录。"""
    metadata = dict(provider_result.get("metadata") or {})
    metadata["vision_analysis"] = vision_analysis
    metadata["vision_context"] = {
        "source": "previous_turn" if reused_context else "current_image",
    }
    metadata["tool_calls"] = [
        {
            "tool": "reuse_vision_analysis" if reused_context else "analyze_image",
            "status": "success",
            "input": {
                "content": content,
                "attachment_count": len(_attachment_image_urls(attachments)),
            },
            "result": {
                "schema_version": vision_analysis.get("schema_version"),
                "style": vision_analysis.get("style") or [],
                "scene": vision_analysis.get("scene") or [],
                "mood": vision_analysis.get("mood") or [],
                "makeup": vision_analysis.get("makeup") or [],
                "search_terms": vision_analysis.get("search_terms") or [],
            },
        }
    ]
    if search_text:
        metadata["vision_search"] = {
            "schema_version": "vision_search_v1",
            "search_text": search_text,
            "resource_types": resource_types or [],
            "filters": {
                "style": vision_analysis.get("style") or [],
                "scene": vision_analysis.get("scene") or [],
                "mood": vision_analysis.get("mood") or [],
                "makeup": vision_analysis.get("makeup") or [],
                "search_terms": vision_search_terms(vision_analysis),
            },
        }
    return metadata


def _vision_agent_result(
    provider_result: dict,
    vision_analysis: dict,
    *,
    content: str | None,
    attachments: list[dict] | None,
) -> dict:
    """生成纯视觉分析场景的助手回复结果。"""
    return {
        "content": build_vision_reply(vision_analysis),
        "metadata": _vision_metadata(
            provider_result,
            vision_analysis,
            content=content,
            attachments=attachments,
        ),
    }


def _vision_retrieval_agent_result(
    provider_result: dict,
    vision_analysis: dict,
    *,
    content: str | None,
    attachments: list[dict] | None,
    search_text: str,
    resource_types: list[str] | None,
    retrieval: dict | None,
    reused_context: bool = False,
) -> dict:
    """生成视觉检索场景的助手回复结果。"""
    return {
        "content": build_vision_retrieval_reply(
            vision_analysis,
            retrieval,
            reused_context=reused_context,
        ),
        "metadata": _vision_metadata(
            provider_result,
            vision_analysis,
            content=content,
            attachments=attachments,
            search_text=search_text,
            resource_types=resource_types,
            reused_context=reused_context,
        ),
    }


def _style_list(value) -> list[str]:
    """将风格值统一转换为字符串列表。"""
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if value:
        return [str(value)]
    return []


def _project_datetime_from_slots(slots: dict) -> datetime | None:
    """根据日期/时间槽位生成企划拍摄时间。"""
    date_value = slots.get("date")
    if not date_value:
        return None
    date_text = str(date_value).strip()
    full_date_match = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", date_text)
    short_date_match = re.fullmatch(r"(\d{1,2})-(\d{1,2})", date_text)
    if not full_date_match and not short_date_match:
        return None

    hour = 10
    minute = 0
    time_value = slots.get("time")
    if time_value:
        time_match = re.match(r"^(\d{1,2}):(\d{2})$", str(time_value))
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2))

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if full_date_match:
        return datetime(int(full_date_match.group(1)), int(full_date_match.group(2)), int(full_date_match.group(3)), hour, minute, 0)
    start = datetime(now.year, int(short_date_match.group(1)), int(short_date_match.group(2)), hour, minute, 0)
    if start < now:
        start = datetime(now.year + 1, int(short_date_match.group(1)), int(short_date_match.group(2)), hour, minute, 0)
    return start


def _project_draft_from_slots(slots: dict, attachments: list[dict] | None = None) -> dict:
    """根据槽位与附件生成企划草稿载荷。"""
    styles = _style_list(slots.get("style"))
    city = slots.get("city")
    location_text = slots.get("location_text")
    budget_max = slots.get("budget_max")
    project_description = str(slots.get("description") or "").strip()
    deliverables = str(slots.get("deliverables") or "").strip() or None
    start = _project_datetime_from_slots(slots)
    duration_minutes = int(slots.get("duration_minutes") or 120)
    reference_images = list(slots.get("reference_images") or [])
    reference_images.extend(_attachment_image_urls(attachments))
    reference_images = list(dict.fromkeys(reference_images))

    explicit_title = str(slots.get("title") or "").strip()
    title_parts = [str(city)] if city else []
    title_parts.extend(styles[:2])
    title_core = "".join(title_parts)
    if explicit_title:
        title = explicit_title
    elif title_core:
        title = f"{title_core}企划" if title_core.endswith("写真") else f"{title_core}写真企划"
    else:
        title = "待补充"

    save_as_draft = slots.get("_submission_action") == "save_draft"
    payload = {
        "title": title,
        "description": project_description or "待补充",
        "category": "portrait",
        "style_tags": styles,
        "city": city or ("待补充" if save_as_draft else ""),
        "location_text": location_text,
        "location_name": slots.get("location_name"),
        "location_address": slots.get("location_address"),
        "location_latitude": slots.get("location_latitude"),
        "location_longitude": slots.get("location_longitude"),
        "location_place_id": slots.get("location_place_id"),
        "location_provider": slots.get("location_provider"),
        "coordinate_system": slots.get("coordinate_system"),
        "location_precision": slots.get("location_precision"),
        "shoot_date_start": start.isoformat() if start else None,
        "shoot_date_end": (start + timedelta(minutes=duration_minutes)).isoformat() if start else None,
        "duration_minutes": duration_minutes,
        "budget_min": None,
        "budget_max": int(budget_max) if budget_max else None,
        "deliverables": deliverables,
        "reference_images": reference_images,
        "visibility": "public",
        "publish": not save_as_draft,
    }
    return {
        "schema_version": "project_draft_v1",
        "slots": slots,
        "missing_slots": _project_missing_slots(slots),
        "project_payload": payload,
    }


def _project_summary_text(draft: dict) -> str:
    """生成企划草稿的中文摘要文本。"""
    payload = draft["project_payload"]
    slots = draft.get("slots") or {}
    reference_count = len(payload.get("reference_images") or [])
    lines = [
        f"标题：{payload['title']}",
        f"城市：{payload['city'] or '待补充'}",
        f"地点：{payload.get('location_text') or '待补充'}",
        f"风格：{'、'.join(payload.get('style_tags') or []) or '待补充'}",
        f"预算：{payload.get('budget_max') or '待补充'}",
        f"时间：{payload.get('shoot_date_start') or '待补充'}",
        f"人数：{slots.get('people_count') or '待补充'}",
        f"需求描述：{payload.get('description') or '待补充'}",
        f"交付要求：{payload.get('deliverables') or '未填写'}",
        f"参考图：{reference_count} 张" if reference_count else "参考图：未添加",
    ]
    return "\n".join(lines)


def _package_price_from_slots(slots: dict):
    """从槽位中取套餐价格。"""
    return slots.get("price") or slots.get("budget_max")


def _package_name_from_slots(slots: dict) -> str:
    """根据槽位生成套餐名称。"""
    explicit_name = (slots.get("package_name") or "").strip()
    if explicit_name:
        if slots.get("_submission_action"):
            return explicit_name
        if explicit_name.endswith(("方案", "套餐")):
            return explicit_name
        return f"{explicit_name}方案"

    styles = _style_list(slots.get("style"))
    city = slots.get("city")
    parts = [str(city)] if city else []
    parts.extend(styles[:2])
    base = "".join(parts) or "摄影"
    if base.endswith(("方案", "套餐")):
        return base
    return f"{base}方案"


def _package_includes_from_slots(slots: dict) -> list[str]:
    """根据槽位生成套餐包含内容列表。"""
    raw_includes = slots.get("package_includes") or []
    if isinstance(raw_includes, str):
        raw_includes = [raw_includes]

    includes = []
    image_count = slots.get("image_count")
    if image_count:
        includes.append(f"精修{int(image_count)}张")
    includes.extend(str(item) for item in raw_includes if str(item).strip())
    if slots.get("requires_makeup"):
        includes.append("妆造")

    result = []
    seen = set()
    for item in includes:
        normalized = str(item).strip()
        if normalized and normalized not in seen:
            result.append(normalized)
            seen.add(normalized)
    return result


def _package_draft_from_slots(slots: dict, attachments: list[dict] | None = None) -> dict:
    """根据槽位与附件生成套餐草稿载荷。"""
    styles = _style_list(slots.get("style"))
    price = _package_price_from_slots(slots)
    duration_minutes = slots.get("duration_minutes")
    image_count = slots.get("image_count")
    package_description = str(slots.get("package_description") or "").strip()
    samples = list(slots.get("sample_images") or [])
    samples.extend(_attachment_image_urls(attachments))
    samples = list(dict.fromkeys(samples))
    includes = _package_includes_from_slots(slots)

    payload = {
        "name": _package_name_from_slots(slots),
        "price": float(price) if price else None,
        "duration": int(duration_minutes) if duration_minutes else None,
        "description": package_description or "待补充",
        "includes": includes,
        "styles": styles,
        "image_count": int(image_count) if image_count else None,
        "city": slots.get("city") or "",
        "samples": samples,
    }
    return {
        "schema_version": "package_draft_v1",
        "slots": slots,
        "missing_slots": _package_missing_slots(slots),
        "package_payload": payload,
    }


def _package_summary_text(draft: dict) -> str:
    """生成套餐草稿的中文摘要文本。"""
    payload = draft["package_payload"]
    sample_count = len(payload.get("samples") or [])
    lines = [
        f"名称：{payload.get('name') or '待补充'}",
        f"城市：{payload.get('city') or '不限'}",
        f"风格：{'、'.join(payload.get('styles') or []) or '待补充'}",
        f"价格：{payload.get('price') or '待补充'}",
        f"时长：{payload.get('duration') or '待补充'} 分钟",
        f"精修：{payload.get('image_count') or '待补充'} 张",
        f"包含：{'、'.join(payload.get('includes') or []) or '待补充'}",
        f"简介：{payload.get('description') or '待补充'}",
        f"参考图：{sample_count} 张" if sample_count else "参考图：未添加",
    ]
    return "\n".join(lines)


def _package_agent_result(
    db: Session,
    *,
    user_id: int,
    conversation_id: int,
    message_id: int,
    intent: AgentIntent,
    attachments: list[dict] | None,
    confirm_requested: bool,
    content: str | None,
) -> dict:
    """套餐发布代理：按缺失槽位、参考图与确认状态生成阶段性回复。"""
    attachment_images = _attachment_image_urls(attachments)
    if attachment_images:
        intent.slots = {
            **intent.slots,
            "sample_images": list(dict.fromkeys([
                *(intent.slots.get("sample_images") or []),
                *attachment_images,
            ])),
        }

    draft = _package_draft_from_slots(intent.slots, attachments)
    missing_slots = draft["missing_slots"]
    missing_labels = [PACKAGE_SLOT_LABELS.get(slot, slot) for slot in missing_slots]
    task_state = _latest_task_state(db, conversation_id, "publish_package") or {}
    reference_images_skipped = _is_reference_image_skip(content) or bool(intent.slots.get("sample_images_skipped"))

    if missing_slots:
        return {
            "content": (
                "我先把方案草稿整理好了：\n"
                f"{_package_summary_text(draft)}\n\n"
                f"还需要补充：{'、'.join(missing_labels)}。"
            ),
            "metadata": {
                "model": {
                    "provider": "platform_orchestrator",
                    "model": "package-agent-draft",
                },
                "package_draft": draft,
                "suggested_actions": [],
                "task_state": {
                    "task_type": "publish_package",
                    "status": "awaiting_details",
                    "slots": intent.slots,
                    "missing_slots": missing_slots,
                    "pending_action": None,
                },
            },
        }

    if (
        not draft["package_payload"].get("samples")
        and not reference_images_skipped
        and not confirm_requested
    ):
        return {
            "content": (
                "基础信息和简介已经齐了。要不要给这个方案加参考图？\n"
                f"{_package_summary_text(draft)}\n\n"
                "上传参考图后，它会作为方案样片展示；也可以跳过，下一步我再给你最终确认。"
            ),
            "metadata": {
                "model": {
                    "provider": "platform_orchestrator",
                    "model": "package-agent-reference-images",
                },
                "package_draft": draft,
                "suggested_actions": [
                    {
                        "type": "add_package_reference_images",
                        "label": "上传参考图",
                        "payload": {},
                        "requires_confirmation": False,
                    },
                    {
                        "type": "skip_package_reference_images",
                        "label": "跳过参考图",
                        "payload": draft["package_payload"],
                        "requires_confirmation": False,
                    },
                ],
                "task_state": {
                    "task_type": "publish_package",
                    "status": "awaiting_reference_images",
                    "slots": intent.slots,
                    "missing_slots": [],
                    "pending_action": None,
                },
            },
        }

    if task_state.get("status") == "awaiting_reference_images" and reference_images_skipped:
        intent.slots = {
            **intent.slots,
            "sample_images_skipped": True,
        }
        draft = _package_draft_from_slots(intent.slots, attachments)

    if confirm_requested:
        tool_call = publish_package_tool(
            db,
            user_id=user_id,
            conversation_id=conversation_id,
            message_id=message_id,
            package_payload=draft["package_payload"],
        )
        result = tool_call.get("result") or {}
        if tool_call["status"] == "success":
            content = f"方案已发布：{result.get('package_name')}。用户现在可以在方案列表里看到并预约。"
            status_value = "completed"
        else:
            content = f"方案发布失败：{result.get('error') or '工具执行失败'}。"
            status_value = "failed"
        return {
            "content": content,
            "metadata": {
                "model": {
                    "provider": "platform_tool",
                    "model": "publish-package",
                },
                "package_draft": draft,
                "tool_calls": [tool_call],
                "suggested_actions": [],
                "task_state": {
                    "task_type": "publish_package",
                    "status": status_value,
                    "slots": intent.slots,
                    "missing_slots": [],
                    "pending_action": None,
                },
            },
        }

    return {
        "content": (
            "我整理好了待发布的方案，请确认：\n"
            f"{_package_summary_text(draft)}\n\n"
            "确认后我会为你发布到方案列表。"
        ),
        "metadata": {
            "model": {
                "provider": "platform_orchestrator",
                "model": "package-agent-confirmation",
            },
            "package_draft": draft,
            "suggested_actions": [
                {
                    "type": "confirm_publish_package",
                    "label": "确认发布方案",
                    "payload": draft["package_payload"],
                    "requires_confirmation": True,
                }
            ],
            "task_state": {
                "task_type": "publish_package",
                "status": "awaiting_confirmation",
                "slots": intent.slots,
                "missing_slots": [],
                "pending_action": {
                    "tool": "publish_package",
                    "input": draft["package_payload"],
                },
            },
        },
    }


def _project_agent_result(
    db: Session,
    *,
    user_id: int,
    conversation_id: int,
    message_id: int,
    intent: AgentIntent,
    attachments: list[dict] | None,
    confirm_requested: bool,
    content: str | None,
) -> dict:
    """企划发布代理：按缺失槽位、参考图与确认状态生成阶段性回复。"""
    attachment_images = _attachment_image_urls(attachments)
    if attachment_images:
        intent.slots = {
            **intent.slots,
            "reference_images": list(dict.fromkeys([
                *(intent.slots.get("reference_images") or []),
                *attachment_images,
            ])),
        }
    draft = _project_draft_from_slots(intent.slots, attachments)
    missing_slots = draft["missing_slots"]
    save_as_draft = intent.slots.get("_submission_action") == "save_draft"
    task_state = _latest_task_state(db, conversation_id, "create_project") or {}
    reference_images_skipped = _is_reference_image_skip(content) or bool(intent.slots.get("reference_images_skipped"))

    if missing_slots and not save_as_draft:
        return {
            "content": "请直接在企划进度卡片中补充信息。",
            "metadata": {
                "model": {
                    "provider": "platform_orchestrator",
                    "model": "project-agent-draft",
                },
                "project_draft": draft,
                "suggested_actions": [],
                "task_state": {
                    "task_type": "create_project",
                    "status": "awaiting_details",
                    "slots": intent.slots,
                    "missing_slots": missing_slots,
                    "pending_action": None,
                },
            },
        }

    if (
        not draft["project_payload"].get("reference_images")
        and not reference_images_skipped
        and not confirm_requested
        and not save_as_draft
    ):
        return {
            "content": (
                "基础信息已经齐了。你可以在企划进度卡片中添加参考图，"
                "也可以直接继续发布。"
            ),
            "metadata": {
                "model": {
                    "provider": "platform_orchestrator",
                    "model": "project-agent-reference-images",
                },
                "project_draft": draft,
                "suggested_actions": [
                    {
                        "type": "add_project_reference_images",
                        "label": "上传参考图",
                        "payload": {},
                        "requires_confirmation": False,
                    },
                    {
                        "type": "skip_project_reference_images",
                        "label": "跳过参考图",
                        "payload": draft["project_payload"],
                        "requires_confirmation": False,
                    },
                ],
                "task_state": {
                    "task_type": "create_project",
                    "status": "awaiting_reference_images",
                    "slots": intent.slots,
                    "missing_slots": [],
                    "pending_action": None,
                },
            },
        }

    if task_state.get("status") == "awaiting_reference_images" and reference_images_skipped:
        intent.slots = {
            **intent.slots,
            "reference_images_skipped": True,
        }
        draft = _project_draft_from_slots(intent.slots, attachments)

    if confirm_requested:
        tool_call = create_project_tool(
            db,
            user_id=user_id,
            conversation_id=conversation_id,
            message_id=message_id,
            project_payload=draft["project_payload"],
        )
        result = tool_call.get("result") or {}
        if tool_call["status"] == "success":
            if save_as_draft:
                content = f"企划草稿已保存：{result.get('title')}。你可以在“我的企划”中继续编辑。"
            else:
                content = f"企划已发布：{result.get('title')}。摄影师现在可以在企划大厅看到并报名。"
            status_value = "completed"
        else:
            content = f"企划发布失败：{result.get('error') or '工具执行失败'}。"
            status_value = "failed"
        return {
            "content": content,
            "metadata": {
                "model": {
                    "provider": "platform_tool",
                    "model": "create-project",
                },
                "project_draft": draft,
                "tool_calls": [tool_call],
                "suggested_actions": [],
                "task_state": {
                    "task_type": "create_project",
                    "status": status_value,
                    "slots": intent.slots,
                    "missing_slots": [],
                    "pending_action": None,
                },
            },
        }

    return {
        "content": "企划信息已准备好，请在进度卡片中确认并发布。",
        "metadata": {
            "model": {
                "provider": "platform_orchestrator",
                "model": "project-agent-confirmation",
            },
            "project_draft": draft,
            "suggested_actions": [
                {
                    "type": "confirm_create_project",
                    "label": "确认发布企划",
                    "payload": draft["project_payload"],
                    "requires_confirmation": True,
                }
            ],
            "task_state": {
                "task_type": "create_project",
                "status": "awaiting_confirmation",
                "slots": intent.slots,
                "missing_slots": [],
                "pending_action": {
                    "tool": "create_project",
                    "input": draft["project_payload"],
                },
            },
        },
    }


def _latest_pending_action(db: Session, conversation_id: int) -> dict | None:
    """从最近的助手消息中获取等待确认的待执行动作。"""
    message = (
        db.query(AIMessage)
        .filter(AIMessage.conversation_id == conversation_id, AIMessage.role == "assistant")
        .order_by(AIMessage.created_at.desc(), AIMessage.id.desc())
        .first()
    )
    if not message:
        return None

    task_state = (message.message_metadata or {}).get("task_state") or {}
    if task_state.get("status") != "awaiting_confirmation":
        return None
    pending_action = task_state.get("pending_action") or {}
    if not pending_action.get("tool"):
        return None
    return {
        "task_state": task_state,
        "pending_action": pending_action,
    }


def _normalize_booking_pending_input(tool_input: dict, task_state: dict) -> dict:
    """补全预约待执行工具入参，回填历史槽位并规范化时间。"""
    normalized = dict(tool_input or {})
    slots = task_state.get("slots") or {}

    if not normalized.get("photographer_id") and slots.get("photographer_id"):
        normalized["photographer_id"] = slots["photographer_id"]
    if not normalized.get("duration_minutes") and slots.get("duration_minutes"):
        normalized["duration_minutes"] = slots["duration_minutes"]
    if not normalized.get("package_description"):
        package_description = (
            normalized.get("package_display")
            or slots.get("package_display")
            or ""
        )
        normalized["package_description"] = package_description

    appointment_date = normalized.get("appointment_date") or slots.get("date")
    appointment_time = normalized.get("appointment_time") or slots.get("time")
    if appointment_date and (
        not appointment_time
        or re.fullmatch(r"\d{1,2}:\d{2}", str(appointment_time))
    ):
        try:
            appointment_dt = build_booking_appointment_datetime(
                str(appointment_date),
                str(appointment_time) if appointment_time else None,
            )
            normalized["appointment_time"] = appointment_dt.isoformat()
        except ValueError:
            pass

    return normalized


def _requested_reference_index(content: str | None) -> int | None:
    """解析用户消息中的“第几个”，返回对应的引用下标。"""
    text = (content or "").strip()
    chinese_numbers = {
        "一": 1,
        "二": 2,
        "两": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
        "十": 10,
    }

    match = re.search(r"第\s*([一二两三四五六七八九十\d]+)\s*(?:个|位|名)?", text)
    if not match:
        match = re.search(r"([1-9]\d*)\s*(?:个|位|名|号)", text)
    if not match:
        return None

    raw_value = match.group(1)
    number = int(raw_value) if raw_value.isdigit() else chinese_numbers.get(raw_value)
    if not number:
        return None
    return number - 1


def _latest_project_references(db: Session, conversation_id: int) -> list[dict]:
    """Return the latest assistant project references for ordinal selection."""
    message = (
        db.query(AIMessage)
        .filter(
            AIMessage.conversation_id == conversation_id,
            AIMessage.role == "assistant",
        )
        .order_by(AIMessage.created_at.desc(), AIMessage.id.desc())
        .first()
    )
    if not message:
        return []
    references = (message.message_metadata or {}).get("references") or {}
    projects = references.get("projects") or []
    return [item for item in projects if isinstance(item, dict)]


def _resolve_project_reference(
    db: Session,
    conversation_id: int,
    content: str | None,
) -> dict | None:
    """Resolve a project selection against the latest recommendation and database."""
    from backend.app.models.project import ProjectStatus, ShootProject

    references = _latest_project_references(db, conversation_id)
    if not references:
        return None

    candidate = None
    index = _requested_reference_index(content)
    if index is not None and 0 <= index < len(references):
        candidate = references[index]
    if candidate is None:
        text = (content or "").strip()
        candidate = next(
            (
                item
                for item in references
                if item.get("title") and str(item["title"]) in text
            ),
            None,
        )
    if not candidate or candidate.get("id") in (None, ""):
        return None

    project = (
        db.query(ShootProject)
        .filter(
            ShootProject.id == candidate["id"],
            ShootProject.status == ProjectStatus.OPEN,
        )
        .first()
    )
    if not project:
        return None

    return {
        **candidate,
        "id": project.id,
        "title": project.title,
        "city": project.city,
        "valid": True,
    }


def _looks_like_project_application_request(content: str | None) -> bool:
    """Recognize an explicit application/selection command, not project advice."""
    text = (content or "").strip()
    if not text or _is_project_consultation(text):
        return False
    if any(term in text for term in ("找企划", "推荐企划", "可应邀的企划", "搜索企划")):
        return False
    return any(
        term in text
        for term in ("申请", "报名", "应邀", "接这个", "提交方案", "参加")
    )


def _project_application_intent(project: dict) -> AgentIntent:
    """Compatibility intent for applying to a project selected from recommendations."""
    return AgentIntent(
        intent="resource_search",
        sub_intents=["prepare_project_application"],
        slots={
            "project_id": project.get("id"),
            "resource_types": ["projects"],
        },
        route="project_application",
        confidence=0.95,
    )


def _project_application_agent_result(project: dict) -> dict:
    """Return the legacy recommendation handoff while the page owns the form."""
    project_id = project.get("id")
    return {
        "content": f"已找到企划「{project.get('title') or '当前企划'}」，可以继续完善应邀方案。",
        "metadata": {
            "model": {
                "provider": "platform_orchestrator",
                "model": "project-application-handoff",
            },
            "selected_project": project,
            "client_actions": [
                {
                    "type": "open_project_application",
                    "label": "填写应邀方案",
                    "project_id": project_id,
                }
            ],
            "task_state": {
                "task_type": "project_application",
                "status": "awaiting_details",
                "slots": {
                    "project_id": project_id,
                    "proposal_text": "",
                    "price_quote": "",
                    "package_snapshot": "",
                    "portfolio_refs": [],
                    "revision_note": "",
                },
                "missing_slots": [],
                "pending_action": None,
            },
        },
    }


def _match_photographer_by_name(content: str | None, photographers: list[dict]) -> dict | None:
    """按显示名称在摄影师列表中匹配用户提及的摄影师。"""
    text = (content or "").strip()
    if not text:
        return None

    candidates = []
    for photographer in photographers:
        display_name = (photographer.get("user_display_name") or "").strip()
        if display_name and display_name in text:
            candidates.append((len(display_name), photographer))

    if not candidates:
        return None
    return sorted(candidates, key=lambda item: item[0], reverse=True)[0][1]


def _latest_referenced_photographer(
    db: Session,
    conversation_id: int,
    content: str | None = None,
) -> dict | None:
    """从历史推荐中找出用户最新引用的摄影师。"""
    requested_index = _requested_reference_index(content)
    messages = (
        db.query(AIMessage)
        .filter(AIMessage.conversation_id == conversation_id, AIMessage.role == "assistant")
        .order_by(AIMessage.created_at.desc(), AIMessage.id.desc())
        .limit(settings.AI_MAX_HISTORY_MESSAGES)
        .all()
    )
    for message in messages:
        references = (message.message_metadata or {}).get("references") or {}
        photographers = references.get("photographers") or []
        if photographers:
            named_match = _match_photographer_by_name(content, photographers)
            if named_match:
                return named_match
            if requested_index is not None:
                if 0 <= requested_index < len(photographers):
                    return photographers[requested_index]
                continue
            return photographers[0]
    return None


def _first_retrieval_photographer(retrieval: dict | None) -> dict | None:
    """返回本次检索结果中的第一位摄影师。"""
    references = (retrieval or {}).get("references") or {}
    photographers = references.get("photographers") or []
    return photographers[0] if photographers else None


def _follow_confirmation_result(
    intent: AgentIntent,
    target: dict | None,
) -> dict:
    """生成关注摄影师确认阶段的回复结果。"""
    if not target:
        return {
            "content": "你想关注哪位摄影师？可以告诉我摄影师名字，或先让我帮你找几位摄影师再选择。",
            "metadata": {
                "model": {
                    "provider": "platform_orchestrator",
                    "model": "follow-confirmation",
                },
                "suggested_actions": [],
                "task_state": {
                    "task_type": "follow_photographer",
                    "status": "awaiting_target",
                    "slots": intent.slots,
                    "pending_action": None,
                },
            },
        }

    display_name = target.get("user_display_name") or f"摄影师 {target.get('user_id')}"
    photographer_id = target.get("user_id")
    return {
        "content": f"我准备帮你关注「{display_name}」。请确认后，我再执行关注操作。",
        "metadata": {
            "model": {
                "provider": "platform_orchestrator",
                "model": "follow-confirmation",
            },
            "suggested_actions": [
                {
                    "type": "confirm_follow_photographer",
                    "label": "确认关注",
                    "payload": {
                        "photographer_id": photographer_id,
                        "photographer_name": display_name,
                    },
                    "requires_confirmation": True,
                }
            ],
            "task_state": {
                "task_type": "follow_photographer",
                "status": "awaiting_confirmation",
                "slots": {
                    **intent.slots,
                    "photographer_id": photographer_id,
                    "photographer_name": display_name,
                },
                "pending_action": {
                    "tool": "follow_photographer",
                    "input": {"photographer_id": photographer_id},
                },
            },
        },
    }


def _execute_pending_action_result(
    db: Session,
    *,
    user_id: int,
    conversation_id: int,
    message_id: int,
    pending: dict,
) -> dict:
    """执行确认后的待处理工具动作并生成回复结果。"""
    pending_action = pending.get("pending_action") or {}
    task_state = pending.get("task_state") or {}
    tool_name = pending_action.get("tool")
    tool_input = pending_action.get("input") or {}

    if tool_name == "follow_photographer":
        photographer_id = tool_input.get("photographer_id")
        tool_call = follow_photographer(
            db,
            user_id=user_id,
            conversation_id=conversation_id,
            message_id=message_id,
            photographer_id=photographer_id,
        )
        result = tool_call.get("result") or {}
        photographer_name = (
            result.get("photographer_name")
            or (task_state.get("slots") or {}).get("photographer_name")
            or f"摄影师 {photographer_id}"
        )
        if tool_call["status"] == "success":
            content = f"已帮你关注「{photographer_name}」。之后你可以在关注列表里找到这位摄影师。"
            status_value = "completed"
        else:
            content = f"关注「{photographer_name}」失败了：{result.get('error') or '工具执行失败'}。"
            status_value = "failed"
        return {
            "content": content,
            "metadata": {
                "model": {
                    "provider": "platform_tool",
                    "model": "follow-photographer",
                },
                "tool_calls": [tool_call],
                "suggested_actions": [],
                "task_state": {
                    **task_state,
                    "status": status_value,
                    "pending_action": None,
                },
            },
        }

    if tool_name == "create_project":
        tool_call = create_project_tool(
            db,
            user_id=user_id,
            conversation_id=conversation_id,
            message_id=message_id,
            project_payload=tool_input,
        )
        result = tool_call.get("result") or {}
        if tool_call["status"] == "success":
            content = f"企划已发布：{result.get('title')}。摄影师现在可以在企划大厅看到并报名。"
            status_value = "completed"
        else:
            content = f"企划发布失败：{result.get('error') or '工具执行失败'}。"
            status_value = "failed"
        return {
            "content": content,
            "metadata": {
                "model": {
                    "provider": "platform_tool",
                    "model": "create-project",
                },
                "tool_calls": [tool_call],
                "suggested_actions": [],
                "task_state": {
                    **task_state,
                    "status": status_value,
                    "pending_action": None,
                },
            },
        }

    if tool_name == "publish_package":
        tool_call = publish_package_tool(
            db,
            user_id=user_id,
            conversation_id=conversation_id,
            message_id=message_id,
            package_payload=tool_input,
        )
        result = tool_call.get("result") or {}
        if tool_call["status"] == "success":
            content = f"方案已发布：{result.get('package_name')}。用户现在可以在方案列表里看到并预约。"
            status_value = "completed"
        else:
            content = f"方案发布失败：{result.get('error') or '工具执行失败'}。"
            status_value = "failed"
        return {
            "content": content,
            "metadata": {
                "model": {
                    "provider": "platform_tool",
                    "model": "publish-package",
                },
                "tool_calls": [tool_call],
                "suggested_actions": [],
                "task_state": {
                    **task_state,
                    "status": status_value,
                    "pending_action": None,
                },
            },
        }

    if tool_name == "create_booking":
        booking_input = _normalize_booking_pending_input(tool_input, task_state)
        tool_call = create_booking_tool(
            db,
            user_id=user_id,
            conversation_id=conversation_id,
            message_id=message_id,
            booking_payload=booking_input,
        )
        result = tool_call.get("result") or {}
        if tool_call["status"] == "success":
            content = (
                f"预约已创建！订单编号：{result.get('order_id')}，"
                f"状态：待摄影师确认。摄影师确认后你会收到通知。"
            )
            status_value = "completed"
        else:
            content = f"预约创建失败：{result.get('error') or '工具执行失败'}。"
            status_value = "failed"
        task_plan = advance_booking_plan(
            task_state,
            status=status_value,
            completed_step_ids=(
                "vision_analysis",
                "search_packages",
                "select_package",
                "select_time",
                "confirm_booking",
                "create_booking",
            ) if status_value == "completed" else (
                "vision_analysis",
                "search_packages",
                "select_package",
                "select_time",
                "confirm_booking",
            ),
            failed_step_id="create_booking" if status_value == "failed" else None,
        )
        next_task_state = {
            **task_state,
            "status": status_value,
            "pending_action": None,
        }
        metadata = {
            "model": {
                "provider": "platform_tool",
                "model": "create-booking",
            },
            "tool_calls": [tool_call],
            "suggested_actions": [],
            "task_state": next_task_state,
        }
        if task_plan:
            next_task_state["task_plan"] = task_plan
            metadata["task_plan"] = task_plan
        return {
            "content": content,
            "metadata": metadata,
        }

    return {
        "content": "这个操作我还不能执行。你可以重新告诉我要做什么，我会先帮你准备确认信息。",
        "metadata": {
            "model": {
                "provider": "platform_tool",
                "model": "unsupported-action",
            },
            "tool_calls": [
                {
                    "tool": tool_name,
                    "status": "failed",
                    "input": tool_input,
                    "result": {"error": "unsupported_tool"},
                }
            ],
            "task_state": {
                **task_state,
                "status": "failed",
                "pending_action": None,
            },
        },
    }


async def send_ai_message(
    db: Session,
    user_id: int,
    conversation_id: int,
    content: str | None,
    attachments: list[dict] | None = None,
    page_context: dict | None = None,
    task_submission: dict | None = None,
    shoot_context_selection: dict | None = None,
) -> tuple[AIMessage, AIMessage]:
    """AI 会话主入口：保存用户消息，完成意图识别、检索与工具编排后生成助手回复。"""
    trace_started_at = perf_counter()
    conversation = get_conversation_or_404(db, user_id, conversation_id)
    selected_shoot_context_arguments = _shoot_context_selection_arguments(
        db,
        conversation.id,
        shoot_context_selection,
    )
    normalized_page_context = _resolve_page_context(db, page_context)
    explicit_attachments = list(attachments or [])
    vision_attachments = explicit_attachments or _page_context_vision_attachments(
        content,
        normalized_page_context,
    )
    user_metadata = {}
    if explicit_attachments:
        user_metadata["attachments"] = explicit_attachments
    if normalized_page_context:
        user_metadata["page_context"] = normalized_page_context
    if task_submission:
        user_metadata["task_submission"] = task_submission
    if shoot_context_selection:
        user_metadata["shoot_context_selection"] = shoot_context_selection

    user_message = AIMessage(
        conversation_id=conversation.id,
        role="user",
        content=content or "",
        message_metadata=user_metadata or None,
    )
    db.add(user_message)
    conversation.updated_at = _now()
    if not conversation.title and content:
        conversation.title = _generate_title(content)
    db.commit()
    db.refresh(user_message)
    db.refresh(conversation)

    active_task_before = get_active_task(db, user_id, conversation.id)
    if active_task_before and not task_submission and content and not _is_task_cancel_request(content):
        patch = extract_task_patch(
            active_task_before.task_type,
            content,
            page_context=normalized_page_context,
            existing_fields=active_task_before.fields or {},
        )
        operations = patch.get("operations") or []
        if operations:
            active_task_before = patch_task(
                db,
                user_id=user_id,
                conversation_id=conversation.id,
                task_id=active_task_before.id,
                revision=active_task_before.revision,
                operations=operations,
                source_message_id=user_message.id,
            )
        if explicit_attachments:
            existing_media = list(active_task_before.media_assets or [])
            for attachment in explicit_attachments:
                url = attachment.get("url") if isinstance(attachment, dict) else None
                if url and url not in existing_media:
                    existing_media.append(url)
            active_task_before.media_assets = existing_media
            active_task_before.updated_at = _now()
        db.flush()

    normalized_submission = normalize_submission(task_submission)
    task_submission_result = None
    if normalized_submission and (
        "form_data" in (task_submission or {})
        or normalized_submission.get("action") == "cancel"
    ):
        try:
            task_submission_result = submit_form_task(
                db,
                user_id=user_id,
                conversation_id=conversation.id,
                message_id=user_message.id,
                submission=normalized_submission,
            )
        except ValueError as exc:
            task_submission_result = {
                "content": "这张任务卡已被更新，请刷新后重新编辑。",
                "metadata": {
                    "agent_form_card": {
                        "task_id": normalized_submission.get("task_id"),
                        "task_type": normalized_submission.get("task_type"),
                        "status": "invalid",
                        "schema_version": 1,
                        "target": {},
                        "initial_fields": normalized_submission.get("form_data") or {},
                        "field_errors": {"_form": str(exc)},
                        "media": {"existing": normalized_submission.get("media_refs") or [], "limits": {}},
                        "actions": ["publish", "save_draft", "cancel"],
                        "revision": normalized_submission.get("revision", 1),
                    },
                    "task_state": {
                        "task_type": normalized_submission.get("task_type"),
                        "status": "failed",
                        "task_id": normalized_submission.get("task_id"),
                        "revision": normalized_submission.get("revision", 1),
                    },
                },
            }

    embedded_form_result = None
    if not normalized_submission:
        embedded_task_type = infer_initial_task_type(content, normalized_page_context)
        current_form_card = latest_form_card(db, conversation.id)
        current_is_editing = bool(current_form_card and current_form_card.get("status") in EDITABLE_STATUSES)
        if embedded_task_type and not current_is_editing:
            embedded_form_result = initial_form_result(embedded_task_type, normalized_page_context or {})

    submitted_intent = None if task_submission_result or embedded_form_result else (
        _project_intent_from_task_submission(task_submission)
        or _package_intent_from_task_submission(task_submission)
    )
    project_application_reference = None
    project_application_result = None
    if (
        not normalized_submission
        and not normalized_page_context
        and _looks_like_project_application_request(content)
    ):
        project_application_reference = _resolve_project_reference(
            db,
            conversation.id,
            content,
        )
        if project_application_reference:
            project_application_result = _project_application_agent_result(
                project_application_reference,
            )

    # 确定性前置检查
    cancel_task_state = _latest_cancellable_task_state(db, conversation.id) if _is_task_cancel_request(content) else None
    pending_candidate = (
        _latest_pending_action(db, conversation.id)
        if cancel_task_state is None and submitted_intent is None and _is_confirmation(content)
        else None
    )
    pending_action = pending_candidate if _pending_action_is_confirmed(content, pending_candidate) else None

    # 多轮资源检索：先取出上一轮留下的 search_context，
    # 既用于告诉分类器“存在一个进行中的资源搜索”，也用于识别本轮是否是“换一个”。
    previous_search_context = (
        latest_search_context(db, conversation.id)
        if cancel_task_state is None and submitted_intent is None
        else None
    )
    working_memory = None
    workspace_source = "none"
    stale_workspace_discarded = False
    workspace_task_type_mismatch = False
    task_transition = "none"
    if cancel_task_state is None and submitted_intent is None:
        try:
            durable_working_memory = load_latest_working_memory(
                db,
                user_id=user_id,
                conversation_id=conversation.id,
            )
            cached_working_memory = get_working_memory(user_id, conversation.id)
            if durable_working_memory is None:
                clear_active_task_pointer(user_id, conversation.id)
                workspace_source = "none"
            elif (
                cached_working_memory
                and cached_working_memory.get("task_id") == durable_working_memory.get("task_id")
                and cached_working_memory.get("task_type") == durable_working_memory.get("task_type")
            ):
                working_memory = cached_working_memory
                workspace_source = "redis"
            else:
                if cached_working_memory:
                    workspace_task_type_mismatch = (
                        cached_working_memory.get("task_type") != durable_working_memory.get("task_type")
                        or cached_working_memory.get("task_id") != durable_working_memory.get("task_id")
                    )
                    stale_workspace_discarded = True
                working_memory = durable_working_memory
                workspace_source = "database"
                from backend.app.services.agent_working_memory_service import save_working_memory
                save_working_memory(user_id, conversation.id, working_memory)
        except Exception:
            working_memory = None
    # A search context is usable only inside the durable active task that
    # produced it. Legacy contexts without task identity are intentionally
    # ignored for refinement to prevent cross-task exclusion/style leakage.
    previous_search_context_stale = False
    previous_search_task_id = (previous_search_context or {}).get("task_id")
    if previous_search_context is not None:
        if not working_memory or working_memory.get("status") != "active":
            previous_search_context_stale = True
            previous_search_context = None
            stale_workspace_discarded = True
        elif previous_search_context.get("task_id") != working_memory.get("task_id"):
            previous_search_context_stale = True
            previous_search_context = None
            stale_workspace_discarded = True
    # Long-term memories are advisory context for the final language model only;
    # they must never affect deterministic task/reference routing or retrieval.
    long_term_memory_prompt = None
    task_episode_prompt = None
    referenced_task_episodes = []
    resume_task_result = None
    if cancel_task_state is None and submitted_intent is None:
        try:
            long_term_memory_prompt = _build_long_term_memory_prompt(
                active_user_memories(db, user_id)
            )
        except Exception:
            long_term_memory_prompt = None
        if task_memory_mode(content) == "summary":
            try:
                referenced_task_episodes = list_recent_task_episodes(db, user_id=user_id, limit=5)
                task_episode_prompt = build_task_episode_prompt(referenced_task_episodes)
            except Exception:
                task_episode_prompt = None
        elif task_memory_mode(content) == "resume":
            try:
                referenced_task_episodes = search_task_episodes(
                    db, user_id=user_id, query=content or "", limit=3,
                )
                if len(referenced_task_episodes) == 1:
                    resumed_task, working_memory = resume_task(
                        db,
                        user_id=user_id,
                        conversation_id=conversation.id,
                        task_id=referenced_task_episodes[0]["task_id"],
                        message_id=user_message.id,
                    )
                    db.commit()
                    workspace_source = "database"
                    task_transition = "resume"
                    previous_search_context = None
                    resume_task_result = {
                        "content": f"已恢复历史任务：{referenced_task_episodes[0]['summary']}",
                        "metadata": {"model": {"provider": "platform_task", "model": "task-resume"}},
                    }
                elif referenced_task_episodes:
                    labels = [item.get("summary") for item in referenced_task_episodes if item.get("summary")]
                    resume_task_result = {
                        "content": "找到多个可能的历史任务，请说明要继续哪一个：\n" + "\n".join(
                            f"{index}. {label}" for index, label in enumerate(labels, start=1)
                        ),
                        "metadata": {"model": {"provider": "platform_task", "model": "task-resume-clarify"}},
                    }
                else:
                    resume_task_result = {
                        "content": "没有找到与这次描述匹配的可恢复历史任务。",
                        "metadata": {"model": {"provider": "platform_task", "model": "task-resume-empty"}},
                    }
            except Exception:
                db.rollback()
                resume_task_result = {
                    "content": "历史任务暂时无法恢复，请稍后重试。",
                    "metadata": {"model": {"provider": "platform_task", "model": "task-resume-error"}},
                }
    if working_memory and is_task_exit_request(content):
        working_memory = pause_working_memory(user_id, conversation.id)
        if working_memory:
            try:
                task_session = sync_working_memory(
                    db,
                    user_id=user_id,
                    conversation_id=conversation.id,
                    memory=working_memory,
                    message_id=user_message.id,
                )
                finalize_task_memory(db, task=task_session, outcome="paused")
                db.commit()
            except Exception:
                db.rollback()
    resource_reference = (
        resolve_resource_reference(working_memory, content)
        if (
            not is_task_exit_request(content)
            and not is_search_refinement(content)
            and not _extract_booking_slots(content)
        )
        else None
    )
    resource_reference_prompt = build_resource_reference_prompt(resource_reference)
    search_refinement = None

    # 灰度门（阶段C §4-C.1、§4-C.2）：先算出本轮生效的 routing mode，
    # 因为“要不要省掉那次分类 LLM”取决于决策层这一轮是否真的接管。
    routing_rollout = resolve_routing_rollout(
        user_id=user_id,
        conversation_id=conversation.id,
    )
    routing_mode = routing_rollout.mode
    deterministic_entry = (
        submitted_intent is not None
        or cancel_task_state is not None
        or pending_action is not None
        or selected_shoot_context_arguments is not None
        or task_submission_result is not None
        or embedded_form_result is not None
        or project_application_result is not None
        or resume_task_result is not None
    )
    # 阶段C §4-C.4：决策层接管时不再为同一条消息做两次理解。
    # 命中灰度的 tool_loop 请求先用规则识别拿一个便宜的基线意图（顺带作为参数校验与
    # 风险兜底，§4-C.5），只有决策层没接管时才补一次完整的分类调用。
    defer_classification = bool(
        settings.AI_DECISION_SKIPS_INTENT_CLASSIFIER
        and routing_mode == "tool_loop"
        and not deterministic_entry
        and (content or "").strip()
    )

    def _contextualize(base: AgentIntent) -> tuple[AgentIntent, dict | None]:
        """既有的上下文修正链：发布/套餐/预约续轮 + “换一个”继承。"""
        booking_facts = _extract_booking_slots(content)
        if booking_facts and base.intent != "booking_flow":
            rule_booking = recognize_intent_by_rules(content, vision_attachments)
            if rule_booking.intent == "booking_flow":
                base = AgentIntent(
                    intent="booking_flow",
                    sub_intents=rule_booking.sub_intents,
                    slots=_merge_slots(base.slots, rule_booking.slots),
                    missing_slots=rule_booking.missing_slots,
                    requires_confirmation=True,
                    route="booking",
                    confidence=max(base.confidence, rule_booking.confidence),
                )
        resolved = _project_contextual_intent(db, conversation.id, base, vision_attachments, content)
        resolved = _package_contextual_intent(db, conversation.id, resolved, vision_attachments, content)
        resolved = _booking_contextual_intent(
            db,
            conversation.id,
            resolved,
            content=content,
            user_id=user_id,
        )
        candidate = resolve_refinement(content, previous_search_context)
        explicit_types = explicit_resource_types(content)
        if candidate and explicit_types:
            previous_types = (previous_search_context or {}).get("slots", {}).get("resource_types") or []
            if previous_types and set(explicit_types) != set(previous_types):
                candidate = None
        resolved = _refined_search_intent(resolved, candidate, content, vision_attachments)
        # 只有真的落成资源搜索时才让 refinement 生效；发布/预约流程不受影响。
        return resolved, (candidate if candidate and resolved.intent == "resource_search" else None)

    async def _classify() -> AgentIntent:
        nonlocal classification
        classification = await classify_intent(
            content,
            vision_attachments,
            active_task=(
                active_task_context(working_memory)
                or active_search_task(previous_search_context)
            ),
            page_context=normalized_page_context,
        )
        return classification.intent

    # 意图识别：task_submission → 取消任务 → pending action → 规则(灰度去重) / LLM 分类器
    classification = None
    if selected_shoot_context_arguments:
        intent = recognize_intent("查询天气")
    elif submitted_intent:
        intent = submitted_intent
    elif embedded_form_result:
        intent = recognize_intent("普通聊天")
    elif project_application_result:
        intent = _project_application_intent(project_application_reference or {})
    elif cancel_task_state:
        intent = recognize_intent(content, vision_attachments)
    elif pending_action:
        intent = recognize_intent(content, vision_attachments)
    elif defer_classification:
        intent = recognize_intent(content, vision_attachments)
    else:
        intent = await _classify()

    # Project application handoff is classified like any other user intent. The
    # target ID still comes only from the trusted project page context.
    if intent.intent == "project_application":
        if normalized_page_context and normalized_page_context.get("resource_type") == "project":
            current_form_card = latest_form_card(db, conversation.id)
            current_is_editing = bool(
                current_form_card and current_form_card.get("status") in EDITABLE_STATUSES
            )
            if not current_is_editing:
                embedded_form_result = initial_form_result(
                    "project_application",
                    normalized_page_context,
                )
                deterministic_entry = True
        else:
            # Without a current project there is no safe target to hand off to;
            # fall back to finding projects instead of opening an unbound form.
            intent = recognize_intent("有没有可应邀的企划")

    vision_provider_result = None
    vision_analysis = None
    vision_search_text = None
    vision_reused_context = False
    page_context_prompt = _build_page_context_prompt(normalized_page_context)

    if not deterministic_entry:
        intent, search_refinement = _contextualize(intent)
    if resource_reference is not None:
        booking_reference_request = intent.intent == "booking_flow" or any(
            term in (content or "") for term in ("预约", "预订", "订这个")
        )
        if not booking_reference_request:
            # Resource inspection is a continuation of the active task.
            intent = AgentIntent(
                intent="chat",
                sub_intents=["inspect_task_resource"],
                slots={},
                missing_slots=[],
                requires_confirmation=False,
                route="chat",
                confidence=1.0,
                parser="rules",
            )
        search_refinement = None
        try:
            working_memory = update_working_memory(
                user_id,
                conversation.id,
                status="active",
                selected_resource=resource_reference,
                event={
                    "type": "resource_reference",
                    "message_id": user_message.id,
                    "resource_id": resource_reference.get("resource_id"),
                    "index": resource_reference.get("index"),
                },
            )
            sync_working_memory(
                db,
                user_id=user_id,
                conversation_id=conversation.id,
                memory=working_memory,
                message_id=user_message.id,
            )
            db.commit()
        except Exception:
            db.rollback()
            pass

    project_discovery_guard_result = None
    if (
        intent.intent == "resource_search"
        and intent.route == "project_discovery"
        and intent.slots.get("resource_types") == ["projects"]
        and _agent_user_role(db, user_id) != "photographer"
        and _latest_task_state(db, conversation.id, "create_project") is None
    ):
        project_discovery_guard_result = {
            "content": "企划大厅目前面向摄影师开放，摄影师可以在这里查找并申请合适的企划。",
            "metadata": {
                "model": {
                    "provider": "platform_guardrail",
                    "model": "project-discovery-role-guard",
                },
                "references": {
                    "photographers": [],
                    "portfolio_items": [],
                    "packages": [],
                    "projects": [],
                },
            },
        }
        intent = recognize_intent("普通聊天")
        deterministic_entry = True

    # 统一决策层（阶段B §4.2）：取消任务、待确认动作、表单提交这三种确定性入口不参与决策。
    decision_outcome = None
    decision_plan = None
    decision_diff = None
    active_booking_task = get_active_task(db, user_id, conversation.id)
    has_active_booking_task = bool(
        active_booking_task and active_booking_task.task_type == "create_booking"
    )
    decision_eligible = (
        routing_mode != "legacy"
        and not deterministic_entry
        and not has_active_booking_task
        and resource_reference is None
        and bool((content or "").strip())
    )
    if selected_shoot_context_arguments:
        user_role = _agent_user_role(db, user_id)
        decision_outcome = AgentDecisionOutcome(
            decision=AgentDecision(
                mode="tool_call",
                tool="get_shoot_context",
                arguments=selected_shoot_context_arguments,
                confidence=1.0,
                reason="用户选择了后端已校验的地点候选",
            ),
            parser="deterministic",
        )
        decision_diff = compare_decision_with_intent(decision_outcome, intent)
        decision_plan = resolve_decision_plan(
            decision_outcome,
            legacy_intent_name="chat",
            user_role=user_role,
            allow_writes=False,
        )
    elif decision_eligible:
        user_role = _agent_user_role(db, user_id)
        decision_outcome = await decide_agent_action(
            content=content,
            has_image=_has_image_attachments(vision_attachments),
            user_role=user_role,
            history=_decision_history(
                db,
                conversation.id,
                exclude_message_id=user_message.id,
                limit=(settings.AI_AGENT_DECISION_MAX_HISTORY if working_memory else 6),
            ),
            page_context=_decision_page_context(normalized_page_context),
            # 只给槽位和资源名称，不给资源 ID：排除逻辑在后端。
            search_context=(
                active_task_context(working_memory)
                or active_search_task(previous_search_context)
            ),
            allow_writes=settings.AI_AGENT_DECISION_ALLOW_WRITE_TOOLS,
        )
        # 去重开关打开时这里比的是“规则 vs 决策”，因为本轮压根没调分类 LLM。
        decision_diff = compare_decision_with_intent(decision_outcome, intent)
        decision_plan = resolve_decision_plan(
            decision_outcome,
            legacy_intent_name=intent.intent,
            user_role=user_role,
            # 写工具一律不在这里执行：既有确认流程 + 事务 + 幂等键仍是唯一入口（§5.2）。
            allow_writes=False,
            exclude_resource_ids=(search_refinement or {}).get("exclude_resource_ids"),
            active_task_types=("resource_search",) if previous_search_context else (),
        )

    # shadow 模式只记录差异，不改变行为；tool_loop 才真正接管路由。
    decision_applied = bool(
        decision_plan is not None
        and decision_plan.applied
        and (selected_shoot_context_arguments is not None or routing_mode == "tool_loop")
    )
    decision_tool_active = decision_applied and decision_plan.action == "search"
    decision_read_tool_active = decision_applied and decision_plan.action == "read_tool"
    decision_clarify_active = decision_applied and decision_plan.action == "clarify"
    # 省掉的分类调用要在决策层没接管时补回来：既有路由的质量不能因为灰度而下降。
    if defer_classification and not decision_applied:
        intent, search_refinement = _contextualize(await _classify())
    if decision_applied and decision_plan.action == "search":
        intent = _decision_search_intent(
            intent,
            tool_name=decision_plan.tool,
            arguments=decision_plan.arguments,
            attachments=vision_attachments,
            confidence=decision_outcome.decision.confidence,
        )
        # 排除逻辑已经通过工具入参生效，refinement 不再重复注入检索层。
        search_refinement = search_refinement if previous_search_context else None
    elif decision_applied and decision_plan.action == "chat":
        intent = _decision_chat_intent(
            intent,
            attachments=vision_attachments,
            confidence=decision_outcome.decision.confidence,
        )
        search_refinement = None

    shoot_context = None
    web_search_call = None
    if decision_read_tool_active and decision_plan.tool == "search_web":
        task_form_id = f"conversation_{conversation.id}_message_{user_message.id}"
        web_search_call = await run_web_search(
            arguments=decision_plan.arguments,
            task_form_id=task_form_id,
            conversation_id=conversation.id,
            message_id=user_message.id,
        )
    if decision_read_tool_active and decision_plan.tool == "get_shoot_context":
        try:
            shoot_context = await ShootContextService().get_context(decision_plan.arguments)
        except Exception:
            # 将供应商异常收敛为结构化元数据，聊天主链路仍可正常返回。
            shoot_context = {
                "schema_version": "shoot_context_v1",
                "status": "failed",
                "place": None,
                "weather": None,
                "sunlight": None,
                "recommendations": [],
                "place_candidates": [],
                "error_code": "service_unavailable",
            }
    shoot_context_error_result = (
        _shoot_context_error_result(shoot_context, decision_plan.arguments)
        if decision_read_tool_active
        else None
    )
    # 在视觉分析写入风格槽位之前保存用户/决策层明确给出的检索条件。
    # MiMo 从图片推断出的风格进入检索文本做软排序，不应冒充用户明确的硬过滤条件。
    explicit_retrieval_criteria = criteria_from_slots(intent.slots)

    if cancel_task_state is None and pending_action is None and _should_run_vision_analysis(intent, vision_attachments):
        provider_messages = _build_provider_messages(
            db,
            conversation.id,
            extra_system_prompts=[VISION_SYSTEM_PROMPT],
        )
        provider = get_ai_provider()
        vision_provider_result = await provider.chat(provider_messages)
        vision_analysis = normalize_vision_analysis(
            vision_provider_result,
            content=content,
            attachments=vision_attachments,
        )
        intent = _apply_vision_slots(intent, vision_analysis)

    elif cancel_task_state is None and pending_action is None and _should_reuse_latest_vision_analysis(intent, content, vision_attachments):
        vision_analysis = _latest_vision_analysis(db, conversation.id)
        if vision_analysis:
            vision_provider_result = {
                "metadata": {
                    "model": {
                        "provider": "platform_memory",
                        "model": "vision-analysis-context",
                    }
                }
            }
            vision_reused_context = True
            intent = _apply_vision_slots(intent, vision_analysis)

    retrieval_content = content
    if vision_analysis and should_run_retrieval(intent):
        vision_search_text = build_vision_search_text(content, vision_analysis)
        retrieval_content = vision_search_text
    elif normalized_page_context and should_run_retrieval(intent):
        retrieval_content = _page_context_retrieval_text(content, normalized_page_context)

    retrieval_requested = (
        should_run_retrieval(intent)
        and cancel_task_state is None
        and pending_action is None
        and not has_active_booking_task
        and not decision_clarify_active
        and not decision_read_tool_active
    )
    tool_call = None
    retrieval = None
    # retrieval_payload 与 retrieval 在既有路径上是同一份数据；企划工具没有对应的
    # 文档检索结果（build_retrieval_context / has_reference_matches 只认三类资源），
    # 所以 references / citation_policy / search_context 统一用 payload 构建。
    retrieval_payload = None
    if retrieval_requested and decision_tool_active:
        tool_call = run_search_tool(
            db,
            tool_name=decision_plan.tool,
            # 入参已由 authorize_tool_call 校验并归一化，排除列表由后端注入。
            arguments=decision_plan.arguments,
            user=_agent_user(db, user_id),
            vision_analysis=vision_analysis,
            image_attachments=vision_attachments,
            request_content=content,
        )
        retrieval = tool_call.get("retrieval")
        retrieval_payload = tool_call.get("payload")
    elif retrieval_requested and intent.slots.get("resource_types") == ["projects"]:
        project_slots = intent.slots or {}
        project_arguments = {
            "city": project_slots.get("city"),
            "styles": slot_styles(project_slots),
            "budget_max": project_slots.get("budget_max"),
            "limit": project_slots.get("limit", 3),
            "exclude_resource_ids": (search_refinement or {}).get("exclude_resource_ids", []),
        }
        tool_call = run_search_tool(
            db,
            tool_name="search_projects",
            arguments=project_arguments,
            user=_agent_user(db, user_id),
        )
        retrieval = tool_call.get("retrieval")
        retrieval_payload = tool_call.get("payload")
    elif retrieval_requested:
        retrieval = retrieve_references(
            db,
            retrieval_content,
            limit=intent.slots.get("limit", 3),
            resource_types=intent.slots.get("resource_types"),
            vision_analysis=vision_analysis,
            image_attachments=vision_attachments,
            # 本轮意图已确认的城市、风格、预算直接作为检索条件，
            # 不让检索器再从反馈型原文重新猜一遍。
            criteria_overrides=explicit_retrieval_criteria,
            inherited_criteria=retrieval_overrides(search_refinement),
            exclude_resource_ids=(search_refinement or {}).get("exclude_resource_ids"),
        )
        retrieval_payload = retrieval
    if retrieval_requested:
        try:
            log_retrieval_run(
                db,
                user_id=user_id,
                conversation_id=conversation.id,
                message_id=user_message.id,
                query_text=(
                    (tool_call.get("result") or {}).get("criteria", {}).get("text") or ""
                    if tool_call
                    else retrieval_content or ""
                ),
                intent=intent.as_dict(),
                retrieval=retrieval_payload,
            )
        except Exception:
            db.rollback()

        # Keep a compact, structured copy of the active search in Redis. The
        # message metadata/search_context remains the durable compatibility
        # path, while this working memory is what the decision layer can use
        # for references such as “the second package” on the next turn.
        try:
            resource_types = (retrieval_payload or {}).get("criteria", {}).get("resource_types") or intent.slots.get("resource_types") or []
            task_type = f"{resource_types[0][:-1] if resource_types and resource_types[0].endswith('s') else resource_types[0]}_search" if resource_types else "resource_search"
            references = (retrieval_payload or {}).get("references") or {}
            resource_items = []
            for resource_key in resource_types:
                for index, item in enumerate(references.get(resource_key) or [], start=1):
                    resource_items.append({
                        "index": index,
                        "resource_type": resource_key,
                        "resource_id": item.get("id") or item.get("package_id") or item.get("user_id"),
                        "snapshot": item,
                        "text_summary": resource_text_summary(item),
                    })
            _, working_memory, task_transition = apply_task_workspace_update(
                db,
                user_id=user_id,
                conversation_id=conversation.id,
                task_type=task_type,
                status="active" if resource_items else "paused",
                slots=dict(intent.slots or {}),
                form={"criteria": (retrieval_payload or {}).get("criteria") or {}},
                resources=resource_items,
                selected_resource=resource_items[0] if len(resource_items) == 1 else None,
                last_tool={
                    "name": tool_call.get("tool") if tool_call else "retrieve_references",
                    "status": tool_call.get("status") if tool_call else ("success" if retrieval_payload else "empty"),
                    "count": len(resource_items),
                },
                event={"type": "search", "message_id": user_message.id, "query": content or ""},
                message_id=user_message.id,
            )
            db.commit()
        except Exception:
            # Working memory must never make a successful search fail.
            db.rollback()

    # 工具路径下的命中判断不能只看三类文档资源，企划命中同样算命中。
    retrieval_has_matches = (
        _tool_call_item_count(tool_call) > 0
        if tool_call
        else has_reference_matches(retrieval)
    )
    tool_call_failed = bool(tool_call) and tool_call.get("status") == "failed"
    # 企划等不走 build_retrieval_context 的资源，用工具专属约束把真实 items 交给最终 LLM（§4.5）。
    tool_result_prompt = (
        build_tool_result_prompt(tool_call)
        if tool_call is not None and retrieval is None and not tool_call_failed
        else None
    )

    if resume_task_result is not None:
        result = resume_task_result
    elif task_submission_result is not None:
        result = task_submission_result
    elif embedded_form_result is not None:
        result = embedded_form_result
    elif project_application_result is not None:
        result = project_application_result
    elif project_discovery_guard_result is not None:
        result = project_discovery_guard_result
    elif cancel_task_state is not None:
        result = _task_cancel_result(cancel_task_state)
    elif pending_action and active_task_before is None:
        result = _execute_pending_action_result(
            db,
            user_id=user_id,
            conversation_id=conversation.id,
            message_id=user_message.id,
            pending=pending_action,
        )
    elif (
        active_task_before is not None
        and active_task_before.task_type not in {"resource_search", "package_search", "photographer_search", "project_search"}
        and intent.intent not in {"project_flow", "package_publish_flow", "booking_flow"}
    ):
        result = _active_task_progress_result(active_task_before)
    elif decision_read_tool_active and decision_plan.tool == "search_web":
        if not web_search_call or web_search_call.get("status") == "failed":
            result = {"content": "联网搜索暂时不可用，请稍后再试。", "metadata": {}}
        elif web_search_call.get("status") == "empty":
            result = {"content": "我没有找到可用的公开网页结果。可以换一个更具体的搜索词再试。", "metadata": {}}
        else:
            provider_messages = _build_provider_messages(
                db,
                conversation.id,
                extra_system_prompts=[
                    "本轮是独立的联网搜索回答。忽略历史消息中任何摄影师、套餐或平台推荐内容；不得复用或延续旧推荐。只能根据下面真实返回的网页资料回答用户当前问题。若网页资料不足，明确说明，不得用模型记忆补充。",
                    build_web_search_context(web_search_call.get("record")),
                ],
                page_context_prompt=page_context_prompt,
            )
            result = await get_ai_provider().chat(provider_messages)
            result["content"], citation_warnings = enforce_web_citations(
                result.get("content") or "", (web_search_call.get("result") or {}).get("items") or []
            )
            if citation_warnings:
                result.setdefault("metadata", {})["web_citation_warnings"] = citation_warnings
                increment_web_metric("citation_warning")
            else:
                increment_web_metric("citation_clean")
    elif decision_read_tool_active:
        if shoot_context_error_result is not None:
            result = shoot_context_error_result
        else:
            # 将真实工具结果作为受约束的系统上下文交给模型，只让模型负责组织语言。
            tool_prompt = (
                "以下是 get_shoot_context 的结构化真实结果。只能复述其中的地点、天气、日照和建议；"
                "不要补造天气数值、坐标、来源响应或未提供的地点选择。\n"
                + json.dumps(shoot_context or {}, ensure_ascii=False)
            )
            provider_messages = _build_provider_messages(
                db,
                conversation.id,
                extra_system_prompts=[tool_prompt],
                page_context_prompt=page_context_prompt,
            )
            result = await get_ai_provider().chat(provider_messages)
    elif intent.intent == "project_flow":
        result = _project_agent_result(
            db,
            user_id=user_id,
            conversation_id=conversation.id,
            message_id=user_message.id,
            intent=intent,
            attachments=attachments,
            confirm_requested=active_task_before is None and (
                submitted_intent is not None or _is_explicit_task_confirmation(content, "create_project")
            ),
            content=content,
        )
    elif intent.intent == "package_publish_flow":
        result = _package_agent_result(
            db,
            user_id=user_id,
            conversation_id=conversation.id,
            message_id=user_message.id,
            intent=intent,
            attachments=attachments,
            confirm_requested=active_task_before is None and (
                submitted_intent is not None or _is_explicit_task_confirmation(content, "publish_package")
            ),
            content=content,
        )
    elif should_run_booking_plan(intent, retrieval):
        result = booking_plan_result(
            intent=intent,
            retrieval=retrieval,
            vision_analysis=vision_analysis,
            vision_reused_context=vision_reused_context,
        )
    elif intent.intent == "booking_flow":
        result = booking_agent_result(
            db,
            user_id=user_id,
            conversation_id=conversation.id,
            message_id=user_message.id,
            content=content,
            confirm_requested=active_task_before is None and _is_explicit_task_confirmation(content, "create_booking"),
            package_reference=resource_reference,
        )
    elif intent.intent == "follow_photographer":
        target = _latest_referenced_photographer(db, conversation.id, content) or _first_retrieval_photographer(retrieval)
        result = _follow_confirmation_result(intent, target)
    elif intent.intent == "image_analysis" and vision_analysis and vision_provider_result:
        result = _vision_agent_result(
            vision_provider_result,
            vision_analysis,
            content=content,
            attachments=vision_attachments,
        )
    elif intent.intent == "resource_search" and vision_analysis and vision_provider_result and vision_search_text:
        result = _vision_retrieval_agent_result(
            vision_provider_result,
            vision_analysis,
            content=content,
            attachments=vision_attachments,
            search_text=vision_search_text,
            resource_types=intent.slots.get("resource_types"),
            retrieval=retrieval,
            reused_context=vision_reused_context,
        )
    elif decision_clarify_active:
        result = _decision_clarify_result(decision_plan.question)
    elif _is_recommendation_count_correction(content):
        result = _recommendation_count_correction_result()
    elif (retrieval_payload is not None or tool_call_failed) and not retrieval_has_matches and (
        search_refinement is not None
        or decision_tool_active
        or _should_use_empty_retrieval_fallback(content, retrieval_payload)
    ):
        result = await _empty_retrieval_result(
            db,
            conversation_id=conversation.id,
            retrieval=retrieval_payload,
            refinement=search_refinement,
            page_context_prompt=page_context_prompt,
        )
    else:
        extra_system_prompts = [
            prompt
            for prompt in (
                tool_result_prompt,
                resource_reference_prompt,
                long_term_memory_prompt,
                task_episode_prompt,
            )
            if prompt
        ]
        provider_messages = _build_provider_messages(
            db,
            conversation.id,
            build_retrieval_context(retrieval),
            extra_system_prompts=extra_system_prompts or None,
            page_context_prompt=page_context_prompt,
        )
        provider = get_ai_provider()
        result = await provider.chat(provider_messages)

    if (
        active_task_before is not None
        and active_task_before.task_type not in {"resource_search", "package_search", "photographer_search", "project_search"}
        and not task_submission
        and cancel_task_state is None
        and not web_search_call
    ):
        progress_result = _active_task_progress_result(active_task_before)
        result = {
            **result,
            "content": progress_result["content"],
            "metadata": {
                **(result.get("metadata") or {}),
                **(progress_result.get("metadata") or {}),
            },
        }

    assistant_metadata = {
        **(result.get("metadata") or {}),
        "intent": intent.as_dict(),
        "versions": {
            "prompt": settings.AI_PROMPT_VERSION,
            "orchestrator": settings.AI_ORCHESTRATOR_VERSION,
            "index": settings.AI_INDEX_VERSION,
        },
        # 灰度归因（阶段C §4-C.2）：每一轮都记，legacy 侧也记，
        # 否则算不出灰度覆盖率，也没法把指标按 mode 分组对比。
        "agent_routing": {
            **routing_rollout.as_dict(),
            "classifier_deferred": defer_classification,
            "classifier_skipped": defer_classification and classification is None,
        },
    }
    # 意图分类诊断（仅当调用了分类器时）
    if classification is not None:
        assistant_metadata["intent_classification"] = {
            "schema_version": INTENT_CLASSIFICATION_TRACE_VERSION,
            "mode": settings.AI_INTENT_CLASSIFIER_MODE,
            "chosen_parser": classification.chosen_parser,
            "rule_intent": classification.rule_intent,
            "model_intent": (
                classification.model_candidate.get("intent")
                if classification.model_candidate
                else None
            ),
            "agreement": classification.agreement,
            "model_confidence": classification.model_confidence,
            "fallback_reason": classification.fallback_reason,
            "latency_ms": classification.model_latency_ms,
            "prompt_version": classification.prompt_version,
            "provider": classification.model_provider,
            "model": classification.model_name,
        }
    if normalized_page_context:
        assistant_metadata["page_context"] = normalized_page_context
    # 决策层诊断：协议版本、原始输出、解析结果、选中的工具与参数、回退原因（§5.5）。
    if decision_outcome is not None:
        assistant_metadata["agent_decision"] = {
            **decision_outcome.as_trace(),
            "routing_mode": routing_mode,
            "applied": decision_applied,
            "plan": decision_plan.as_dict() if decision_plan else None,
            "shadow_diff": decision_diff,
        }
    if tool_call is not None:
        assistant_metadata["tool_call"] = _tool_call_trace(tool_call)
    if web_search_call is not None:
        assistant_metadata["tool_call"] = _tool_call_trace(web_search_call)
        assistant_metadata["web_search"] = web_search_call.get("record")
        assistant_metadata["web_reference_images"] = {
            "schema_version": "web_reference_images_v1",
            "items": (web_search_call.get("record") or {}).get("reference_images") or [],
        }
        assistant_metadata["citation_policy"] = {
            "schema_version": "web_search_citation_v1",
            "required": web_search_call.get("status") == "success",
            "allowed_urls": [item.get("url") for item in (web_search_call.get("result") or {}).get("items") or []],
        }
    if shoot_context is not None:
        # 同一份结构化结果供客户端卡片直接渲染，避免从自然语言回复反向解析数据。
        assistant_metadata["shoot_context"] = shoot_context
    if retrieval_payload:
        references = retrieval_payload.get("references") or {}
        assistant_metadata = {
            **assistant_metadata,
            "references": references,
            "retrieval": {
                "context_schema_version": retrieval_payload.get("context_schema_version"),
                "criteria": retrieval_payload.get("criteria") or {},
                "diagnostics": retrieval_payload.get("diagnostics") or {},
            },
            "citation_policy": {
                "schema_version": "resource_citation_v1",
                "required": True,
                "allowed_resource_ids": {
                    key: [
                        item.get("id") or item.get("user_id") or item.get("package_id")
                        for item in values or []
                    ]
                    for key, values in references.items()
                },
            },
        }
        # 落成本轮的 search_context，供下一轮“换一个”继承条件并排除已推荐资源。
        search_context = build_search_context(
            retrieval=retrieval_payload,
            intent=intent,
            previous=previous_search_context,
            refinement=search_refinement,
            # 工具路径下用工具自己的检索文本，别把“换一个”这类原话留给下一轮。
            query_text=None if tool_call is not None else content,
            task_id=(working_memory or {}).get("task_id"),
            task_type=(working_memory or {}).get("task_type"),
            revision=(working_memory or {}).get("revision"),
        )
        if search_context:
            assistant_metadata["search_context"] = search_context
            # 重复推荐率（阶段C §4-C.3）：本轮推荐里有多少是上一轮已经给过的。
            # 只记 ID 与计数，不重复整份资源内容。
            assistant_metadata["recommendation_overlap"] = _recommendation_overlap(
                previous=previous_search_context,
                current=search_context,
                refinement=search_refinement is not None,
            )

    assistant_metadata = normalize_agent_metadata(assistant_metadata)
    active_task_id = (working_memory or {}).get("task_id") or get_active_task_id(user_id, conversation.id)
    assistant_metadata["context_provenance"] = {
        "active_task_id": active_task_id,
        "active_task_type": (working_memory or {}).get("task_type"),
        "workspace_source": workspace_source,
        "workspace_revision": (working_memory or {}).get("revision"),
        "previous_search_task_id": previous_search_task_id,
        "referenced_episode_ids": [
            item.get("episode_id") for item in referenced_task_episodes
            if item.get("episode_id")
        ],
        "long_term_memory_ids": [],
        "task_transition": task_transition,
        "stale_workspace_discarded": stale_workspace_discarded,
        "task_type_mismatch": workspace_task_type_mismatch,
        "cross_task_slots_blocked": [],
        "context_sources": [
            "current_message",
            *( ["active_task"] if working_memory else [] ),
            *( ["referenced_task_episodes"] if task_episode_prompt else [] ),
            *( ["active_user_memories"] if long_term_memory_prompt else [] ),
            "recent_dialogue",
        ],
    }
    # Persist the mutable task independently from assistant message metadata. The old
    # metadata snapshot remains useful for audit/replay, but is no longer authoritative.
    task_state = assistant_metadata.get("task_state")
    if not isinstance(task_state, dict) and embedded_form_result:
        task_state = (embedded_form_result.get("metadata") or {}).get("task_state")
    if isinstance(task_state, dict) and task_state.get("task_type") in {
        "create_project", "publish_package", "publish_work", "project_application", "create_booking",
    }:
        task_type = task_state["task_type"]
        slots = task_state.get("slots") or {}
        task_fields = slots
        if task_type == "create_booking":
            selected_package = slots.get("selected_package") or {}
            pending_input = ((task_state.get("pending_action") or {}).get("input") or {})
            target_sources = (slots, selected_package, pending_input)
            target = {}
            for key in ("photographer_id", "package_id"):
                for source in target_sources:
                    value = source.get(key) if isinstance(source, dict) else None
                    if key == "package_id" and isinstance(source, dict) and value in (None, ""):
                        value = source.get("id")
                    if value not in (None, ""):
                        target[key] = value
                        break
            task_fields = {
                "appointment_date": slots.get("date") or slots.get("appointment_date"),
                "appointment_time": slots.get("appointment_time"),
                "notes": slots.get("notes"),
            }
            if not task_fields["appointment_time"] and slots.get("date") and slots.get("time"):
                try:
                    task_fields["appointment_time"] = build_booking_appointment_datetime(
                        str(slots["date"]), str(slots["time"]),
                    ).isoformat()
                except ValueError:
                    pass
            task_fields = {key: value for key, value in task_fields.items() if value not in (None, "")}
        else:
            target = {}
        target = {
            **target,
            **{
                key: slots[key]
                for key in ("project_id", "package_id", "photographer_id", "work_id")
                if slots.get(key) is not None
            },
        }
        if normalized_page_context:
            resource_id = normalized_page_context.get("resource_id")
            if resource_id and normalized_page_context.get("resource_type") == "project":
                target.setdefault("project_id", resource_id)
        status_map = {
            "awaiting_details": "collecting", "awaiting_reference_images": "collecting",
            "awaiting_confirmation": "collecting", "awaiting_package": "collecting",
            "awaiting_date": "collecting", "awaiting_time": "collecting", "editing": "editing_page",
            "completed": "completed", "cancelled": "cancelled",
        }
        task = sync_task_snapshot(
            db,
            user_id=user_id,
            conversation_id=conversation.id,
            task_type=task_type,
            fields=task_fields,
            target=target,
            media_assets=slots.get("media_assets") or slots.get("media_refs") or [],
            status=status_map.get(task_state.get("status"), "collecting"),
            source_message_id=user_message.id,
        )
        assistant_metadata["active_task"] = serialize_task(task) if task.status in {"collecting", "editing_page", "submitting"} else None
        # Compatibility snapshot for old clients and audit replay. The mobile chat
        # intentionally ignores this key and renders only active_task.
        if "agent_form_card" not in assistant_metadata:
            assistant_metadata["agent_form_card"] = card_from_task_state(task_state, conversation.id)

    assistant_message = AIMessage(
        conversation_id=conversation.id,
        role="assistant",
        content=result["content"],
        message_metadata=assistant_metadata or None,
    )
    db.add(assistant_message)
    conversation.updated_at = _now()
    db.commit()
    db.refresh(assistant_message)
    db.refresh(user_message)

    # Keep provider history bounded after a task has ended, while retaining all
    # original messages for audit and replay.
    try:
        compress_completed_task_history(db, conversation=conversation)
        db.commit()
    except Exception:
        db.rollback()

    try:
        from backend.app.services.ai_trace_service import record_agent_trace
        record_agent_trace(
            db,
            user_id=user_id,
            conversation_id=conversation.id,
            user_message_id=user_message.id,
            assistant_message_id=assistant_message.id,
            intent=intent.as_dict(),
            metadata=assistant_metadata,
            total_latency_ms=round((perf_counter() - trace_started_at) * 1000),
        )
    except Exception:
        db.rollback()

    return user_message, assistant_message
