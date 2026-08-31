"""AI 智能体编排的契约模型：意图分类、槽位、能力注册表与工作流状态。"""

from __future__ import annotations

import json
from datetime import date, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


INTENT_SCHEMA_VERSION = "agent_intent_v2"
WORKFLOW_SCHEMA_VERSION = "agent_workflow_v1"
TOOL_SCHEMA_VERSION = "agent_tool_v1"

# ── LLM Intent Classifier Schemas ──────────────────────────────────────────

LLM_INTENT_CANDIDATE_SCHEMA_VERSION = "llm_intent_candidate_v2"
INTENT_CLASSIFICATION_TRACE_VERSION = "intent_classification_trace_v2"


class ProjectReference(BaseModel):
    """JSON-safe, deliberately small project reference stored in AI metadata."""

    model_config = ConfigDict(extra="forbid")

    id: int
    title: str
    city: str | None = None
    budget_min: int | None = None
    budget_max: int | None = None
    budget_label: str | None = None
    date_label: str | None = None
    status: str
    reference_images: list[str] = Field(default_factory=list)
    match_reason: str | None = None


def _to_int_or_none(value: Any) -> int | None:
    """将值安全转为 int，空值返回 None，布尔值视为非法。"""
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise ValueError("boolean is not a valid project budget")
    return int(value)


def _iso_or_none(value: Any) -> str | None:
    """将日期/时间值转为 ISO 字符串，空值返回 None。"""
    if value is None or value == "":
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, str):
        return value.strip() or None
    raise TypeError("project date must be a string or date-like value")


def _string_list(value: Any) -> list[str]:
    """将值规范化为非空字符串列表。"""
    if value is None:
        return []
    if not isinstance(value, (list, tuple)):
        raise TypeError("project reference_images must be a list")
    return [item for item in value if isinstance(item, str) and item]


def _clean_text(value: Any) -> str | None:
    """清理文本字段：去空白，空值返回 None。"""
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError("project reference text fields must be strings")
    return value.strip() or None


def _project_budget_label(budget_min: int | None, budget_max: int | None) -> str | None:
    """按预算上下限生成中文预算标签。"""
    if budget_min is not None and budget_max is not None:
        return f"{budget_min}-{budget_max}元"
    if budget_max is not None:
        return f"≤{budget_max}元"
    if budget_min is not None:
        return f"≥{budget_min}元"
    return None


def build_ai_project_reference(item: dict[str, Any]) -> dict[str, Any]:
    """Convert a full project serialization into the AI metadata contract."""

    budget_min = _to_int_or_none(item.get("budget_min"))
    budget_max = _to_int_or_none(item.get("budget_max"))
    reference = ProjectReference(
        id=int(item["id"]),
        title=str(item["title"]),
        city=_clean_text(item.get("city")),
        budget_min=budget_min,
        budget_max=budget_max,
        budget_label=_project_budget_label(budget_min, budget_max),
        date_label=_iso_or_none(item.get("shoot_date_start") or item.get("date_label")),
        status=str(item.get("status") or "open"),
        reference_images=_string_list(item.get("reference_images")),
        match_reason=_clean_text(item.get("match_reason")),
    )
    return reference.model_dump(mode="json")


