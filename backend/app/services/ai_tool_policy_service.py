"""AI 工具策略服务：工具注册、风险分级、鉴权与执行准备。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Type

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from backend.app.models.ai_conversation import AgentActionLog, AIConversation
from backend.app.schemas.photographer import PackageSchema
from backend.app.schemas.recommendation import PackageRecommendationQuery
from backend.app.schemas.project import ProjectCreate
from backend.app.schemas.inspiration import InspirationCreate
from backend.app.services.ai_agent_contracts import TOOL_SCHEMA_VERSION
from backend.app.services.ai_agent_decision_contracts import (
    GetShootContextInput,
    SearchPackagesInput,
    SearchPhotographersInput,
    SearchPlatformRulesInput,
    SearchPortfolioItemsInput,
    SearchProjectsInput,
    SearchWebInput,
)
from backend.app.core.config import settings


class ToolRiskLevel(str, Enum):
    """工具风险等级：只读/可逆写/敏感写/禁止。"""
    READ_ONLY = "read_only"
    REVERSIBLE_WRITE = "reversible_write"
    SENSITIVE_WRITE = "sensitive_write"
    FORBIDDEN = "forbidden"


class ConfirmationPolicy(str, Enum):
    """工具执行所需的用户确认策略。"""
    NONE = "none"
    ONCE = "once"
    TWICE = "twice"
    TRADITIONAL_UI = "traditional_ui"
    FORBIDDEN = "forbidden"


TOOL_PERMISSION_PROFILES: dict[str, set[str] | None] = {
    "read_only": set(),
    "normal": None,
    "publisher": {"create_project", "publish_package", "publish_work", "create_inspiration_draft"},
    "booking": {"create_booking", "get_available_slots", "search_bookable_packages"},
}

HIGH_RISK_TOOLS = {"create_project", "publish_package", "publish_work", "create_booking"}


class FollowPhotographerInput(BaseModel):
    """关注摄影师工具的入参模型。"""
    model_config = ConfigDict(extra="forbid")
    photographer_id: int = Field(gt=0)


class AvailabilityInput(BaseModel):
    """查询可约时段工具的入参模型。"""
    model_config = ConfigDict(extra="forbid")
    photographer_id: int = Field(gt=0)
    package_duration: int = Field(default=120, gt=0)
    date_str: str | None = None


class CreateBookingInput(BaseModel):
    """创建预约订单工具的入参模型。"""
    model_config = ConfigDict(extra="forbid")
    package_id: str | None = None
    photographer_id: int = Field(gt=0)
    package_description: str | None = None
    package_display: str | None = None
    appointment_date: str | None = None
    # Kept optional solely for old callers; new booking requests must use appointment_date.
    appointment_time: str | None = None
    duration_minutes: int = Field(default=120, gt=0)
    notes: str | None = None


@dataclass(frozen=True)
class ToolSpec:
    """工具规格定义：入参模型、风险等级、确认策略与审计字段。"""
    name: str
    input_model: Type[BaseModel]
    risk_level: ToolRiskLevel
    confirmation_policy: ConfirmationPolicy
    timeout_seconds: int
    retryable: bool
    idempotent: bool
    audit_fields: tuple[str, ...]
    compensation: str | None = None
    schema_version: str = TOOL_SCHEMA_VERSION
    # ── 以下字段供阶段B 的统一决策层使用（工具目录 + 鉴权），不影响既有调用点 ──
    # description / argument_hint 会拼进决策 prompt 的工具目录。
    description: str = ""
    argument_hint: tuple[str, ...] = ()
    # 空元组表示不限角色；否则只有列出的角色可以调用。
    allowed_roles: tuple[str, ...] = ()
    # 是否出现在给模型看的工具目录里。带平台实体 ID 入参的工具默认不暴露，
    # 避免模型为了凑参数而编造 photographer_id / package_id（§5.1）。
    llm_selectable: bool = False
    # 只允许模型“提出”，不允许决策层直接执行：参数必须由后端从真实候选补全，
    # 执行仍走既有确认流程与事务（§5.2）。
    proposal_only: bool = False
    # 只有存在这些进行中的任务时才允许调用（例如必须先有一次资源搜索）。
    requires_active_task: tuple[str, ...] = ()

    @property
    def required_confirmations(self) -> int:
        """按确认策略换算需要的确认次数，不适用时返回 99。"""
        if self.confirmation_policy == ConfirmationPolicy.NONE:
            return 0
        if self.confirmation_policy == ConfirmationPolicy.ONCE:
            return 1
        if self.confirmation_policy == ConfirmationPolicy.TWICE:
            return 2
        return 99

    @property
    def is_write(self) -> bool:
        """判断该工具是否属于写操作。"""
        return self.risk_level in {
            ToolRiskLevel.REVERSIBLE_WRITE,
            ToolRiskLevel.SENSITIVE_WRITE,
        }


TOOL_REGISTRY: dict[str, ToolSpec] = {
    "get_shoot_context": ToolSpec(
        name="get_shoot_context",
        input_model=GetShootContextInput,
        risk_level=ToolRiskLevel.READ_ONLY,
        confirmation_policy=ConfirmationPolicy.NONE,
        timeout_seconds=10,
        retryable=True,
        idempotent=True,
        audit_fields=("location_text", "shoot_date", "start_time", "duration_minutes"),
        description="查询指定地点、日期和时段的真实天气、地图位置、日照窗口及户外拍摄建议。地点有歧义时返回候选，不自行选择。",
        argument_hint=(
            "location_text: 拍摄地点",
            "shoot_date: 拍摄日期，格式 YYYY-MM-DD",
            "start_time: 开始时间，格式 HH:MM，可选",
            "duration_minutes: 拍摄时长，默认 120 分钟",
            "latitude / longitude: 已确认坐标时成对提供，可选",
        ),
        llm_selectable=True,
    ),
    "search_photographers": ToolSpec(
        name="search_photographers",
        input_model=SearchPhotographersInput,
        risk_level=ToolRiskLevel.READ_ONLY,
        confirmation_policy=ConfirmationPolicy.NONE,
        timeout_seconds=15,
        retryable=True,
        idempotent=True,
        audit_fields=("city", "styles", "budget_max", "limit"),
        description="检索平台已上架的摄影师，返回真实的摄影师候选（含简介、报价区间、作品摘要）。",
        argument_hint=(
            "city: 城市",
            "styles: 风格/题材列表",
            "budget_max: 预算上限（元）",
            "photographer_name: 用户点名的摄影师",
            "limit: 返回数量 1-10",
            "query_text: 用户的检索意图短语（不含反馈词）",
        ),
        llm_selectable=True,
    ),
    "search_portfolio_items": ToolSpec(
        name="search_portfolio_items",
        input_model=SearchPortfolioItemsInput,
        risk_level=ToolRiskLevel.READ_ONLY,
        confirmation_policy=ConfirmationPolicy.NONE,
        timeout_seconds=15,
        retryable=True,
        idempotent=True,
        audit_fields=("city", "styles", "limit"),
        description="检索平台上的作品/样片，用于“找作品、看案例、找类似风格的片子”。",
        argument_hint=(
            "city: 城市",
            "styles: 风格/题材列表",
            "photographer_name: 用户点名的摄影师",
            "limit: 返回数量 1-10",
            "query_text: 用户的检索意图短语",
        ),
        llm_selectable=True,
    ),
    "search_packages": ToolSpec(
        name="search_packages",
        input_model=SearchPackagesInput,
        risk_level=ToolRiskLevel.READ_ONLY,
        confirmation_policy=ConfirmationPolicy.NONE,
        timeout_seconds=15,
        retryable=True,
        idempotent=True,
        audit_fields=("city", "styles", "budget_max", "requires_makeup", "limit"),
        description="检索已上架的拍摄套餐/方案（含价格、时长、精修张数、是否含妆造）。用户问“方案、套餐、报价、多少钱”时用它。",
        argument_hint=(
            "city: 城市",
            "styles: 风格/题材列表，如 婚礼、写真、毕业照",
            "budget_max: 预算上限（元）",
            "requires_makeup: 是否必须含妆造",
            "photographer_name: 用户点名的摄影师",
            "limit: 返回数量 1-10",
            "query_text: 用户的检索意图短语",
        ),
        llm_selectable=True,
    ),
    "search_projects": ToolSpec(
        name="search_projects",
        input_model=SearchProjectsInput,
        risk_level=ToolRiskLevel.READ_ONLY,
        confirmation_policy=ConfirmationPolicy.NONE,
        timeout_seconds=15,
        retryable=True,
        idempotent=True,
        audit_fields=("city", "styles", "budget_max", "limit"),
        description="检索可应邀的企划（客户发布的拍摄需求），供摄影师找活、报名、申请应邀时使用。",
        argument_hint=(
            "city: 城市",
            "styles: 题材列表",
            "budget_min / budget_max: 预算区间（元）",
            "limit: 返回数量 1-10",
        ),
        allowed_roles=("photographer",),
        llm_selectable=True,
    ),
    "search_web": ToolSpec(
        name="search_web",
        input_model=SearchWebInput,
        risk_level=ToolRiskLevel.READ_ONLY,
        confirmation_policy=ConfirmationPolicy.NONE,
        timeout_seconds=10,
        retryable=True,
        idempotent=True,
        audit_fields=("query", "limit", "language", "freshness"),
        description="Search public web pages for external facts and current information; returns real titles, snippets, and URLs.",
        argument_hint=(
            "query: search query, 2-300 characters",
            "limit: 1-5 results",
            "language: zh-CN, zh-TW, or en-US",
            "freshness: day/week/month/year, optional",
        ),
        llm_selectable=True,
    ),
    "search_platform_rules": ToolSpec(
        name="search_platform_rules",
        input_model=SearchPlatformRulesInput,
        risk_level=ToolRiskLevel.READ_ONLY,
        confirmation_policy=ConfirmationPolicy.NONE,
        timeout_seconds=10,
        retryable=True,
        idempotent=True,
        audit_fields=("query", "limit"),
        description=(
            "检索平台自身的业务规则文档，返回带规则编号的原文片段。"
            "覆盖：订单交易与退款政策、定金尾款、平台服务费、改期与验收期限、"
            "返修规则、争议处理、企划流程、作品与方案上传限制、入驻审核、"
            "用户与 AI 助手使用规则等。"
            "用户询问平台规则、政策、条款、期限、金额比例时必须使用本工具，不要凭记忆回答。"
        ),
        argument_hint=(
            "query: 用户的规则问题关键词，2-300 字符",
            "limit: 返回片段数量 1-10，默认 5",
        ),
        llm_selectable=True,
    ),
    "search_bookable_packages": ToolSpec(
        name="search_bookable_packages",
        input_model=PackageRecommendationQuery,
        risk_level=ToolRiskLevel.READ_ONLY,
        confirmation_policy=ConfirmationPolicy.NONE,
        timeout_seconds=15,
        retryable=True,
        idempotent=True,
        audit_fields=("city", "styles", "budget_max", "shoot_date", "time_start", "time_end", "max_distance_km"),
        description="按日期与档期筛选可预约套餐（预约规划流程内部使用）。",
    ),
    "get_available_slots": ToolSpec(
        name="get_available_slots",
        input_model=AvailabilityInput,
        risk_level=ToolRiskLevel.READ_ONLY,
        confirmation_policy=ConfirmationPolicy.NONE,
        timeout_seconds=10,
        retryable=True,
        idempotent=True,
        audit_fields=("photographer_id", "date_str"),
        description="查询某位摄影师的可约时段（需要真实 photographer_id，由预约流程提供）。",
    ),
    "follow_photographer": ToolSpec(
        name="follow_photographer",
        input_model=FollowPhotographerInput,
        risk_level=ToolRiskLevel.REVERSIBLE_WRITE,
        confirmation_policy=ConfirmationPolicy.ONCE,
        timeout_seconds=10,
        retryable=False,
        idempotent=True,
        audit_fields=("photographer_id",),
        compensation="unfollow_photographer",
        description="关注某位摄影师。写操作：只能提出，必须由用户确认后由后端执行。",
        argument_hint=("photographer_id 由后端从上一轮真实候选补全，不要自己填",),
        llm_selectable=True,
        proposal_only=True,
    ),
    "create_project": ToolSpec(
        name="create_project",
        input_model=ProjectCreate,
        risk_level=ToolRiskLevel.REVERSIBLE_WRITE,
        confirmation_policy=ConfirmationPolicy.ONCE,
        timeout_seconds=15,
        retryable=False,
        idempotent=True,
        audit_fields=("title", "city", "budget_max", "publish"),
        compensation="close_project",
        description="发布企划（拍摄需求征集）。写操作：只能提出，字段由既有表单流程收集并经用户确认。",
        argument_hint=("企划字段由后端表单流程收集，不要自己编造",),
        llm_selectable=True,
        proposal_only=True,
    ),
    "publish_package": ToolSpec(
        name="publish_package",
        input_model=PackageSchema,
        risk_level=ToolRiskLevel.REVERSIBLE_WRITE,
        confirmation_policy=ConfirmationPolicy.ONCE,
        timeout_seconds=15,
        retryable=False,
        idempotent=True,
        audit_fields=("name", "price", "duration", "city"),
        compensation="deactivate_package",
        description="发布/上架摄影套餐。写操作：只能提出，字段由既有表单流程收集并经用户确认。",
        argument_hint=("套餐字段由后端表单流程收集，不要自己编造",),
        allowed_roles=("photographer",),
        llm_selectable=True,
        proposal_only=True,
    ),
    "create_booking": ToolSpec(
        name="create_booking",
        input_model=CreateBookingInput,
        risk_level=ToolRiskLevel.REVERSIBLE_WRITE,
        confirmation_policy=ConfirmationPolicy.ONCE,
        timeout_seconds=20,
        retryable=False,
        idempotent=True,
        audit_fields=("photographer_id", "package_id", "appointment_date", "duration_minutes"),
        compensation="cancel_pending_booking",
        description="创建预约订单。写操作：只能提出，套餐与摄影师 ID 由后端从上一轮真实候选补全，并必须经用户确认。",
        argument_hint=("package_id / photographer_id / appointment_date 由后端补全，不要自己填",),
        llm_selectable=True,
        proposal_only=True,
    ),
    "create_inspiration_draft": ToolSpec(
        name="create_inspiration_draft",
        input_model=InspirationCreate,
        risk_level=ToolRiskLevel.REVERSIBLE_WRITE,
        confirmation_policy=ConfirmationPolicy.NONE,
        timeout_seconds=20,
        retryable=True,
        idempotent=True,
        audit_fields=("title", "tags", "status"),
        compensation="archive_inspiration",
        description="Create a private inspiration draft from validated Agent output.",
    ),
}

# 指南里出现过的别名（§3.2 工具清单）与既有注册名的映射，避免模型用别名时直接判为未知工具。
TOOL_ALIASES: dict[str, str] = {
    "get_photographer_availability": "get_available_slots",
    "search_photographer": "search_photographers",
    "search_package": "search_packages",
    "search_portfolio": "search_portfolio_items",
    "search_portfolio_item": "search_portfolio_items",
    "search_project": "search_projects",
    "search_rules": "search_platform_rules",
    "search_platform_rule": "search_platform_rules",
    "query_rules": "search_platform_rules",
}


def resolve_tool_name(tool_name: str | None) -> str:
    """把别名解析成注册名；未知名称原样返回，由调用方按 unregistered_tool 处理。"""
    name = (tool_name or "").strip()
    return TOOL_ALIASES.get(name, name)


class ToolPolicyError(ValueError):
    """工具策略校验失败时抛出的异常。"""
    pass


@dataclass(frozen=True)
class ToolExecutionPreparation:
    """工具执行前的准备结果：规格、规范化入参与幂等信息。"""
    spec: ToolSpec
    normalized_input: dict[str, Any]
    idempotency_key: str | None
    existing_log: AgentActionLog | None
    action_summary: dict[str, Any] = field(default_factory=dict)


def get_tool_spec(tool_name: str) -> ToolSpec:
    """按名称获取工具规格，未注册时抛 ToolPolicyError。"""
    spec = TOOL_REGISTRY.get(tool_name)
    if not spec:
        raise ToolPolicyError(f"unregistered_tool:{tool_name}")
    return spec


# ── 阶段B：工具目录与统一鉴权 ───────────────────────────────────────────────


def build_tool_catalog(
    *,
    user_role: str | None = None,
    allow_writes: bool = True,
    include_read_tools: bool = False,
) -> list[dict[str, Any]]:
    """给决策模型看的工具目录：只暴露该角色真的能用的工具。

    目录里带上风险等级和确认要求，让模型知道写操作必须先 confirm，
    而不是以为自己可以直接下单（§5.2）。
    """
    catalog: list[dict[str, Any]] = []
    for spec in TOOL_REGISTRY.values():
        if not spec.llm_selectable or spec.risk_level == ToolRiskLevel.FORBIDDEN:
            continue
        if spec.name == "search_web" and not settings.WEB_SEARCH_ENABLED:
            continue
        if spec.name == "search_platform_rules" and not settings.AI_PLATFORM_RULES_ENABLED:
            continue
        # 旧调用方默认维持原目录；仅决策循环显式开放新增的只读工具。
        if spec.name in {"get_shoot_context", "search_web", "search_platform_rules"} and not include_read_tools:
            continue
        if spec.allowed_roles and (user_role or "") not in spec.allowed_roles:
            continue
        if spec.is_write and not allow_writes:
            continue
        catalog.append({
            "name": spec.name,
            "description": spec.description,
            "arguments": list(spec.argument_hint),
            "risk_level": spec.risk_level.value,
            "requires_confirmation": spec.required_confirmations > 0,
            "execution": "backend_confirm_flow" if spec.proposal_only else "backend_direct",
        })
    return catalog


@dataclass(frozen=True)
class ToolAuthorization:
    """一次工具调用的鉴权结果。

    allowed=False 时 error_code 说明原因，调用方据此回退到既有流程并记录 fallback_reason，
    绝不能在鉴权失败后仍然执行工具。
    """

    tool: str
    allowed: bool
    spec: ToolSpec | None = None
    normalized_input: dict[str, Any] = field(default_factory=dict)
    error_code: str | None = None
    requires_confirmation: bool = False
    dropped_fields: tuple[str, ...] = ()

    @property
    def is_write(self) -> bool:
        """判断本次授权结果对应的工具是否为写操作。"""
        return bool(self.spec and self.spec.is_write)

    def as_dict(self) -> dict[str, Any]:
        """将鉴权结果转为可序列化的字典。"""
        return {
            "tool": self.tool,
            "allowed": self.allowed,
            "error_code": self.error_code,
            "risk_level": self.spec.risk_level.value if self.spec else None,
            "requires_confirmation": self.requires_confirmation,
            "dropped_fields": list(self.dropped_fields),
        }


def authorize_tool_call(
    tool_name: str | None,
    *,
    arguments: dict[str, Any] | None = None,
    user_role: str | None = None,
    allow_writes: bool = True,
    confirmation_count: int = 0,
    active_task_types: tuple[str, ...] = (),
    approval_policy: str = "confirm_write",
    tool_permission_profile: str = "normal",
) -> ToolAuthorization:
    """执行前的统一策略检查（§4.4）：参数合法性、角色权限、写权限、确认要求。

    顺序即优先级：先判断工具本身是否可用，再校验参数，最后才看确认次数——
    这样返回的 error_code 总是指向第一个真正的问题。
    """
    resolved = resolve_tool_name(tool_name)
    if not resolved:
        return ToolAuthorization(tool="", allowed=False, error_code="missing_tool")
    spec = TOOL_REGISTRY.get(resolved)
    if spec is None:
        return ToolAuthorization(
            tool=resolved,
            allowed=False,
            error_code=f"unregistered_tool:{resolved}",
        )
    if spec.risk_level == ToolRiskLevel.FORBIDDEN:
        return ToolAuthorization(
            tool=resolved, allowed=False, spec=spec, error_code=f"tool_forbidden:{resolved}"
        )
    if not spec.llm_selectable:
        return ToolAuthorization(
            tool=resolved, allowed=False, spec=spec, error_code=f"tool_not_selectable:{resolved}"
        )
    if spec.allowed_roles and (user_role or "") not in spec.allowed_roles:
        return ToolAuthorization(
            tool=resolved, allowed=False, spec=spec, error_code=f"role_not_allowed:{user_role or 'unknown'}"
        )
    allowed_profile = TOOL_PERMISSION_PROFILES.get(tool_permission_profile)
    if tool_permission_profile not in TOOL_PERMISSION_PROFILES:
        return ToolAuthorization(tool=resolved, allowed=False, spec=spec, error_code="unknown_permission_profile")
    if allowed_profile is not None and resolved not in allowed_profile:
        return ToolAuthorization(tool=resolved, allowed=False, spec=spec, error_code=f"tool_not_in_profile:{tool_permission_profile}")
    if spec.is_write and not allow_writes:
        return ToolAuthorization(
            tool=resolved, allowed=False, spec=spec, error_code=f"writes_not_allowed:{resolved}"
        )
    if spec.proposal_only:
        # 写操作的参数必须由后端从真实候选补全，决策层只能提出，不能执行。
        return ToolAuthorization(
            tool=resolved, allowed=False, spec=spec, error_code=f"proposal_only_tool:{resolved}",
            requires_confirmation=True,
        )
    if spec.requires_active_task and not any(
        task_type in active_task_types for task_type in spec.requires_active_task
    ):
        return ToolAuthorization(
            tool=resolved, allowed=False, spec=spec, error_code=f"missing_active_task:{resolved}"
        )

    payload = dict(arguments or {})
    unknown = tuple(
        key for key in payload if key not in spec.input_model.model_fields
    )
    try:
        normalized = spec.input_model.model_validate(payload).model_dump(
            mode="json",
            exclude_none=True,
        )
    except Exception as exc:
        return ToolAuthorization(
            tool=resolved,
            allowed=False,
            spec=spec,
            error_code=f"invalid_arguments:{type(exc).__name__}",
            dropped_fields=unknown,
        )

    required_confirmations = spec.required_confirmations
    if approval_policy == "confirm_all" and spec.is_write:
        required_confirmations = max(required_confirmations, 1)
    if resolved in HIGH_RISK_TOOLS:
        required_confirmations = max(required_confirmations, 1)
    if approval_policy == "auto" and spec.risk_level == ToolRiskLevel.REVERSIBLE_WRITE and resolved not in HIGH_RISK_TOOLS:
        required_confirmations = 0
    if confirmation_count < required_confirmations:
        return ToolAuthorization(
            tool=resolved,
            allowed=False,
            spec=spec,
            normalized_input=normalized,
            error_code=f"confirmation_required:{resolved}:{required_confirmations}",
            requires_confirmation=True,
        )

    return ToolAuthorization(
        tool=resolved,
        allowed=True,
        spec=spec,
        normalized_input=normalized,
        requires_confirmation=spec.required_confirmations > 0,
    )


def build_action_summary(tool_name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return a compact, human-readable summary used by confirmation UIs and audit."""
    resolved = resolve_tool_name(tool_name)
    labels = {
        "create_project": "发布拍摄企划", "publish_package": "发布摄影套餐",
        "publish_work": "发布作品", "create_booking": "创建预约",
        "follow_photographer": "关注摄影师", "create_inspiration_draft": "保存灵感草稿",
    }
    args = arguments or {}
    spec = TOOL_REGISTRY.get(resolved)
    details = [{"field": key, "value": args[key]} for key in (spec.audit_fields if spec else ()) if key in args]
    return {"tool": resolved, "title": labels.get(resolved, resolved), "risk_level": spec.risk_level.value if spec else "forbidden", "details": details}


