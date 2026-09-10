"""
LLM 意图分类服务。

提供混和分类流程：始终计算规则候选作为回退基线，可选调用 LLM 模型
以提高语义分类精度，最终通过后端策略表生成安全的 AgentIntent。
"""

from __future__ import annotations

import json
import re
from time import perf_counter
from typing import Any

from backend.app.core.config import settings
from backend.app.services.ai_agent_contracts import (
    INTENT_CLASSIFICATION_TRACE_VERSION,
    LLM_INTENT_CANDIDATE_SCHEMA_VERSION,
    AgentIntent,
    IntentClassificationResult,
    LLMIntentCandidate,
    apply_intent_policy,
)
from backend.app.services.ai_intent_prompt import (
    INTENT_CLASSIFICATION_SYSTEM_PROMPT,
    INTENT_PROMPT_VERSION,
)
from backend.app.services.ai_orchestrator_service import recognize_intent_by_rules
from backend.app.services.ai_provider import AIProvider, get_text_provider
from backend.app.services.ai_retrieval_service import RESOURCE_TYPE_TERMS


def _clean_json_output(raw: str) -> str:
    """清理模型输出中的 Markdown fence 和其他非 JSON 包装。"""
    cleaned = raw.strip()
    # 移除 ```json ... ``` 或 ``` ... ```
    if cleaned.startswith("```"):
        # 找到第一个换行后的内容和最后一个 ```
        first_newline = cleaned.find("\n")
        if first_newline != -1:
            cleaned = cleaned[first_newline + 1 :]
        # 移除末尾的 ```
        last_fence = cleaned.rfind("```")
        if last_fence != -1:
            cleaned = cleaned[:last_fence]
    return cleaned.strip()


def _build_classification_input(
    content: str | None,
    attachments: list[dict] | None = None,
    *,
    active_task: dict | None = None,
    page_context: dict | None = None,
) -> str:
    """构建分类器输入 JSON。"""
    has_image = any((item or {}).get("type") == "image" for item in attachments or [])
    attachment_count = len(attachments or [])
    page_summary = {}
    if isinstance(page_context, dict) and page_context.get("resource_type"):
        page_summary = {
            "resource_type": page_context.get("resource_type"),
            "has_current_resource": bool(page_context.get("resource_id")),
            "title": str(page_context.get("title") or "")[:120],
        }
    return json.dumps(
        {
            "content": (content or "").strip(),
            "has_image": has_image,
            "attachment_count": attachment_count,
            "active_task": active_task or {},
            "page_context": page_summary,
        },
        ensure_ascii=False,
    )


def _merge_slots(
    rule_slots: dict[str, Any],
    model_slots: dict[str, Any],
) -> dict[str, Any]:
    """
    合并规则和模型的槽位输出。

    规则优先（确定性）字段：budget_max, budget_min, date, time, people_count,
    duration_minutes, image_count, limit。

    模型优先（语义）字段：photographer_name, package_name, styles,
    description, deliverables, package_description, city, location_text,
    requires_makeup, package_includes, title。
    """
    merged = dict(rule_slots)

    model_priority = {
        "photographer_name",
        "package_name",
        "styles",
        "description",
        "deliverables",
        "package_description",
        "city",
        "location_text",
        "requires_makeup",
        "package_includes",
        "title",
        "resource_types",
    }

    for key in model_priority:
        model_value = model_slots.get(key)
        if model_value not in (None, "", [], {}):
            # 清理整句命令被抽成名称的情况
            if key in {"photographer_name", "package_name", "title", "location_text", "city"}:
                cleaned = _clean_semantic_name(model_value)
                if cleaned:
                    merged[key] = cleaned
            else:
                merged[key] = model_value

    # 规则补充模型缺失的确定性字段
    rule_fallback = {
        "budget_max",
        "budget_min",
        "date",
        "time",
        "people_count",
        "duration_minutes",
        "image_count",
        "limit",
    }
    for key in rule_fallback:
        if key not in merged or merged[key] in (None, "", []):
            rule_value = rule_slots.get(key)
            if rule_value not in (None, "", []):
                merged[key] = rule_value

    return merged


def _explicit_rule_resource_types(content: str | None, rule_intent: AgentIntent) -> list[str]:
    """Return the resource target explicitly named in the current message.

    Generic rule fallbacks such as “帮我找找” may default to photographers, so only a
    literal resource term in the current message is strong enough to constrain hybrid
    classification. This keeps prior active-task context from rewriting “方案” as “企划”.
    """
    if rule_intent.intent != "resource_search":
        return []
    resource_types = list(rule_intent.slots.get("resource_types") or [])
    if len(resource_types) != 1:
        return []
    resource_type = resource_types[0]
    terms = RESOURCE_TYPE_TERMS.get(resource_type) or ()
    text = (content or "").strip()
    return resource_types if any(term in text for term in terms) else []


