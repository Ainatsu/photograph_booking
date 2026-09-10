"""Agent 统一能力契约（workflow 阶段 A）。

定义 capability 的输入/输出模型与统一结果信封 capability_result_v1：
只有通过 output schema 校验的 data 才允许进入后续 workflow context。
检索与灵感草稿能力复用既有契约模型，避免同一入参出现两份漂移定义。
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

CAPABILITY_SCHEMA_VERSION = "agent_capability_v1"
CAPABILITY_RESULT_SCHEMA_VERSION = "capability_result_v1"

CapabilityStatus = Literal["success", "empty", "waiting_async", "waiting_user", "failed"]


# ── 视觉能力入参 ─────────────────────────────────────────────────────────────


class VisionAttachment(BaseModel):
    """视觉能力的图片附件，对齐消息 metadata 中的附件结构。

    extra="allow"：现有附件还携带 thumb_url / attachment_index 等字段，
    能力层只消费 type / url / mime_type，其余原样透传。
    """

    model_config = ConfigDict(extra="allow")

    type: str
    url: str
    mime_type: str | None = None


def _only_image_attachments(value: Any) -> list[Any]:
    """只保留带 URL 的图片附件，非图片条目静默丢弃。"""
    if not isinstance(value, (list, tuple)):
        return []
    return [
        item
        for item in value
        if isinstance(item, dict) and item.get("type") == "image" and item.get("url")
    ]


class VisionSkillInput(BaseModel):
    """三个视觉 skill（分析/赏析/风格）的共用入参。"""

    model_config = ConfigDict(extra="forbid")

    conversation_id: int
    content: str | None = Field(default=None, max_length=4000)
    attachments: list[VisionAttachment] = Field(default_factory=list)

    @field_validator("attachments", mode="before")
    @classmethod
    def _keep_images(cls, value: Any) -> list[Any]:
        """规范化附件列表：只保留图片条目。"""
        return _only_image_attachments(value)


# ── 灵感草稿入参 ─────────────────────────────────────────────────────────────


class CreateInspirationDraftInput(BaseModel):
    """inspiration.create_draft 的入参：参考文本 + 受信参考图片。"""

    model_config = ConfigDict(extra="forbid")

    reference_text: str | None = Field(default=None, max_length=2000)
    images: list[VisionAttachment] = Field(default_factory=list)

    @field_validator("images", mode="before")
    @classmethod
    def _keep_images(cls, value: Any) -> list[Any]:
        """规范化图片列表：只保留图片条目。"""
        return _only_image_attachments(value)

    @model_validator(mode="after")
    def _require_image(self) -> "CreateInspirationDraftInput":
        """灵感草稿必须至少带一张参考图片。"""
        if not self.images:
            raise ValueError("reference_images_required")
        return self


# ── 能力输出模型 ─────────────────────────────────────────────────────────────


class ImageAnalysisData(BaseModel):
    """vision.analyze_image 的结构化输出，对齐 vision_analysis_v1。"""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["vision_analysis_v1"]
    summary: str
    style: list[str] = Field(default_factory=list)
    scene: list[str] = Field(default_factory=list)
    mood: list[str] = Field(default_factory=list)
    makeup: list[str] = Field(default_factory=list)
    lighting: list[str] = Field(default_factory=list)
    color: list[str] = Field(default_factory=list)
    composition: list[str] = Field(default_factory=list)
    search_terms: list[str] = Field(default_factory=list)
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    provider: dict[str, Any] = Field(default_factory=dict)
    # 派生检索词，供 workflow 模板 $context.image_analysis.search_query 使用。
    search_query: str = ""


class SkillReplyData(BaseModel):
    """vision.appreciate_image / vision.analyze_style 的自由文本输出。"""

    model_config = ConfigDict(extra="forbid")

    schema_version: str
    reply: str


class SearchData(BaseModel):
    """检索类能力的结构化输出，对齐 agent_search_tool_v1 的 result。"""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["agent_search_tool_v1"]
    resource_type: str
    count: int = Field(ge=0)
    resource_ids: list[Any] = Field(default_factory=list)
    items: list[dict[str, Any]] = Field(default_factory=list)
    criteria: dict[str, Any] = Field(default_factory=dict)
    diagnostics: dict[str, Any] = Field(default_factory=dict)


class InspirationDraftData(BaseModel):
    """inspiration.create_draft 的输出，对齐 create_inspiration_draft 的 result。"""

    model_config = ConfigDict(extra="forbid")

    created: bool
    inspiration_id: int | None = None
    status: str | None = None
    title: str | None = None
    cover_url: str | None = None


# ── 最终回复组装入参/输出（workflow 阶段 D） ─────────────────────────────────


class ComposeResponseInput(BaseModel):
    """agent.compose_response 的入参：前序步骤已过 output schema 校验的结构化结果。

    模板白名单保证这三个字段只能引用 $context 下的既有键，compose 不接受
    任意自然语言拼接，回复中的每个资源引用都来自 search 的真实 items。
    """

    model_config = ConfigDict(extra="forbid")

    user_request: str | None = Field(default=None, max_length=4000)
    appreciation: dict = Field(default_factory=dict)
    analysis: dict = Field(default_factory=dict)
    search: dict = Field(default_factory=dict)


class ComposeResponseData(BaseModel):
    """agent.compose_response 的结构化输出：最终回复正文 + 消息 metadata。"""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["agent_compose_response_v1"]
    content: str
    metadata: dict = Field(default_factory=dict)


# ── 灵感生成入参/输出（workflow 阶段 E：search_then_inspire） ────────────────


class InspirationGenerateInput(BaseModel):
    """inspiration.generate 的入参：参考文本 + 上一步 search 的真实 items。

    items 来自 $context.search.items（已过 output schema 校验），可用图片
    过滤由 adapter 复刻 legacy compound_workflow 分支完成。
    """

    model_config = ConfigDict(extra="forbid")

    reference_text: str | None = Field(default=None, max_length=2000)
    items: list[dict[str, Any]] = Field(default_factory=list)


class InspirationGenerateData(BaseModel):
    """inspiration.generate 的结构化输出。

    复用 create_inspiration_workflow 的回复正文与 metadata。字段名用
    flow_status：顶层 status 键会被 registry 剥离为信封状态，不能复用。
    无可用静态图是合法完成（flow_status=failed + error.code=
    no_usable_images），与阶段 D 空检索降级同模式。
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["inspiration_generate_v1"]
    flow_status: Literal["generating", "awaiting_reference_images", "failed"]
    content: str
    inspiration_id: int | None = None
    entry: dict[str, Any] | None = None
    inspiration_flow: dict[str, Any] = Field(default_factory=dict)
    active_task: dict[str, Any] | None = None
    error: dict[str, Any] | None = None