def ensure_json_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """Fail before persistence if agent metadata violates the JSON column contract."""

    try:
        json.dumps(metadata, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("AI assistant metadata is not JSON serializable") from exc
    return metadata


class LLMIntentSlots(BaseModel):
    """LLM 输出的语义槽位，严格禁止 extra 字段。"""

    model_config = ConfigDict(extra="forbid")

    resource_types: list[Literal["photographers", "portfolio_items", "packages", "projects"]] | None = None
    city: str | None = None
    location_text: str | None = None
    budget_min: float | None = Field(default=None, ge=0)
    budget_max: float | None = Field(default=None, ge=0)
    styles: list[str] | None = None
    date: str | None = None
    time: str | None = None
    time_start: str | None = None
    time_end: str | None = None
    max_distance_km: float | None = Field(default=None, ge=0)
    budget_strict: bool | None = None
    date_strict: bool | None = None
    availability_required: bool | None = None
    sort_mode: Literal["best_match", "nearest", "lowest_price", "earliest_available"] | None = None
    people_count: int | None = Field(default=None, gt=0)
    limit: int | None = Field(default=None, ge=1, le=20)
    photographer_name: str | None = None
    package_name: str | None = None
    duration_minutes: int | None = Field(default=None, gt=0)
    image_count: int | None = Field(default=None, ge=0)
    requires_makeup: bool | None = None
    package_includes: list[str] | None = None
    title: str | None = None
    description: str | None = None
    deliverables: str | None = None
    package_description: str | None = None


class LLMIntentCandidate(BaseModel):
    """LLM 输出的严格校验后的候选结果。"""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["llm_intent_candidate_v1", "llm_intent_candidate_v2"] = LLM_INTENT_CANDIDATE_SCHEMA_VERSION
    intent: Literal[
        "chat",
        "resource_search",
        "image_analysis",
        "image_generation_flow",
        "create_inspiration_flow",
        "project_application",
        "project_flow",
        "package_publish_flow",
        "booking_flow",
        "follow_photographer",
        "work_publish_flow",
    ]
    slots: LLMIntentSlots = Field(default_factory=LLMIntentSlots)
    confidence: float = Field(ge=0, le=1)


# ── Intent Policy Table ────────────────────────────────────────────────────

def _search_sub_intent(resource_types: list[str] | None) -> str:
    """根据资源类型映射对应的搜索子意图。"""
    if resource_types == ["packages"]:
        return "search_package"
    if resource_types == ["portfolio_items"]:
        return "search_portfolio_item"
    if resource_types == ["photographers"]:
        return "search_photographer"
    if resource_types == ["projects"]:
        return "search_project"
    return "search_resources"


INTENT_POLICIES: dict[str, dict[str, Any]] = {
    "chat": {
        "route": "chat",
        "sub_intents": ["general_chat"],
        "requires_confirmation": False,
    },
    "resource_search": {
        "route": "retrieval",
        "sub_intents": ["search_resources"],
        "requires_confirmation": False,
    },
    "image_analysis": {
        "route": "vision",
        "sub_intents": ["vision_analysis"],
        "requires_confirmation": False,
    },
    "image_generation_flow": {
        "route": "image_generation",
        "sub_intents": ["text_to_image", "image_to_image"],
        "requires_confirmation": False,
    },
    "create_inspiration_flow": {
        "route": "inspiration",
        "sub_intents": ["vision_analysis", "generate_inspiration", "select_location", "save_inspiration"],
        "requires_confirmation": False,
    },
    "project_application": {
        "route": "project_application",
        "sub_intents": ["prepare_project_application"],
        "requires_confirmation": False,
    },
    "project_flow": {
        "route": "project",
        "sub_intents": ["create_project"],
        "requires_confirmation": True,
    },
    "package_publish_flow": {
        "route": "package",
        "sub_intents": ["publish_package"],
        "requires_confirmation": True,
    },
    "booking_flow": {
        "route": "booking",
        "sub_intents": ["search_package", "create_booking"],
        "requires_confirmation": True,
    },
    "follow_photographer": {
        "route": "follow",
        "sub_intents": ["prepare_follow"],
        "requires_confirmation": True,
    },
    "work_publish_flow": {
        "route": "work_publish",
        "sub_intents": ["prepare_work_publish"],
        "requires_confirmation": False,
    },
}


def apply_intent_policy(
    intent_name: str,
    model_slots: dict[str, Any] | None = None,
    has_image: bool = False,
) -> dict[str, Any]:
    """根据 intent 名称生成安全的 route / sub_intents / requires_confirmation / missing_slots。"""
    policy = INTENT_POLICIES.get(intent_name, INTENT_POLICIES["chat"])
    result = dict(policy)
    slots = dict(model_slots or {})

    # 图片存在时补充 vision_analysis
    if has_image and intent_name in {"resource_search", "booking_flow", "image_analysis"}:
        if "vision_analysis" not in result.get("sub_intents", []):
            result["sub_intents"] = ["vision_analysis", *result.get("sub_intents", [])]

    # resource_types 对应的搜索子意图
    if intent_name == "resource_search":
        resource_types = slots.get("resource_types")
        has_vision = "vision_analysis" in result.get("sub_intents", [])
        if resource_types:
            result["sub_intents"] = [_search_sub_intent(resource_types)]
            # 企划发现使用独立路由
            if resource_types == ["projects"]:
                result["route"] = "project_discovery"
                result["requires_confirmation"] = False
        else:
            result["sub_intents"] = ["search_resources"]
        if has_vision:
            result["sub_intents"] = ["vision_analysis", *result["sub_intents"]]
        # 图片驱动的检索使用单独的 route
        if has_image:
            result["route"] = "vision_retrieval"

    if intent_name == "booking_flow":
        resource_types = slots.get("resource_types", ["packages"])
        sub_intents = ["search_package", "create_booking"]
        if has_image:
            sub_intents.insert(0, "vision_analysis")
        result["sub_intents"] = sub_intents

    # missing_slots
    result["missing_slots"] = _policy_missing_slots(intent_name, slots)
    return result


def _policy_missing_slots(intent_name: str, slots: dict[str, Any]) -> list[str]:
    """按意图计算缺失的必要槽位列表。"""
    if intent_name == "project_flow":
        required = ("city", "budget_max", "style", "date", "people_count", "description")
        return [name for name in required if not slots.get(name)]
    if intent_name == "package_publish_flow":
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
    if intent_name == "booking_flow":
        missing = []
        if not slots.get("date"):
            missing.append("date")
        return missing
    return []


# ── Classification Result ──────────────────────────────────────────────────


class IntentClassificationResult(BaseModel):
    """分类器输出的完整结果，同时包含规则和模型候选。"""

    model_config = ConfigDict(extra="forbid")

    intent: AgentIntent
    parser: Literal["rules", "model", "fallback"] = "rules"
    fallback_reason: str | None = None
    rule_candidate: dict[str, Any] = Field(default_factory=dict)
    model_candidate: dict[str, Any] | None = None
    chosen_parser: str = "rules"
    rule_intent: str | None = None
    model_latency_ms: int | None = None
    model_confidence: float | None = None
    model_provider: str | None = None
    model_name: str | None = None
    prompt_version: str | None = None
    agreement: bool | None = None


class RuleIntentCandidate(BaseModel):
    """规则候选结果，显式表达是否真正命中规则。"""

    model_config = ConfigDict(extra="forbid")

    intent: str
    matched: bool
    matched_rule: str | None = None
    coverage: float = 0.0
    slots: dict[str, Any] = Field(default_factory=dict)


# ── Capability Registry ────────────────────────────────────────────────────

CAPABILITIES: dict[tuple[str, str | None], dict[str, Any]] = {
    ("resource_search", "projects"): {
        "route": "project_discovery",
        "sub_intent": "search_project",
        "allowed_roles": ["photographer"],
        "write": False,
        "requires_confirmation": False,
    },
    ("resource_search", "photographers"): {
        "route": "retrieval",
        "sub_intent": "search_photographer",
        "write": False,
        "requires_confirmation": False,
    },
    ("resource_search", "portfolio_items"): {
        "route": "retrieval",
        "sub_intent": "search_portfolio_item",
        "write": False,
        "requires_confirmation": False,
    },
    ("resource_search", "packages"): {
        "route": "retrieval",
        "sub_intent": "search_package",
        "write": False,
        "requires_confirmation": False,
    },
    ("project_flow", None): {
        "route": "project",
        "sub_intent": "create_project",
        "allowed_roles": ["customer"],
        "write": True,
        "requires_confirmation": True,
    },
}


def check_capability(intent_name: str, resource_types: list[str] | None) -> dict[str, Any] | None:
    """检查能力注册表，返回能力配置或 None（无权/不合法）。"""
    # 尝试带 resource_types 的精确匹配
    if resource_types:
        # 只支持单一资源类型的匹配
        for rt in resource_types:
            direct = CAPABILITIES.get((intent_name, rt))
            if direct:
                return direct
    # 尝试不带 resource_types 的匹配
    return CAPABILITIES.get((intent_name, None))


class WorkflowStatus(str, Enum):
    """工作流状态枚举。"""
    COLLECTING_SLOTS = "collecting_slots"
    RETRIEVING = "retrieving"
    PRESENTING_OPTIONS = "presenting_options"
    AWAITING_DETAILS = "awaiting_details"
    AWAITING_REFERENCE_IMAGES = "awaiting_reference_images"
    AWAITING_TARGET = "awaiting_target"
    AWAITING_PACKAGE = "awaiting_package"
    AWAITING_DATE = "awaiting_date"
    AWAITING_TIME = "awaiting_time"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"


class AgentSlots(BaseModel):
    """统一的槽位契约；保留 extra 以兼容后续垂直流程扩展。"""

    model_config = ConfigDict(extra="allow")

    resource_types: list[str] | None = None
    city: str | None = None
    location_text: str | None = None
    budget_min: float | None = Field(default=None, ge=0)
    budget_max: float | None = Field(default=None, ge=0)
    style: str | list[str] | None = None
    styles: list[str] | None = None
    date: str | None = None
    time: str | None = None
    time_start: str | None = None
    time_end: str | None = None
    max_distance_km: float | None = Field(default=None, ge=0)
    budget_strict: bool | None = None
    date_strict: bool | None = None
    availability_required: bool | None = None
    sort_mode: Literal["best_match", "nearest", "lowest_price", "earliest_available"] | None = None
    people_count: int | None = Field(default=None, gt=0)
    limit: int | None = Field(default=None, ge=1, le=20)
    photographer_id: int | None = Field(default=None, gt=0)
    photographer_name: str | None = None
    package_id: str | None = None
    package_name: str | None = None
    duration_minutes: int | None = Field(default=None, gt=0)
    image_count: int | None = Field(default=None, ge=0)
    requires_makeup: bool | None = None
    package_includes: list[str] | None = None
    title: str | None = None
    description: str | None = None


class AgentIntent(BaseModel):
    """编排层唯一的结构化意图输出。"""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["agent_intent_v2"] = INTENT_SCHEMA_VERSION
    intent: str
    sub_intents: list[str] = Field(default_factory=list)
    slots: dict[str, Any] = Field(default_factory=dict)
    missing_slots: list[str] = Field(default_factory=list)
    requires_confirmation: bool = False
    route: str = "chat"
    confidence: float = Field(default=0.7, ge=0, le=1)
    parser: Literal["rules", "model", "fallback"] = "rules"

    @field_validator("slots", mode="before")
    @classmethod
    def validate_slots(cls, value: Any) -> dict[str, Any]:
        """规范化槽位：AgentSlots 实例直接转字典，其余走模型校验。"""
        if isinstance(value, AgentSlots):
            return value.model_dump(exclude_none=True)
        return AgentSlots.model_validate(value or {}).model_dump(exclude_none=True)

    def as_dict(self) -> dict[str, Any]:
        """将意图序列化为 JSON 兼容字典。"""
        return self.model_dump(mode="json")


class PendingToolAction(BaseModel):
    """待确认的工具调用动作（含幂等键与确认次数）。"""
    model_config = ConfigDict(extra="forbid")

    tool: str
    input: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = None
    confirmation_count: int = Field(default=1, ge=0)


class AgentTaskState(BaseModel):
    """持久化到消息 metadata 的统一工作流状态。"""

    model_config = ConfigDict(extra="allow")

    schema_version: Literal["agent_workflow_v1"] = WORKFLOW_SCHEMA_VERSION
    task_type: str
    status: WorkflowStatus
    slots: dict[str, Any] = Field(default_factory=dict)
    missing_slots: list[str] = Field(default_factory=list)
    pending_action: PendingToolAction | None = None

    @field_validator("slots", mode="before")
    @classmethod
    def validate_slots(cls, value: Any) -> dict[str, Any]:
        """规范化槽位：以 AgentSlots 校验后转字典。"""
        return AgentSlots.model_validate(value or {}).model_dump(exclude_none=True)


def normalize_agent_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    """在写入消息前校验并版本化编排层输出。"""

    normalized = dict(metadata or {})
    task_state = normalized.get("task_state")
    if task_state:
        normalized["task_state"] = AgentTaskState.model_validate(task_state).model_dump(
            mode="json",
            exclude_none=False,
        )
        normalized["workflow_schema_version"] = WORKFLOW_SCHEMA_VERSION
    return normalized