def prepare_tool_execution(
    db: Session,
    *,
    tool_name: str,
    tool_input: dict[str, Any],
    user_id: int,
    conversation_id: int,
    confirmation_count: int,
    idempotency_key: str | None = None,
) -> ToolExecutionPreparation:
    """校验策略并规范化入参，返回执行准备结果与幂等记录。"""
    spec = get_tool_spec(tool_name)
    conversation = db.query(AIConversation).filter(
        AIConversation.id == conversation_id, AIConversation.user_id == user_id
    ).first()
    profile = getattr(conversation, "tool_permission_profile", "normal") if conversation else "normal"
    allowed_profile = TOOL_PERMISSION_PROFILES.get(profile)
    if profile not in TOOL_PERMISSION_PROFILES:
        raise ToolPolicyError("unknown_permission_profile")
    resolved_tool_name = resolve_tool_name(tool_name)
    if allowed_profile is not None and resolved_tool_name not in allowed_profile:
        raise ToolPolicyError(f"tool_not_in_profile:{profile}")
    approval_policy = (getattr(conversation, "approval_policy", "confirm_write") if conversation else "confirm_write") or "confirm_write"
    required_confirmations = spec.required_confirmations
    if approval_policy == "confirm_all" and spec.is_write:
        required_confirmations = max(required_confirmations, 1)
    if resolved_tool_name in HIGH_RISK_TOOLS:
        required_confirmations = max(required_confirmations, 1)
    if approval_policy == "auto" and spec.risk_level == ToolRiskLevel.REVERSIBLE_WRITE and resolved_tool_name not in HIGH_RISK_TOOLS:
        required_confirmations = 0
    if spec.risk_level == ToolRiskLevel.FORBIDDEN:
        raise ToolPolicyError(f"tool_forbidden:{tool_name}")
    if confirmation_count < required_confirmations:
        raise ToolPolicyError(
            f"confirmation_required:{tool_name}:{required_confirmations}"
        )

    normalized = spec.input_model.model_validate(tool_input or {}).model_dump(
        mode="json",
        exclude_none=True,
    )
    resolved_key = None
    existing = None
    if spec.idempotent:
        resolved_key = idempotency_key or build_idempotency_key(
            tool_name=tool_name,
            user_id=user_id,
            conversation_id=conversation_id,
            normalized_input=normalized,
        )
        existing = db.query(AgentActionLog).filter(
            AgentActionLog.idempotency_key == resolved_key
        ).first()

    return ToolExecutionPreparation(
        spec=spec,
        normalized_input=normalized,
        idempotency_key=resolved_key,
        existing_log=existing,
        action_summary=build_action_summary(tool_name, normalized),
    )


def build_idempotency_key(
    *,
    tool_name: str,
    user_id: int,
    conversation_id: int,
    normalized_input: dict[str, Any],
) -> str:
    """按用户、会话、工具与入参生成稳定的幂等键。"""
    canonical = json.dumps(
        normalized_input,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]
    return f"agent:{user_id}:{conversation_id}:{tool_name}:{digest}"


def replay_tool_call(log: AgentActionLog) -> dict[str, Any]:
    """从操作日志重放一次工具调用的结果与策略信息。"""
    return {
        "tool": log.tool_name,
        "status": log.status,
        "input": log.tool_input or {},
        "result": log.tool_result or {},
        "policy": {
            "schema_version": log.tool_schema_version or TOOL_SCHEMA_VERSION,
            "risk_level": log.risk_level,
            "confirmation_policy": log.confirmation_policy,
            "confirmation_count": log.confirmation_count,
            "idempotency_key": log.idempotency_key,
            "replayed": True,
        },
    }