# ── 预订创建入参/输出（workflow 阶段 E：booking_flow 拆解） ──────────────────


class BookingCreateInput(BaseModel):
    """booking.create 的入参：预订流程的多轮状态由 run.input 驱动。

    slots 是跨轮合并后的预订槽位（摄影师/套餐/日期等）；task_state 是上一轮
    waiting 结果里的 task_state 快照（供 advance_booking_plan 推进计划）；
    confirmed 只有在调用方完成显式确认短语校验后才为 True。
    """

    model_config = ConfigDict(extra="forbid")

    user_request: str | None = Field(default=None, max_length=4000)
    items: list[dict[str, Any]] = Field(default_factory=list)
    slots: dict[str, Any] = Field(default_factory=dict)
    intent_slots: dict[str, Any] = Field(default_factory=dict)
    task_state: dict[str, Any] | None = None
    confirmed: bool = False
    first_turn: bool = False
    vision_analysis: dict[str, Any] | None = None
    vision_reused_context: bool = False
    search_criteria: dict[str, Any] = Field(default_factory=dict)


class BookingCreateData(BaseModel):
    """booking.create 的结构化输出：阶段 stage + legacy 同款回复正文与 metadata。

    stage 取自结果 metadata.task_state.status（awaiting_package /
    awaiting_date / awaiting_confirmation / completed / failed）；
    awaiting_* 阶段以 waiting_user 信封返回，create 步骤暂停等待用户。
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["booking_create_v1"]
    stage: Literal[
        "awaiting_package", "awaiting_date", "awaiting_confirmation",
        "completed", "failed",
    ]
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


# ── 统一结果信封 ─────────────────────────────────────────────────────────────


class CapabilityError(BaseModel):
    """能力失败的错误描述。"""

    model_config = ConfigDict(extra="forbid")

    code: str
    message: str = ""
    retryable: bool = False


class CapabilityProvenance(BaseModel):
    """结果溯源信息。

    provider 存放原始 provider metadata（非仅 model 子键），
    供主服务组装 message_metadata 时还原既有结构。
    """

    model_config = ConfigDict(extra="forbid")

    capability: str
    attempt: int = Field(default=1, ge=1)
    duration_ms: int = Field(default=0, ge=0)
    tool_name: str | None = None
    provider: dict[str, Any] = Field(default_factory=dict)


class CapabilityResult(BaseModel):
    """统一能力结果信封 capability_result_v1。

    status=success/empty 表示能力执行成功（empty 是“无命中”的合法结果）；
    data 只有通过 output schema 校验才会出现在这里。
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["capability_result_v1"] = CAPABILITY_RESULT_SCHEMA_VERSION
    capability: str
    status: CapabilityStatus
    data: dict[str, Any] | None = None
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error: CapabilityError | None = None
    provenance: CapabilityProvenance | None = None

    @property
    def is_success(self) -> bool:
        """能力是否成功执行（含空结果）。"""
        return self.status in {"success", "empty"}

    def as_dict(self) -> dict[str, Any]:
        """序列化为 JSON 安全字典。"""
        return self.model_dump(mode="json", exclude_none=True)