def _reconcile_hybrid_intent(
    content: str | None,
    rule_intent: AgentIntent,
    model_intent: AgentIntent,
    *,
    has_image: bool,
) -> AgentIntent:
    """Fuse candidates while preserving explicit facts from the current message."""
    # Advice about the current project must stay chat even if the model overweights
    # the words “应邀” or “企划”. The rule candidate contains the deterministic
    # consultation guard and is the safer result for this handoff boundary.
    if (
        (model_intent.intent == "project_application" and rule_intent.intent == "chat")
        or (rule_intent.intent == "project_application" and model_intent.intent == "chat")
    ):
        return rule_intent

    # A no-image inspiration request with an explicit style is the fixed
    # search-then-inspire workflow. The model prompt carries no
    # compound_workflow label until v6, so the model reports only the leading
    # clause of the compound instruction (resource_search, chat, or the legacy
    # create_inspiration_flow). The deterministic search-then-inspire rule is
    # high precision (explicit creation phrasing plus explicit search/style
    # language) and owns this fixed chain; a single-step model reading must
    # not downgrade it, and an empty attachment list is never sent to the
    # image reference-only handler.
    if (
        not has_image
        and (
            (
                rule_intent.intent == "compound_workflow"
                and model_intent.intent != "compound_workflow"
            )
            or (
                model_intent.intent == "create_inspiration_flow"
                and (model_intent.slots.get("style") or model_intent.slots.get("styles"))
            )
        )
    ):
        slots = dict(rule_intent.slots or {})
        slots.update({key: value for key, value in (model_intent.slots or {}).items() if value not in (None, "", [])})
        policy = apply_intent_policy("compound_workflow", slots, has_image=False)
        return AgentIntent(
            intent="compound_workflow",
            sub_intents=policy["sub_intents"],
            slots=slots,
            missing_slots=policy["missing_slots"],
            requires_confirmation=policy["requires_confirmation"],
            route=policy["route"],
            confidence=max(rule_intent.confidence, model_intent.confidence),
            parser="rules",
        )

    explicit_types = _explicit_rule_resource_types(content, rule_intent)
    if not explicit_types:
        return model_intent

    slots = dict(model_intent.slots or {})
    slots["resource_types"] = explicit_types
    # Deterministic current-message extraction outranks semantic guesses for these fields.
    for key in ("city", "budget_min", "budget_max", "date", "time", "limit"):
        value = (rule_intent.slots or {}).get(key)
        if value not in (None, "", [], {}):
            slots[key] = value
    policy = apply_intent_policy("resource_search", slots, has_image=has_image)
    return AgentIntent(
        intent="resource_search",
        sub_intents=policy["sub_intents"],
        slots=slots,
        missing_slots=policy["missing_slots"],
        requires_confirmation=policy["requires_confirmation"],
        route=policy["route"],
        confidence=max(rule_intent.confidence, model_intent.confidence),
        parser="model",
    )


def _clean_semantic_name(value: Any) -> str | None:
    """清理语义名称为合理值。"""
    if not isinstance(value, str):
        return None
    text = value.strip()
    # 过滤掉包含句子结构或命令的"名称"
    if not text or len(text) < 2:
        return None
    if any(term in text for term in ("帮我", "请", "想", "搜索", "找", "推荐", "关注", "发布", "预约", "取消")):
        return None
    if len(text) > 40:
        return None
    return text


def _build_agent_intent_from_model(
    model_candidate: LLMIntentCandidate,
    rule_intent: AgentIntent,
    has_image: bool,
) -> AgentIntent:
    """将模型候选 + 后端策略表生成完整的 AgentIntent。"""
    model_slots = model_candidate.slots.model_dump(exclude_none=True)

    # 统一 style → styles
    if "style" in model_slots and "styles" not in model_slots:
        model_slots["styles"] = model_slots.pop("style")
    if isinstance(model_slots.get("styles"), str):
        model_slots["styles"] = [model_slots["styles"]]

    merged_slots = _merge_slots(rule_intent.slots, model_slots)
    policy = apply_intent_policy(model_candidate.intent, merged_slots, has_image=has_image)

    return AgentIntent(
        intent=model_candidate.intent,
        sub_intents=policy["sub_intents"],
        slots=merged_slots,
        missing_slots=policy["missing_slots"],
        requires_confirmation=policy["requires_confirmation"],
        route=policy["route"],
        confidence=model_candidate.confidence,
        parser="model",
    )


def _parse_llm_response(
    raw_content: str | None,
    rule_intent: AgentIntent,
    has_image: bool,
    min_confidence: float,
) -> tuple[AgentIntent | None, dict[str, Any] | None, str | None]:
    """
    解析 LLM 响应并尝试构建 AgentIntent。
    返回 (intent, model_candidate_dict, error_reason)。
    """
    if not raw_content or not raw_content.strip():
        return None, None, "empty_response"

    cleaned = _clean_json_output(raw_content)
    if not cleaned:
        return None, None, "empty_after_clean"

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        return None, None, "invalid_json"

    if not isinstance(parsed, dict):
        return None, None, "not_a_dict"

    try:
        model_candidate = LLMIntentCandidate.model_validate(parsed)
    except Exception as exc:
        return None, None, f"schema_validation_error: {type(exc).__name__}"

    if model_candidate.confidence < min_confidence:
        return None, model_candidate.model_dump(mode="json"), f"low_confidence: {model_candidate.confidence}"

    try:
        intent = _build_agent_intent_from_model(model_candidate, rule_intent, has_image)
    except Exception as exc:
        return None, model_candidate.model_dump(mode="json"), f"policy_error: {type(exc).__name__}"

    return intent, model_candidate.model_dump(mode="json"), None


