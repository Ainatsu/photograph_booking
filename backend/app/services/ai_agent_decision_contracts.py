"""统一 Agent 决策协议与 search_* 工具入参契约（阶段B）。

阶段A 之前的路由是「分类器给意图 → 后端 if/elif 决定做什么」：意图名和工具名是两套词表，
新增一个能力要同时改规则分类器、策略表和编排分支，模型也无法表达“我需要先问一句”。

阶段B 把这一层收敛成一个决策协议（见 docs/codex-agent-llm-tool-routing-refactor-guide.md §3、§4）：
模型只输出 mode + tool + arguments，后端负责参数校验、权限判断、状态合并和真实执行。

本模块只定义契约与纯函数：
- 四种决策模式：chat / tool_call / clarify / confirm；
- search_* 工具的严格入参模型（extra="forbid"、风格同义词归一化、拒绝整句与指代词）；
- 后端独占参数的剥离：排除哪些资源 ID 由 search_context 决定，不接受模型自己编。

策略判断在 ai_tool_policy_service，工具执行在 ai_search_tool_service，
模型调用与影子对比在 ai_agent_decision_service。
"""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.app.services.ai_domain_synonyms import normalize_terms


DECISION_SCHEMA_VERSION = "agent_decision_v1"
DECISION_TRACE_VERSION = "agent_decision_trace_v1"

DECISION_MODES = ("chat", "tool_call", "clarify", "confirm")


class GetShootContextInput(BaseModel):
    """地点、日期与拍摄时段的严格入参。"""

    model_config = ConfigDict(extra="forbid")

    location_text: str = Field(min_length=2, max_length=120)
    location_address: str | None = Field(default=None, max_length=240)
    shoot_date: date
    start_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    duration_minutes: int = Field(default=120, gt=0, le=1440)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    @model_validator(mode="after")
    def _coordinates_must_be_paired(self) -> "GetShootContextInput":
        """校验经纬度必须成对提供，并校验开始时间的真实时钟范围。"""
        # 单独的经度或纬度无法定位；若没有完整坐标，则统一回退到地点文本解析。
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude_longitude_must_be_provided_together")
        if self.start_time is not None:
            # 正则只约束字符串形状，这里再校验真实的时钟取值范围。
            hour, minute = (int(value) for value in self.start_time.split(":"))
            if hour > 23 or minute > 59:
                raise ValueError("invalid_start_time")
        return self

# 后端独占的参数：模型即使输出也一律丢弃并记入审计。
# 排除列表来自上一轮 search_context 的真实推荐记录，模型无法知道平台的资源 ID（§5.1）。
BACKEND_OWNED_ARGUMENT_FIELDS = ("exclude_resource_ids",)

# 短条件（城市、摄影师名、风格）的长度上限：超过就说明模型把整句话塞了进来。
MAX_CONDITION_LENGTH = 24
MAX_QUERY_TEXT_LENGTH = 120
MAX_STYLE_TERMS = 5
MAX_EXCLUDE_IDS = 50
MAX_QUESTION_LENGTH = 120

# 出现这些成分说明这是一句话而不是一个条件值。
_SENTENCE_MARKERS = (
    "帮我",
    "请",
    "我想",
    "我要",
    "推荐",
    "搜索",
    "查找",
    "找一",
    "找个",
    "预约",
    "发布",
    "关注",
    "，",
    ",",
    "。",
    "？",
    "?",
    "！",
    "!",
    "\n",
)

# 对话控制词与指代词：它们是对上一轮结果的反馈，不是资源特征（§5.1、阶段A 同一条约束）。
_CONTROL_TERMS = (
    "这个",
    "那个",
    "刚才",
    "上一个",
    "上个",
    "换一个",
    "换个",
    "再来",
    "别的",
    "其他的",
    "其它的",
    "不满意",
    "不太满意",
    "不喜欢",
    "不太喜欢",
    "不合适",
    "不行",
    "随便",
    "任意",
    "未知",
)


def clean_condition_text(value: Any, *, max_length: int = MAX_CONDITION_LENGTH) -> str | None:
    """清理模型给出的短条件值：拒绝整句、指代词、控制词和超长文本。"""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if len(text) < 2 or len(text) > max_length:
        return None
    if any(marker in text for marker in _SENTENCE_MARKERS):
        return None
    if any(term in text for term in _CONTROL_TERMS):
        return None
    return text


def clean_style_terms(value: Any) -> list[str]:
    """风格列表：逐项清理后做同义词归一化（“婚庆/婚宴/婚礼跟拍”→“婚礼”）。"""
    if isinstance(value, str):
        raw: list[Any] = [value]
    elif isinstance(value, (list, tuple)):
        raw = list(value)
    else:
        return []
    cleaned = [
        text
        for text in (clean_condition_text(item, max_length=16) for item in raw)
        if text
    ]
    return normalize_terms(cleaned)[:MAX_STYLE_TERMS]


