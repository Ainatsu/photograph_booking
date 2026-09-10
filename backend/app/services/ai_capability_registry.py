"""Agent 统一能力注册表与执行入口（workflow 阶段 A）。

execute_capability 是主服务与未来 Workflow Runtime 的唯一能力调用方式：
- 未注册能力、非法入参、adapter 异常、输出校验失败统一映射为
  capability_result_v1 的 failed 信封，错误码可观测；
- 只有通过 output schema 校验的 data 才出现在结果里，供阶段 B/C
  持久化并注入 workflow context。

超时与重试本轮只在 spec 中声明策略，运行时强制归阶段 C。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Awaitable, Callable, Literal, Type

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from backend.app.services.ai_agent_decision_contracts import (
    SearchPackagesInput,
    SearchPhotographersInput,
    SearchPortfolioItemsInput,
)
from backend.app.services.ai_capability_contracts import (
    CAPABILITY_SCHEMA_VERSION,
    CapabilityError,
    CapabilityProvenance,
    CapabilityResult,
    CapabilityStatus,
    ComposeResponseData,
    ComposeResponseInput,
    CreateInspirationDraftInput,
    BookingCreateData,
    BookingCreateInput,
    ImageAnalysisData,
    InspirationDraftData,
    InspirationGenerateData,
    InspirationGenerateInput,
    SearchData,
    SkillReplyData,
    VisionSkillInput,
)
from backend.app.services import ai_capability_adapters as adapters


CapabilityAdapter = Callable[[Session, Any, Any], Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class CapabilitySpec:
    """能力规格：输入/输出模型、执行模式与策略声明。"""

    name: str
    kind: Literal["skill", "tool"]
    input_model: Type[BaseModel]
    output_model: Type[BaseModel]
    adapter: CapabilityAdapter
    execution_mode: Literal["sync", "async"] = "sync"
    retryable: bool = False
    timeout_seconds: int = 30
    requires_confirmation: bool = False
    allowed_roles: tuple[str, ...] = ()
    idempotent: bool = False
    description: str = ""
    schema_version: str = CAPABILITY_SCHEMA_VERSION

    @property
    def requires_user_context(self) -> bool:
        """执行该能力是否必须提供 user 上下文。"""
        return self.kind == "tool"


CAPABILITY_REGISTRY: dict[str, CapabilitySpec] = {
    "vision.analyze_image": CapabilitySpec(
        name="vision.analyze_image",
        kind="skill",
        input_model=VisionSkillInput,
        output_model=ImageAnalysisData,
        adapter=adapters.vision_analyze_image,
        execution_mode="sync",
        retryable=False,
        timeout_seconds=60,
        description="对用户上传的图片做结构化视觉分析，产出风格、场景、情绪等标签与派生检索词。",
    ),
    "vision.appreciate_image": CapabilitySpec(
        name="vision.appreciate_image",
        kind="skill",
        input_model=VisionSkillInput,
        output_model=SkillReplyData,
        adapter=adapters.vision_appreciate_image,
        execution_mode="sync",
        retryable=False,
        timeout_seconds=60,
        description="赏析参考图作品，输出自由文本的摄影视角解读。",
    ),
    "vision.analyze_style": CapabilitySpec(
        name="vision.analyze_style",
        kind="skill",
        input_model=VisionSkillInput,
        output_model=SkillReplyData,
        adapter=adapters.vision_analyze_style,
        execution_mode="sync",
        retryable=False,
        timeout_seconds=60,
        description="分析参考图风格 DNA，输出逐层结论的自由文本。",
    ),
    "portfolio.search": CapabilitySpec(
        name="portfolio.search",
        kind="tool",
        input_model=SearchPortfolioItemsInput,
        output_model=SearchData,
        adapter=adapters.run_resource_search,
        execution_mode="sync",
        retryable=True,
        timeout_seconds=15,
        description="按城市、风格、摄影师名等条件检索作品/样片。",
    ),
    "photographer.search": CapabilitySpec(
        name="photographer.search",
        kind="tool",
        input_model=SearchPhotographersInput,
        output_model=SearchData,
        adapter=adapters.run_resource_search,
        execution_mode="sync",
        retryable=True,
        timeout_seconds=15,
        description="按城市、风格、预算等条件检索已上架摄影师。",
    ),
    "package.search": CapabilitySpec(
        name="package.search",
        kind="tool",
        input_model=SearchPackagesInput,
        output_model=SearchData,
        adapter=adapters.run_resource_search,
        execution_mode="sync",
        retryable=True,
        timeout_seconds=15,
        description="按城市、风格、预算、是否含妆造检索套餐。",
    ),
    "inspiration.create_draft": CapabilitySpec(
        name="inspiration.create_draft",
        kind="tool",
        input_model=CreateInspirationDraftInput,
        output_model=InspirationDraftData,
        adapter=adapters.create_inspiration_draft_adapter,
        execution_mode="sync",
        retryable=False,
        timeout_seconds=15,
        requires_confirmation=False,
        idempotent=True,
        description="从受信参考图片创建私有灵感草稿（复用既有工具策略、审计与幂等机制）。",
    ),
    "agent.compose_response": CapabilitySpec(
        name="agent.compose_response",
        kind="skill",
        input_model=ComposeResponseInput,
        output_model=ComposeResponseData,
        adapter=adapters.compose_response_adapter,
        execution_mode="sync",
        retryable=False,
        timeout_seconds=10,
        description="汇总前序步骤通过 output schema 校验的结构化结果，组装最终用户回复与消息 metadata。",
    ),
    "inspiration.generate": CapabilitySpec(
        name="inspiration.generate",
        kind="tool",
        input_model=InspirationGenerateInput,
        output_model=InspirationGenerateData,
        adapter=adapters.inspiration_generate,
        execution_mode="sync",
        retryable=False,
        timeout_seconds=30,
        idempotent=True,
        description="包装 create_inspiration_workflow：从检索结果的真实参考图创建灵感草稿并排队异步生成（阶段 E search_then_inspire）。",
    ),
    "booking.create": CapabilitySpec(
        name="booking.create",
        kind="tool",
        input_model=BookingCreateInput,
        output_model=BookingCreateData,
        adapter=adapters.booking_create,
        execution_mode="sync",
        retryable=False,
        timeout_seconds=15,
        requires_confirmation=True,
        idempotent=True,
        description="预订流程的创建步骤：复刻 booking_agent_result 阶段分支，缺槽位/待确认时以 waiting_user 暂停，显式确认后调用 create_booking 工具（阶段 E）。",
    ),
}


def get_capability_spec(name: str) -> CapabilitySpec | None:
    """按名称查找能力规格，未注册时返回 None。"""
    return CAPABILITY_REGISTRY.get(name)


def list_capabilities() -> list[CapabilitySpec]:
    """列出全部已注册能力（供未来 planner / runtime 使用）。"""
    return list(CAPABILITY_REGISTRY.values())


def _failed_result(
    capability: str,
    *,
    error_code: str,
    message: str,
    retryable: bool = False,
    attempt: int = 1,
    duration_ms: int = 0,
    tool_name: str | None = None,
    provider: dict[str, Any] | None = None,
) -> CapabilityResult:
    """构造失败的统一信封。"""
    return CapabilityResult(
        capability=capability,
        status="failed",
        error=CapabilityError(code=error_code, message=message, retryable=retryable),
        provenance=CapabilityProvenance(
            capability=capability,
            attempt=attempt,
            duration_ms=duration_ms,
            tool_name=tool_name,
            provider=provider or {},
        ),
    )


def _validate_no_unknown_fields(
    spec: CapabilitySpec,
    input_data: dict[str, Any],
) -> None:
    """拒绝 input 中未在 input_model 声明的字段。

    SearchInputBase 是 extra="forbid"，Pydantic 自身会报错，但报错信息
    把校验失败和未知字段混在一起；这里先显式区分未知字段，错误码更可观测。
    """
    known = set(spec.input_model.model_fields)
    unknown = set(input_data) - known
    if unknown:
        raise KeyError(f"unknown_fields:{','.join(sorted(unknown))}")


async def execute_capability(
    db: Session,
    *,
    name: str,
    input: dict[str, Any],
    user: Any = None,
    user_id: int | None = None,
    conversation_id: int | None = None,
    message_id: int | None = None,
    attempt: int = 1,
    idempotency_key: str | None = None,
    vision_analysis: dict[str, Any] | None = None,
    image_attachments: list[dict[str, Any]] | None = None,
    request_content: str | None = None,
    commit: bool = True,
) -> CapabilityResult:
    """统一执行一个已注册能力并返回 capability_result_v1 信封。"""
    spec = CAPABILITY_REGISTRY.get(name)
    if spec is None:
        return _failed_result(
            name,
            error_code="unknown_capability",
            message=f"capability not registered: {name}",
        )

    tool_name = getattr(spec.adapter, "__name__", None)

    # ── 入参校验与归一化 ──
    try:
        _validate_no_unknown_fields(spec, input or {})
        normalized_input = spec.input_model.model_validate(input or {})
    except KeyError as exc:
        return _failed_result(
            name,
            error_code="invalid_input",
            message=str(exc),
            attempt=attempt,
            tool_name=tool_name,
        )
    except ValidationError as exc:
        return _failed_result(
            name,
            error_code="invalid_input",
            message=str(exc.errors()[:5]),
            attempt=attempt,
            tool_name=tool_name,
        )

    context: dict[str, Any] = {
        "capability_name": spec.name,
        "user": user,
        "user_id": user_id,
        "conversation_id": conversation_id,
        "message_id": message_id,
        "idempotency_key": idempotency_key,
        "vision_analysis": vision_analysis,
        "image_attachments": image_attachments,
        "request_content": request_content,
        "commit": commit,
    }

    # ── 执行 adapter ──
    started_at = perf_counter()
    try:
        adapter_output = await spec.adapter(db, normalized_input, context=context)
    except Exception as exc:
        duration_ms = round((perf_counter() - started_at) * 1000)
        return _failed_result(
            name,
            error_code="capability_error",
            message=str(exc)[:500],
            retryable=spec.retryable,
            attempt=attempt,
            duration_ms=duration_ms,
            tool_name=tool_name,
        )
    duration_ms = round((perf_counter() - started_at) * 1000)

    # adapter 输出中的信封级字段先剥离，剩余部分才进入 output schema 校验。
    adapter_status: CapabilityStatus | None = adapter_output.pop("status", None)
    artifacts = adapter_output.pop("artifacts", None) or []
    warnings = adapter_output.pop("warnings", None) or []
    provider_metadata = adapter_output.pop("provider_metadata", None) or {}

    if adapter_status == "failed":
        # adapter 自报失败时结果不符合 output schema（可能只带 error 字段），
        # 不再走输出校验，直接映射为 failed 信封。
        return _failed_result(
            name,
            error_code="capability_error",
            message=str(adapter_output.get("error") or "capability reported failure"),
            retryable=spec.retryable,
            attempt=attempt,
            duration_ms=duration_ms,
            tool_name=tool_name,
            provider=provider_metadata,
        )

    adapter_extra = {
        key: value
        for key, value in adapter_output.items()
        if key not in _ADAPTER_TRANSPARENT_KEYS
    }

    # ── 输出校验：只有通过 output schema 的 data 才能进 workflow context ──
    try:
        validated_data = spec.output_model.model_validate(adapter_extra)
    except ValidationError as exc:
        return _failed_result(
            name,
            error_code="invalid_output",
            message=str(exc.errors()[:5]),
            attempt=attempt,
            duration_ms=duration_ms,
            tool_name=tool_name,
            provider=provider_metadata,
        )

    data = validated_data.model_dump(mode="json")

    status: CapabilityStatus = "success"
    if spec.output_model is SearchData:
        status = "success" if validated_data.count > 0 else "empty"
    elif adapter_status == "empty":
        status = "empty"
    elif adapter_status in ("waiting_user", "waiting_async"):
        # adapter 自报等待（阶段 E booking.create）：数据已过 output schema
        # 校验并随信封持久化，Runtime 据此把步骤/run 置为 waiting 状态。
        status = adapter_status

    return CapabilityResult(
        capability=spec.name,
        status=status,
        data=data,
        artifacts=artifacts,
        warnings=warnings,
        provenance=CapabilityProvenance(
            capability=spec.name,
            attempt=attempt,
            duration_ms=duration_ms,
            tool_name=tool_name,
            provider=provider_metadata,
        ),
    )


# adapter 输出中不参与 output schema 校验、只透传给调用方的字段。
_ADAPTER_TRANSPARENT_KEYS = frozenset({
    "retrieval",
    "payload",
    "replayed",
    "tool_input",
    "duration_ms",
})
