"""统一 Agent 决策服务（阶段B §4.2、§4.3、§4.6）。

调用链：ai_service 收集状态 → 本模块让 LLM 输出一个决策 → ai_tool_policy_service 鉴权 →
ai_search_tool_service 执行工具 → ai_service 把真实结果交给最终 LLM 组织话术。

模型只决定"下一步做什么"，所有事实、ID 和权限判断都在后端；模型输出非法、置信度不足、
工具未注册或没有权限时，一律回退到既有的意图路由，并记下 fallback_reason（§4.5、§5.5）。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from time import perf_counter
from typing import Any, Literal

from backend.app.core.config import settings
from backend.app.services.availability_service import platform_today
from backend.app.services.ai_agent_contracts import AgentIntent
from backend.app.services.ai_agent_decision_contracts import (
    DECISION_SCHEMA_VERSION,
    DECISION_TRACE_VERSION,
    AgentDecision,
    decision_condition_slots,
    sanitize_arguments,
)
from backend.app.services.ai_agent_decision_prompt import (
    DECISION_PROMPT_VERSION,
    build_decision_system_prompt,
)
from backend.app.services.ai_provider import AIProvider, get_text_provider
from backend.app.services.ai_search_context_service import slot_styles
from backend.app.services.ai_orchestrator_service import recognize_intent_by_rules
from backend.app.services.ai_search_tool_service import (
    is_search_tool,
    search_tool_for_resource_types,
)
from backend.app.services.ai_tool_policy_service import (
    ToolAuthorization,
    authorize_tool_call,
    build_tool_catalog,
    resolve_tool_name,
)


# 原始输出只留可诊断的长度：审计要能看到模型说了什么，但不必把整段文本长期留在库里。
MAX_RAW_OUTPUT_LENGTH = 600

# 只在这两个意图上接管路由：发布/预约/取消等多轮表单流程仍由既有状态机负责（§5.2）。
# rule_query 是单步只读检索，同样交给决策层（模型选 search_platform_rules 或 chat）。
DECISION_ELIGIBLE_INTENTS = frozenset({"chat", "resource_search", "rule_query"})

_INTENT_TO_TOOL = {
    "booking_flow": "create_booking",
    "project_flow": "create_project",
    "package_publish_flow": "publish_package",
    "follow_photographer": "follow_photographer",
    "rule_query": "search_platform_rules",
}

_COMPARED_SLOT_FIELDS = ("city", "budget_min", "budget_max", "limit", "requires_makeup")
_EXPLICIT_WEB_SEARCH_TERMS = (
    "联网搜索", "联网查", "上网搜索", "上网查", "网页搜索", "网上搜索",
    "搜索一下新闻", "查最新新闻", "查最新资料", "最新资讯", "实时资讯",
)

_WEATHER_TERMS = ("天气", "气温", "降雨", "下雨", "日照", "日出", "日落", "黄金时刻", "拍摄环境")
_CHINESE_DIGITS = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
_DATE_TOKEN_PATTERN = re.compile(
    r"(?:(?P<year>\d{4})年)?(?P<month>\d{1,2}|[一二两三四五六七八九十]+)月"
    r"(?P<day>\d{1,2}|[一二两三四五六七八九十]+)(?:日|号)"
)


def _calendar_number(value: str) -> int:
    if value.isdigit():
        return int(value)
    if value == "十":
        return 10
    if "十" in value:
        left, right = value.split("十", 1)
        tens = _CHINESE_DIGITS.get(left, 1) if left else 1
        ones = _CHINESE_DIGITS.get(right, 0) if right else 0
        return tens * 10 + ones
    return _CHINESE_DIGITS.get(value, 0)


def infer_shoot_context_decision(content: str | None, *, today: date | None = None) -> AgentDecision | None:
    """Resolve common explicit weather queries without letting history rewrite place/date."""
    text = (content or "").strip()
    if not text or not any(term in text for term in _WEATHER_TERMS):
        return None
    match = _DATE_TOKEN_PATTERN.search(text)
    if match is None:
        return None
    current = today or platform_today()
    try:
        shoot_date = date(
            int(match.group("year") or current.year),
            _calendar_number(match.group("month")),
            _calendar_number(match.group("day")),
        )
    except ValueError:
        return None

    weather_index = min(
        (text.find(term, match.end()) for term in _WEATHER_TERMS if text.find(term, match.end()) >= 0),
        default=len(text),
    )
    candidates = (text[match.end():weather_index], text[:match.start()])
    location = None
    for candidate in candidates:
        cleaned = re.sub(r"^(?:请问|请帮我|帮我|查询|查查|查一下|看一下|看看|想知道|在)", "", candidate.strip())
        cleaned = cleaned.strip(" ，,。！？?的在于")
        if 2 <= len(cleaned) <= 120:
            location = cleaned
            break
    if not location:
        return None
    return AgentDecision(
        mode="tool_call",
        tool="get_shoot_context",
        arguments={"location_text": location, "shoot_date": shoot_date.isoformat()},
        confidence=0.99,
        reason="当前消息包含明确地点和月日，年份按平台当前年份补全",
    )


def infer_explicit_search_decision(content: str | None) -> AgentDecision | None:
    """Route explicit current-message resource searches without conversation history.

    The model still handles ambiguous/refinement turns, but a literal target such as
    “方案” or “企划” must not be replaced by the previous search_context.
    """
    text = (content or "").strip()
    if not text:
        return None
    intent = recognize_intent_by_rules(text)
    if intent.intent != "resource_search":
        return None
    resource_types = list(intent.slots.get("resource_types") or [])
    tool = search_tool_for_resource_types(resource_types)
    if not tool or len(resource_types) != 1:
        return None
    resource_type = resource_types[0]
    from backend.app.services.ai_retrieval_service import RESOURCE_TYPE_TERMS

    if not any(term in text for term in RESOURCE_TYPE_TERMS.get(resource_type, ())):
        return None

    slots = intent.slots or {}
    arguments: dict[str, Any] = {"limit": slots.get("limit") or 3}
    if slots.get("city"):
        arguments["city"] = slots["city"]
    styles = slot_styles(slots)
    if styles:
        arguments["styles"] = styles
    for key in ("budget_min", "budget_max", "requires_makeup", "photographer_name"):
        value = slots.get(key)
        if value not in (None, "", [], {}):
            arguments[key] = value
    return AgentDecision(
        mode="tool_call",
        tool=tool,
        arguments=arguments,
        confidence=0.99,
        reason="当前消息明确指定了资源类型，忽略历史搜索类型",
    )


def is_explicit_web_search_request(content: str | None) -> bool:
    """判断用户是否明确要求联网搜索（与决策层的触发词保持同一来源）。

    显式联网搜索必须优先于工作区里的资源引用解析：active 任务里的序数引用
    （“第一个”类）走的是 ai_service 的确定性分支，根本不进决策层，所以调用方
    要在进入该分支之前先调这个谓词排除掉联网搜索请求。
    """
    text = " ".join((content or "").strip().split())
    return bool(text) and any(term in text for term in _EXPLICIT_WEB_SEARCH_TERMS)


def infer_explicit_web_search_decision(content: str | None) -> AgentDecision | None:
    """Deterministically honor an explicit request for public web search.

    This must run before the generic resource-search fallback, whose historical
    default is ``search_photographers``. Provider availability is checked later
    by the tool executor so a disabled provider yields a truthful failure.
    """
    if not is_explicit_web_search_request(content):
        return None
    text = " ".join((content or "").strip().split())
    query = text
    for term in _EXPLICIT_WEB_SEARCH_TERMS:
        query = query.replace(term, "")
    query = " ".join(query.replace("。", " ").split()).strip(" ：:，,") or text
    return AgentDecision(
        mode="tool_call",
        tool="search_web",
        arguments={"query": query[:300], "limit": 5, "language": "zh-CN"},
        confidence=1.0,
        reason="用户明确要求联网搜索，优先于平台内部资源检索",
    )


def _reconcile_explicit_search_decision(
    content: str | None,
    decision: AgentDecision,
) -> AgentDecision:
    """Correct only decisions contradicted by an explicit current-message target."""
    explicit = infer_explicit_search_decision(content)
    if explicit is None or decision.mode == "confirm":
        return decision

    should_override = (
        decision.mode == "tool_call"
        and is_search_tool(decision.tool)
        and decision.tool != explicit.tool
    )
    if not should_override:
        return decision

    # Preserve semantic conditions the rule extractor may not understand, while current
    # message facts and the resource/tool choice remain authoritative.
    common_fields = {
        "city", "styles", "budget_min", "budget_max", "limit", "query_text",
        "requires_makeup", "photographer_name",
    }
    arguments = {
        key: value
        for key, value in (decision.arguments or {}).items()
        if key in common_fields and value not in (None, "", [], {})
    }
    arguments.update(explicit.arguments)
    return explicit.model_copy(update={
        "arguments": arguments,
        "confidence": max(explicit.confidence, decision.confidence),
    })


@dataclass(frozen=True)
class AgentDecisionOutcome:
    """一次决策调用的结果与诊断。"""

    decision: AgentDecision | None
    parser: Literal["model", "deterministic", "fallback"] = "fallback"
    fallback_reason: str | None = None
    raw_output: str | None = None
    latency_ms: int = 0
    provider: str | None = None
    model: str | None = None
    dropped_fields: tuple[str, ...] = ()

    def as_trace(self) -> dict[str, Any]:
        """输出可审计的决策追踪记录。"""
        decision = self.decision
        return {
            "schema_version": DECISION_TRACE_VERSION,
            "protocol_version": DECISION_SCHEMA_VERSION,
            "prompt_version": DECISION_PROMPT_VERSION,
            "parser": self.parser,
            "fallback_reason": self.fallback_reason,
            "mode": decision.mode if decision else None,
            "tool": decision.tool if decision else None,
            "arguments": dict(decision.arguments) if decision else {},
            "confidence": decision.confidence if decision else None,
            "reason": decision.reason if decision else None,
            "question": decision.question if decision else None,
            "dropped_fields": list(self.dropped_fields),
            "latency_ms": self.latency_ms,
            "provider": self.provider,
            "model": self.model,
            "raw_output": self.raw_output,
        }


@dataclass(frozen=True)
class DecisionPlan:
    """决策落到本轮编排上的执行计划。

    action="legacy" 表示这一轮不由决策层接管（写操作、鉴权失败、模型不可用等），
    ai_service 继续按既有意图路由执行，两者不会同时生效。
    """

    action: Literal["search", "read_tool", "chat", "clarify", "legacy"]
    applied: bool
    tool: str | None = None
    arguments: dict[str, Any] = field(default_factory=dict)
    question: str | None = None
    authorization: ToolAuthorization | None = None
    not_applied_reason: str | None = None
    dropped_fields: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        """将执行计划序列化为字典。"""
        return {
            "action": self.action,
            "applied": self.applied,
            "tool": self.tool,
            "arguments": self.arguments,
            "question": self.question,
            "not_applied_reason": self.not_applied_reason,
            "authorization": self.authorization.as_dict() if self.authorization else None,
            "dropped_fields": list(self.dropped_fields),
        }


def _clean_json_output(raw: str) -> str:
    """去掉模型可能加上的 Markdown fence。"""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        first_newline = cleaned.find("\n")
        if first_newline != -1:
            cleaned = cleaned[first_newline + 1 :]
        last_fence = cleaned.rfind("```")
        if last_fence != -1:
            cleaned = cleaned[:last_fence]
    return cleaned.strip()


def build_decision_input(
    *,
    content: str | None,
    has_image: bool = False,
    user_role: str | None = None,
    history: list[dict[str, Any]] | None = None,
    page_context: dict[str, Any] | None = None,
    search_context: dict[str, Any] | None = None,
) -> str:
    """决策器输入：当前消息 + 有限历史 + 页面上下文 + 进行中的搜索状态（§4.2）。

    只传结论性的少量状态，不传图片内容、不传资源 ID 列表：
    模型不需要知道平台 ID，排除逻辑由后端完成（§5.1、§5.5）。
    """
    return json.dumps(
        {
            "content": (content or "").strip(),
            "current_date": platform_today().isoformat(),
            "timezone": settings.PLATFORM_TIMEZONE,
            "has_image": bool(has_image),
            "user_role": user_role or "unknown",
            "history": history or [],
            "page_context": page_context or {},
            "search_context": search_context or {},
        },
        ensure_ascii=False,
    )


async def decide_agent_action(
    *,
    content: str | None,
    has_image: bool = False,
    user_role: str | None = None,
    history: list[dict[str, Any]] | None = None,
    page_context: dict[str, Any] | None = None,
    search_context: dict[str, Any] | None = None,
    allow_writes: bool = True,
    provider: AIProvider | None = None,
    min_confidence: float | None = None,
) -> AgentDecisionOutcome:
    """让模型给出一次决策；任何异常都收敛成 fallback，不抛给调用方。"""
    if not (content or "").strip():
        return AgentDecisionOutcome(decision=None, fallback_reason="empty_content")

    deterministic_weather = infer_shoot_context_decision(content) if provider is None else None
    if deterministic_weather is not None:
        return AgentDecisionOutcome(decision=deterministic_weather, parser="deterministic")
    explicit_web = infer_explicit_web_search_decision(content)
    if explicit_web is not None:
        return AgentDecisionOutcome(decision=explicit_web, parser="deterministic")

    threshold = (
        settings.AI_AGENT_DECISION_MIN_CONFIDENCE if min_confidence is None else min_confidence
    )
    catalog = build_tool_catalog(
        user_role=user_role,
        allow_writes=allow_writes,
        include_read_tools=True,
    )
    system_prompt = build_decision_system_prompt(catalog)
    user_prompt = build_decision_input(
        content=content,
        has_image=has_image,
        user_role=user_role,
        history=history,
        page_context=page_context,
        search_context=search_context,
    )

    provider = provider or get_text_provider()
    latency_ms = 0
    provider_name: str | None = None
    model_name: str | None = None
    try:
        started = perf_counter()
        result = await provider.chat(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
            response_format=(
                {"type": "json_object"} if settings.AI_AGENT_DECISION_JSON_MODE else None
            ),
        )
        latency_ms = round((perf_counter() - started) * 1000)
        raw = (result.get("content") or "").strip()
        model_meta = (result.get("metadata") or {}).get("model") or {}
        provider_name = model_meta.get("provider")
        model_name = model_meta.get("model")
    except Exception as exc:
        return AgentDecisionOutcome(
            decision=None,
            fallback_reason=f"provider_error: {type(exc).__name__}",
            latency_ms=latency_ms,
        )

    truncated = raw[:MAX_RAW_OUTPUT_LENGTH] or None
    base = {
        "raw_output": truncated,
        "latency_ms": latency_ms,
        "provider": provider_name,
        "model": model_name,
    }
    if not raw:
        return AgentDecisionOutcome(decision=None, fallback_reason="empty_response", **base)

    cleaned = _clean_json_output(raw)
    if not cleaned:
        return AgentDecisionOutcome(decision=None, fallback_reason="empty_after_clean", **base)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        return AgentDecisionOutcome(decision=None, fallback_reason="invalid_json", **base)
    if not isinstance(parsed, dict):
        return AgentDecisionOutcome(decision=None, fallback_reason="not_a_dict", **base)

    # 后端独占参数在进入契约校验之前剥离：模型输出它不算非法，但一律不生效。
    arguments, dropped = sanitize_arguments(parsed.get("arguments"))
    if "arguments" in parsed:
        parsed["arguments"] = arguments
    try:
        decision = AgentDecision.model_validate(parsed)
    except Exception as exc:
        return AgentDecisionOutcome(
            decision=None,
            fallback_reason=f"schema_validation_error: {type(exc).__name__}",
            dropped_fields=tuple(dropped),
            **base,
        )

    if decision.confidence < threshold:
        return AgentDecisionOutcome(
            decision=decision,
            parser="fallback",
            fallback_reason=f"low_confidence: {decision.confidence}",
            dropped_fields=tuple(dropped),
            **base,
        )

    resolved_tool = resolve_tool_name(decision.tool) if decision.tool else None
    if resolved_tool and resolved_tool != decision.tool:
        decision = decision.model_copy(update={"tool": resolved_tool})

    decision = _reconcile_explicit_search_decision(content, decision)
    resolved_tool = resolve_tool_name(decision.tool) if decision.tool else None
    if resolved_tool and resolved_tool not in {item["name"] for item in catalog}:
        return AgentDecisionOutcome(
            decision=decision,
            parser="fallback",
            fallback_reason=f"tool_not_available: {resolved_tool}",
            dropped_fields=tuple(dropped),
            **base,
        )

    return AgentDecisionOutcome(
        decision=decision,
        parser="model",
        dropped_fields=tuple(dropped),
        **base,
    )


def resolve_decision_plan(
    outcome: AgentDecisionOutcome | None,
    *,
    legacy_intent_name: str,
    user_role: str | None = None,
    allow_writes: bool = False,
    exclude_resource_ids: list[str] | tuple[str, ...] | None = None,
    active_task_types: tuple[str, ...] = (),
) -> DecisionPlan:
    """把决策翻译成本轮的执行计划，并在执行前完成策略检查（§4.4）。

    阶段B 只让决策层接管"聊天 + 读检索"：写操作（预约、发布、关注）继续走既有的
    确认 + 事务 + 幂等键流程，所以这里对写工具一律返回 legacy，由 ai_service 按老路径执行。
    """
    if outcome is None or outcome.decision is None or outcome.parser not in {"model", "deterministic"}:
        return DecisionPlan(
            action="legacy",
            applied=False,
            not_applied_reason=(outcome.fallback_reason if outcome else "no_decision") or "no_decision",
        )
    if legacy_intent_name not in DECISION_ELIGIBLE_INTENTS and outcome.decision.tool != "search_web":
        return DecisionPlan(
            action="legacy",
            applied=False,
            not_applied_reason=f"legacy_flow_active:{legacy_intent_name}",
        )

    decision = outcome.decision
    if decision.mode == "chat":
        return DecisionPlan(action="chat", applied=True)
    if decision.mode == "clarify":
        return DecisionPlan(action="clarify", applied=True, question=decision.question)

    arguments, dropped = sanitize_arguments(decision.arguments)
    excludes = [str(item) for item in exclude_resource_ids or [] if str(item or "").strip()]
    if excludes:
        arguments["exclude_resource_ids"] = excludes
    authorization = authorize_tool_call(
        decision.tool,
        arguments=arguments,
        user_role=user_role,
        allow_writes=allow_writes,
        active_task_types=active_task_types,
    )
    if not authorization.allowed:
        return DecisionPlan(
            action="legacy",
            applied=False,
            tool=authorization.tool,
            authorization=authorization,
            not_applied_reason=authorization.error_code,
            dropped_fields=tuple(dropped),
        )
    # 只读上下文工具拥有独立执行路径，避免被当成资源搜索并进入 RAG 流程。
    if authorization.tool in {"get_shoot_context", "search_web", "search_platform_rules"}:
        return DecisionPlan(
            action="read_tool",
            applied=True,
            tool=authorization.tool,
            arguments=authorization.normalized_input,
            authorization=authorization,
            dropped_fields=tuple(dropped),
        )
    if not is_search_tool(authorization.tool):
        return DecisionPlan(
            action="legacy",
            applied=False,
            tool=authorization.tool,
            authorization=authorization,
            not_applied_reason=f"unsupported_tool:{authorization.tool}",
            dropped_fields=tuple(dropped),
        )
    return DecisionPlan(
        action="search",
        applied=True,
        tool=authorization.tool,
        arguments=authorization.normalized_input,
        authorization=authorization,
        dropped_fields=tuple(dropped),
    )


def expected_tool_for_intent(intent: AgentIntent | None) -> str | None:
    """既有意图对应的工具名，用于影子对比（§4.6）。"""
    if intent is None:
        return None
    if intent.intent == "resource_search":
        return search_tool_for_resource_types(intent.slots.get("resource_types"))
    return _INTENT_TO_TOOL.get(intent.intent)


def compare_decision_with_intent(
    outcome: AgentDecisionOutcome | None,
    intent: AgentIntent | None,
) -> dict[str, Any]:
    """老分类器 vs 新决策器的差异（意图 / 工具 / 槽位），用于灰度期对齐。"""
    decision = outcome.decision if outcome else None
    legacy_tool = expected_tool_for_intent(intent)
    legacy_slots = dict((intent.slots if intent else None) or {})
    decision_slots = decision_condition_slots(decision)

    slot_diff: dict[str, dict[str, Any]] = {}
    legacy_styles = slot_styles(legacy_slots)
    decision_styles = decision_slots.get("styles") or []
    if legacy_styles != decision_styles:
        slot_diff["styles"] = {"legacy": legacy_styles, "decision": decision_styles}
    for name in _COMPARED_SLOT_FIELDS:
        legacy_value = legacy_slots.get(name)
        decision_value = decision_slots.get(name)
        if legacy_value in (None, "", []) and decision_value in (None, "", []):
            continue
        if legacy_value != decision_value:
            slot_diff[name] = {"legacy": legacy_value, "decision": decision_value}

    return {
        "legacy_intent": intent.intent if intent else None,
        "legacy_route": intent.route if intent else None,
        "legacy_tool": legacy_tool,
        "decision_mode": decision.mode if decision else None,
        "decision_tool": decision.tool if decision else None,
        "tool_agreement": legacy_tool == (decision.tool if decision else None),
        "intent_agreement": _intent_agreement(intent, decision),
        "slot_diff": slot_diff,
    }


def _intent_agreement(intent: AgentIntent | None, decision: AgentDecision | None) -> bool | None:
    """把四种决策模式折回意图语义后再比较，避免"模式名 != 意图名"的假差异。"""
    if intent is None or decision is None:
        return None
    if decision.mode == "chat":
        return intent.intent == "chat"
    if decision.mode == "clarify":
        # 追问既可能对应 chat，也可能对应条件不全的搜索，两者都不算分歧。
        return intent.intent in DECISION_ELIGIBLE_INTENTS
    if is_search_tool(decision.tool):
        return intent.intent == "resource_search"
    return _INTENT_TO_TOOL.get(intent.intent) == decision.tool