def clean_resource_ids(value: Any) -> list[str]:
    """资源 ID 列表：只保留非空字符串化 ID，去重并限长。"""
    if not isinstance(value, (list, tuple)):
        return []
    result: list[str] = []
    for item in value:
        if isinstance(item, bool) or item is None:
            continue
        text = str(item).strip()
        if not text or text in result:
            continue
        result.append(text)
    return result[:MAX_EXCLUDE_IDS]


def sanitize_arguments(arguments: Any) -> tuple[dict[str, Any], list[str]]:
    """剥离后端独占参数，返回 (可用参数, 被丢弃的字段名)。

    模型编造的资源 ID 一律不进入检索层：排除列表只能由后端从 search_context 生成。
    """
    payload = dict(arguments or {}) if isinstance(arguments, dict) else {}
    dropped = [field for field in BACKEND_OWNED_ARGUMENT_FIELDS if field in payload]
    for field in dropped:
        payload.pop(field, None)
    return payload, dropped


def single_question(text: Any) -> str | None:
    """一轮最多一个追问（§5.3）：只保留第一个问句，多问一律截断。"""
    if not isinstance(text, str):
        return None
    normalized = text.strip().replace("\n", " ")
    if not normalized:
        return None
    for index, char in enumerate(normalized):
        if char in "？?":
            return normalized[: index + 1][:MAX_QUESTION_LENGTH]
    return normalized[:MAX_QUESTION_LENGTH]


# ── search_* 工具入参 ───────────────────────────────────────────────────────


class SearchInputBase(BaseModel):
    """检索类工具的公共入参。

    extra="forbid"：模型不能自己发明字段（例如 photographer_id、package_id），
    §5.1 要求平台实体 ID 只能由后端从真实候选里给出。
    """

    model_config = ConfigDict(extra="forbid")

    query_text: str | None = Field(default=None, max_length=MAX_QUERY_TEXT_LENGTH)
    city: str | None = None
    styles: list[str] = Field(default_factory=list)
    budget_min: float | None = Field(default=None, ge=0)
    budget_max: float | None = Field(default=None, ge=0)
    limit: int = Field(default=3, ge=1, le=10)
    exclude_resource_ids: list[str] = Field(default_factory=list)

    @field_validator("query_text", mode="before")
    @classmethod
    def _normalize_query_text(cls, value: Any) -> str | None:
        """规范化搜索文本：去空白、折叠换行并限长。"""
        if not isinstance(value, str):
            return None
        text = value.strip().replace("\n", " ")
        return text[:MAX_QUERY_TEXT_LENGTH] or None

    @field_validator("city", mode="before")
    @classmethod
    def _normalize_city(cls, value: Any) -> str | None:
        """规范化城市字段：拒绝整句、指代词与超长文本。"""
        return clean_condition_text(value)

    @field_validator("styles", mode="before")
    @classmethod
    def _normalize_styles(cls, value: Any) -> list[str]:
        """规范化风格列表：逐项清理并做同义词归一化。"""
        return clean_style_terms(value)

    @field_validator("exclude_resource_ids", mode="before")
    @classmethod
    def _normalize_exclude_ids(cls, value: Any) -> list[str]:
        """规范化排除资源 ID 列表：去重并限长。"""
        return clean_resource_ids(value)

    @model_validator(mode="after")
    def _check_budget_range(self) -> "SearchInputBase":
        """校验预算上下限：最小值不得大于最大值。"""
        if (
            self.budget_min is not None
            and self.budget_max is not None
            and self.budget_min > self.budget_max
        ):
            raise ValueError("budget_min_greater_than_budget_max")
        return self


class SearchPhotographersInput(SearchInputBase):
    """按城市、风格、预算检索已上架摄影师。"""

    photographer_name: str | None = None

    @field_validator("photographer_name", mode="before")
    @classmethod
    def _normalize_name(cls, value: Any) -> str | None:
        """规范化摄影师名称：清理并拒绝整句与指代词。"""
        return clean_condition_text(value)


class SearchPortfolioItemsInput(SearchInputBase):
    """按城市、风格检索作品/样片。"""

    photographer_name: str | None = None

    @field_validator("photographer_name", mode="before")
    @classmethod
    def _normalize_name(cls, value: Any) -> str | None:
        """规范化摄影师名称：清理并拒绝整句与指代词。"""
        return clean_condition_text(value)


class SearchPackagesInput(SearchInputBase):
    """按城市、风格、预算、是否含妆造检索套餐。"""

    photographer_name: str | None = None
    requires_makeup: bool | None = None

    @field_validator("photographer_name", mode="before")
    @classmethod
    def _normalize_name(cls, value: Any) -> str | None:
        """规范化摄影师名称：清理并拒绝整句与指代词。"""
        return clean_condition_text(value)