async def classify_intent(
    content: str | None,
    attachments: list[dict] | None = None,
    *,
    active_task: dict | None = None,
    page_context: dict | None = None,
    provider: AIProvider | None = None,
    mode: str | None = None,
) -> IntentClassificationResult:
    """
    异步意图分类主入口。

    处理顺序：
    1. 始终计算 rule candidate（作为回退和精确槽位来源）。
    2. 根据 mode 决定是否调用 LLM。
    3. 校验 LLM 输出，通过后端策略表生成完整 AgentIntent。
    4. 低置信度/非法输出回退规则结果。
    """
    mode = (mode or settings.AI_INTENT_CLASSIFIER_MODE).lower()
    min_confidence = settings.AI_INTENT_CLASSIFIER_MIN_CONFIDENCE
    has_image = any((item or {}).get("type") == "image" for item in attachments or [])

    # 1. 始终计算规则候选
    rule_intent = recognize_intent_by_rules(content, attachments)
    rule_candidate = rule_intent.as_dict()

    # 2. rules 模式直接返回
    if mode == "rules":
        return IntentClassificationResult(
            intent=rule_intent,
            parser="rules",
            chosen_parser="rules",
            rule_candidate=rule_candidate,
            rule_intent=rule_intent.intent,
        )

    # 3. 调用 LLM
    provider = provider or get_text_provider()
    classification_input = _build_classification_input(
        content,
        attachments,
        active_task=active_task,
        page_context=page_context,
    )

    model_latency_ms = 0
    model_raw: str | None = None
    model_provider_name: str | None = None
    model_name_str: str | None = None

    try:
        start = perf_counter()
        result = await provider.chat(
            [
                {"role": "system", "content": INTENT_CLASSIFICATION_SYSTEM_PROMPT},
                {"role": "user", "content": classification_input},
            ],
            temperature=0.0,
            response_format={"type": "json_object"} if settings.AI_INTENT_CLASSIFIER_JSON_MODE else None,
        )
        model_latency_ms = round((perf_counter() - start) * 1000)
        model_raw = (result.get("content") or "").strip()
        model_meta = result.get("metadata", {}).get("model", {})
        model_provider_name = model_meta.get("provider")
        model_name_str = model_meta.get("model")
    except Exception as exc:
        # Provider 异常，回退规则
        return IntentClassificationResult(
            intent=rule_intent,
            parser="fallback",
            fallback_reason=f"provider_error: {type(exc).__name__}",
            chosen_parser="rules",
            rule_candidate=rule_candidate,
            model_latency_ms=model_latency_ms,
            model_provider=model_provider_name,
            model_name=model_name_str,
            prompt_version=INTENT_PROMPT_VERSION,
        )

    # 4. 解析 LLM 响应
    model_intent, model_candidate, fallback_reason = _parse_llm_response(
        model_raw,
        rule_intent,
        has_image,
        min_confidence,
    )

    rule_intent_name = rule_intent.intent
    model_intent_name = model_intent.intent if model_intent else None

    if model_intent is None:
        # 回退规则
        return IntentClassificationResult(
            intent=rule_intent,
            parser="fallback",
            fallback_reason=fallback_reason or "model_parse_failed",
            chosen_parser="rules",
            rule_candidate=rule_candidate,
            model_candidate=model_candidate,
            model_latency_ms=model_latency_ms,
            model_confidence=model_candidate.get("confidence") if model_candidate else None,
            model_provider=model_provider_name,
            model_name=model_name_str,
            prompt_version=INTENT_PROMPT_VERSION,
            agreement=rule_intent_name == model_intent_name,
        )

    # 5. 根据 mode 决定使用哪个结果
    if mode == "hybrid":
        chosen = _reconcile_hybrid_intent(
            content,
            rule_intent,
            model_intent,
            has_image=has_image,
        )
        chosen_parser = "rules" if chosen is rule_intent else "model"
        fallback_reason = None
    else:
        # shadow 模式：记录但使用规则
        chosen = rule_intent
        chosen_parser = "rules"
        fallback_reason = "shadow_mode"

    return IntentClassificationResult(
        intent=chosen,
        parser=chosen_parser,
        fallback_reason=fallback_reason,
        chosen_parser=chosen_parser,
        rule_candidate=rule_candidate,
        model_candidate=model_candidate,
        model_latency_ms=model_latency_ms,
        model_confidence=model_candidate.get("confidence") if model_candidate else None,
        model_provider=model_provider_name,
        model_name=model_name_str,
        prompt_version=INTENT_PROMPT_VERSION,
        agreement=rule_intent_name == model_intent_name,
    )