class SearchWebInput(BaseModel):
    """Strict public web-search input owned by the backend."""

    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=2, max_length=300)
    limit: int = Field(default=5, ge=1, le=5)
    language: Literal["zh-CN", "zh-TW", "en-US"] = "zh-CN"
    freshness: Literal["day", "week", "month", "year"] | None = None
    include_domains: list[str] = Field(default_factory=list, max_length=20)
    exclude_domains: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("query", mode="before")
    @classmethod
    def _normalize_query(cls, value: Any) -> str:
        if not isinstance(value, str):
            raise ValueError("query_required")
        return " ".join(value.strip().split())

    @field_validator("include_domains", "exclude_domains", mode="before")
    @classmethod
    def _normalize_domains(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, (list, tuple)):
            raise ValueError("domains_must_be_list")
        domains: list[str] = []
        for item in value:
            domain = str(item).strip().lower()
            if domain and "/" not in domain and ":" not in domain and domain not in domains:
                domains.append(domain)
        return domains[:20]


class SearchProjectsInput(SearchInputBase):
    """检索可应邀的企划（拍摄需求），仅摄影师可用。"""


SEARCH_TOOL_INPUT_MODELS: dict[str, type[BaseModel]] = {
    "search_photographers": SearchPhotographersInput,
    "search_portfolio_items": SearchPortfolioItemsInput,
    "search_packages": SearchPackagesInput,
    "search_projects": SearchProjectsInput,
    "search_web": SearchWebInput,
}


# ── 决策协议 ────────────────────────────────────────────────────────────────


class AgentDecision(BaseModel):
    """LLM 的一次路由决策。

    模型只描述“下一步做什么”，不描述“结果是什么”：
    - chat：直接回答，不需要平台数据；
    - tool_call：调用某个工具（读操作由后端直接执行，写操作交既有确认流程）；
    - clarify：缺少关键条件，需要向用户追问一个问题；
    - confirm：已经能确定要做的写操作，但必须先让用户确认。
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["agent_decision_v1"] = DECISION_SCHEMA_VERSION
    mode: Literal["chat", "tool_call", "clarify", "confirm"]
    tool: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    needs_clarification: bool = False
    question: str | None = None
    confidence: float = Field(ge=0, le=1)
    reason: str | None = Field(default=None, max_length=200)

    @field_validator("tool", mode="before")
    @classmethod
    def _normalize_tool(cls, value: Any) -> str | None:
        """规范化工具名：去空白，空串视为未提供。"""
        if not isinstance(value, str):
            return None
        return value.strip() or None

    @field_validator("arguments", mode="before")
    @classmethod
    def _normalize_arguments(cls, value: Any) -> dict[str, Any]:
        """规范化工具参数：非字典一律视为空字典。"""
        return dict(value) if isinstance(value, dict) else {}

    @field_validator("reason", mode="before")
    @classmethod
    def _normalize_reason(cls, value: Any) -> str | None:
        """规范化决策理由：折叠空白并限长 200。"""
        if not isinstance(value, str):
            return None
        return value.strip().replace("\n", " ")[:200] or None

    @model_validator(mode="after")
    def _enforce_mode_shape(self) -> "AgentDecision":
        """按模式强制决策形状：工具调用必须带工具，澄清必须带问题。"""
        if self.mode in {"tool_call", "confirm"}:
            if not self.tool:
                raise ValueError(f"{self.mode}_requires_tool")
            self.needs_clarification = False
            self.question = None
        else:
            # chat / clarify 不允许携带工具，避免“边聊边偷偷调用”的歧义状态。
            self.tool = None
            self.arguments = {}
        if self.mode == "clarify":
            question = single_question(self.question)
            if not question:
                raise ValueError("clarify_requires_question")
            self.question = question
            self.needs_clarification = True
        elif self.mode == "chat":
            self.needs_clarification = False
            self.question = None
        return self

    def as_dict(self) -> dict[str, Any]:
        """将决策序列化为 JSON 兼容字典。"""
        return self.model_dump(mode="json")


def decision_condition_slots(decision: AgentDecision | None) -> dict[str, Any]:
    """从决策参数里取出可以和意图槽位对比的条件字段（用于影子对比）。"""
    arguments = (decision.arguments if decision else None) or {}
    slots: dict[str, Any] = {}
    if arguments.get("city"):
        slots["city"] = arguments["city"]
    if arguments.get("styles"):
        slots["styles"] = list(arguments["styles"])
    for field in ("budget_min", "budget_max", "limit", "requires_makeup"):
        if arguments.get(field) is not None:
            slots[field] = arguments[field]
    return slots
