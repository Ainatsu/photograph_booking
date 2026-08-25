"""AI 智能体追踪服务：记录智能体执行轨迹并输出质量看板指标。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.models.ai_conversation import AgentActionLog, AgentRetrievalLog
from backend.app.models.ai_production import AgentTrace, AIIndexJob
from backend.app.services.ai_tool_policy_service import TOOL_REGISTRY


# 阶段C §4-C.3 要观察的"错误工具率"：模型选了一个后端根本不能执行的工具。
# 这些前缀都来自 authorize_tool_call / resolve_decision_plan 的错误码。
WRONG_TOOL_REASON_CODES = frozenset({
    "unregistered_tool",
    "tool_not_available",
    "tool_not_selectable",
    "tool_forbidden",
    "role_not_allowed",
    "invalid_arguments",
    "unsupported_tool",
    "missing_active_task",
    "missing_tool",
})

# 写操作被决策层拦下的原因：阶段B/C 里这个比例应当恒为 1.0，
# 一旦下降说明有写工具绕过了既有确认流程（§5.2）。
WRITE_BLOCK_REASON_CODES = frozenset({
    "proposal_only_tool",
    "writes_not_allowed",
    "confirmation_required",
})

WRITE_TOOL_NAMES = frozenset(name for name, spec in TOOL_REGISTRY.items() if spec.is_write)


def _reason_code(value: Any) -> str:
    """错误码只取 ":" 前的前缀，避免工具名、置信度把分桶打散。"""
    return str(value or "").split(":")[0].strip()


def _rate(numerator: int, denominator: int) -> float:
    """计算比率并保留四位小数，分母为 0 时返回 0。"""
    return round(numerator / denominator, 4) if denominator else 0.0


def decision_rollout_metrics(flags_list: list[dict[str, Any]]) -> dict[str, Any]:
    """阶段C §4-C.3 的灰度五项指标（外加一个分类器省略率）。

    全部从 AgentTrace.quality_flags 计算，看板与离线评估共用同一套定义，
    避免"两个地方算出两个数"。
    """
    decision_flags = [flags for flags in flags_list if flags.get("decision_routing_mode")]
    tool_flags = [flags for flags in flags_list if flags.get("tool_call_tool")]
    proposals = [flags for flags in decision_flags if flags.get("decision_tool")]
    wrong_tool = [
        flags
        for flags in proposals
        if _reason_code(
            flags.get("decision_not_applied_reason") or flags.get("decision_fallback_reason")
        )
        in WRONG_TOOL_REASON_CODES
        or flags.get("tool_call_status") == "failed"
    ]
    # 写操作提案：模型点名写工具，或者直接给出 confirm 模式。
    write_proposals = [
        flags
        for flags in decision_flags
        if flags.get("decision_tool") in WRITE_TOOL_NAMES or flags.get("decision_mode") == "confirm"
    ]
    write_blocked = [
        flags
        for flags in write_proposals
        if not flags.get("decision_applied")
        and (
            _reason_code(
                flags.get("decision_not_applied_reason") or flags.get("decision_fallback_reason")
            )
            in WRITE_BLOCK_REASON_CODES
            or _reason_code(flags.get("decision_not_applied_reason")) == "legacy_flow_active"
        )
    ]
    recommended = [flags for flags in flags_list if flags.get("recommended_count")]
    refined = [flags for flags in recommended if flags.get("recommendation_refinement")]
    routed = [flags for flags in flags_list if flags.get("routing_mode")]
    return {
        "tool_calls": len(tool_flags),
        # 工具调用成功率 / 无结果率 / 报错率：三者互斥，加起来是 1。
        "tool_success_rate": _rate(
            sum(1 for flags in tool_flags if flags.get("tool_call_status") == "success"),
            len(tool_flags),
        ),
        "no_result_rate": _rate(
            sum(1 for flags in tool_flags if flags.get("tool_call_status") == "empty"),
            len(tool_flags),
        ),
        "tool_error_rate": _rate(
            sum(1 for flags in tool_flags if flags.get("tool_call_status") == "failed"),
            len(tool_flags),
        ),
        "tool_proposals": len(proposals),
        "wrong_tool_rate": _rate(len(wrong_tool), len(proposals)),
        "recommendation_turns": len(recommended),
        "repeat_recommendation_rate": _rate(
            sum(1 for flags in recommended if flags.get("repeat_recommendation")),
            len(recommended),
        ),
        "repeat_after_refinement_rate": _rate(
            sum(1 for flags in refined if flags.get("repeat_recommendation")),
            len(refined),
        ),
        "write_proposals": len(write_proposals),
        "write_block_rate": _rate(len(write_blocked), len(write_proposals)),
        "classifier_skip_rate": _rate(
            sum(1 for flags in routed if flags.get("routing_classifier_skipped")),
            len(routed),
        ),
    }


def rollout_coverage(flags_list: list[dict[str, Any]]) -> dict[str, Any]:
    """灰度覆盖情况：多少流量真的落进了目标模式，以及各模式的分布。"""
    routed = [flags for flags in flags_list if flags.get("routing_mode")]
    modes: dict[str, int] = {}
    reasons: dict[str, int] = {}
    for flags in routed:
        mode = str(flags.get("routing_mode"))
        modes[mode] = modes.get(mode, 0) + 1
        reason = str(flags.get("routing_reason") or "unknown")
        reasons[reason] = reasons.get(reason, 0) + 1
    return {
        "target_mode": settings.AGENT_ROUTING_MODE,
        "baseline_mode": settings.AGENT_ROUTING_BASELINE_MODE,
        "percent": settings.AGENT_ROUTING_ROLLOUT_PERCENT,
        "unit": settings.AGENT_ROUTING_ROLLOUT_UNIT,
        "total": len(routed),
        "coverage_rate": _rate(
            sum(1 for flags in routed if flags.get("routing_in_rollout")), len(routed)
        ),
        "modes": dict(sorted(modes.items())),
        "reasons": dict(sorted(reasons.items(), key=lambda item: item[1], reverse=True)),
    }


def record_agent_trace(
    db: Session,
    *,
    user_id: int,
    conversation_id: int,
    user_message_id: int,
    assistant_message_id: int,
    intent: dict[str, Any],
    metadata: dict[str, Any],
    total_latency_ms: int,
) -> AgentTrace:
    """记录一次智能体执行轨迹，聚合质量标志并持久化。"""
    model = metadata.get("model") or {}
    fallback = metadata.get("fallback") or {}
    retrieval = metadata.get("retrieval") or {}
    diagnostics = retrieval.get("diagnostics") or {}
    citation = metadata.get("citation_policy") or {}
    allowed_ids = citation.get("allowed_resource_ids") or {}
    referenced_count = sum(len(values or []) for values in allowed_ids.values())
    quality_flags = {
        "has_retrieval": bool(retrieval),
        "has_citations": referenced_count > 0,
        "empty_citation_after_retrieval": bool(retrieval) and referenced_count == 0,
        "multimodal": bool((diagnostics.get("multimodal") or {}).get("enabled")),
        # 模型不可用时走的降级回复（DegradedAIProvider）：这类回复不是 agent 答错，
        # 而是服务侧故障，必须能在看板上单独看到，不然会被当成质量问题去查路由。
        "provider_degraded": bool(metadata.get("degraded")),
    }
    provenance = metadata.get("context_provenance") or {}
    if provenance:
        quality_flags["active_task_id"] = provenance.get("active_task_id")
        quality_flags["active_task_type"] = provenance.get("active_task_type")
        quality_flags["workspace_source"] = provenance.get("workspace_source")
        quality_flags["workspace_revision"] = provenance.get("workspace_revision")
        quality_flags["previous_search_task_id"] = provenance.get("previous_search_task_id")
        quality_flags["referenced_episode_ids"] = provenance.get("referenced_episode_ids") or []
        quality_flags["long_term_memory_ids"] = provenance.get("long_term_memory_ids") or []
        quality_flags["task_transition"] = provenance.get("task_transition") or "none"
        quality_flags["stale_workspace_discarded"] = bool(provenance.get("stale_workspace_discarded"))
        quality_flags["task_type_mismatch"] = bool(provenance.get("task_type_mismatch"))
        quality_flags["cross_task_slots_blocked"] = provenance.get("cross_task_slots_blocked") or []
        quality_flags["context_sources"] = provenance.get("context_sources") or []
    # 意图分类诊断
    intent_classification = metadata.get("intent_classification") or {}
    if intent_classification:
        quality_flags["classifier_mode"] = intent_classification.get("mode")
        quality_flags["classifier_chosen_parser"] = intent_classification.get("chosen_parser")
        quality_flags["classifier_agreement"] = intent_classification.get("agreement")
        quality_flags["classifier_fallback"] = intent_classification.get("fallback_reason") is not None
        quality_flags["classifier_latency_ms"] = intent_classification.get("latency_ms")
    # 统一决策层诊断（阶段B §5.5）：灰度期要能按 routing_mode 统计接管率与回退原因。
    decision = metadata.get("agent_decision") or {}
    if decision:
        shadow_diff = decision.get("shadow_diff") or {}
        plan = decision.get("plan") or {}
        quality_flags["decision_routing_mode"] = decision.get("routing_mode")
        quality_flags["decision_parser"] = decision.get("parser")
        quality_flags["decision_mode"] = decision.get("mode")
        quality_flags["decision_tool"] = decision.get("tool")
        quality_flags["decision_applied"] = bool(decision.get("applied"))
        quality_flags["decision_action"] = plan.get("action")
        quality_flags["decision_fallback"] = decision.get("fallback_reason") is not None
        quality_flags["decision_fallback_reason"] = decision.get("fallback_reason")
        quality_flags["decision_not_applied_reason"] = plan.get("not_applied_reason")
        quality_flags["decision_latency_ms"] = decision.get("latency_ms")
        quality_flags["decision_confidence"] = decision.get("confidence")
        quality_flags["decision_tool_agreement"] = shadow_diff.get("tool_agreement")
        quality_flags["decision_intent_agreement"] = shadow_diff.get("intent_agreement")
        quality_flags["decision_slot_diff_fields"] = sorted(shadow_diff.get("slot_diff") or {})
    tool_call = metadata.get("tool_call") or {}
    if tool_call:
        quality_flags["tool_call_tool"] = tool_call.get("tool")
        quality_flags["tool_call_status"] = tool_call.get("status")
        quality_flags["tool_call_count"] = tool_call.get("count")
        quality_flags["tool_call_latency_ms"] = tool_call.get("latency_ms")
        quality_flags["tool_call_error"] = tool_call.get("error")
    # 灰度归因（阶段C §4-C.2）：legacy 侧也要有这几个字段，否则算不出覆盖率。
    routing = metadata.get("agent_routing") or {}
    if routing:
        quality_flags["routing_mode"] = routing.get("mode")
        quality_flags["routing_target_mode"] = routing.get("target_mode")
        quality_flags["routing_in_rollout"] = bool(routing.get("in_rollout"))
        quality_flags["routing_unit"] = routing.get("unit")
        quality_flags["routing_bucket"] = routing.get("bucket")
        quality_flags["routing_reason"] = routing.get("reason")
        quality_flags["routing_classifier_skipped"] = bool(routing.get("classifier_skipped"))
    # 重复推荐率（阶段C §4-C.3）。
    overlap = metadata.get("recommendation_overlap") or {}
    if overlap:
        quality_flags["recommended_count"] = overlap.get("recommended_count")
        quality_flags["recommendation_refinement"] = bool(overlap.get("refinement"))
        quality_flags["repeat_recommendation_count"] = overlap.get("repeat_count")
        quality_flags["repeat_recommendation"] = bool(overlap.get("repeat_count"))
        quality_flags["repeat_after_refinement"] = bool(
            overlap.get("refinement") and overlap.get("repeat_count")
        )
    trace = AgentTrace(
        user_id=user_id,
        conversation_id=conversation_id,
        user_message_id=user_message_id,
        assistant_message_id=assistant_message_id,
        intent=intent.get("intent"),
        route=intent.get("route"),
        status="success",
        prompt_version=settings.AI_PROMPT_VERSION,
        orchestrator_version=settings.AI_ORCHESTRATOR_VERSION,
        index_version=settings.AI_INDEX_VERSION,
        provider=model.get("provider"),
        model=model.get("model"),
        fallback_used=1 if fallback.get("used") else 0,
        input_tokens=model.get("input_tokens"),
        output_tokens=model.get("output_tokens"),
        retrieval_latency_ms=diagnostics.get("latency_ms"),
        total_latency_ms=max(0, int(total_latency_ms)),
        referenced_resource_ids=allowed_ids or None,
        quality_flags=quality_flags,
    )
    db.add(trace)
    db.commit()
    db.refresh(trace)
    return trace


def agent_quality_dashboard(db: Session, days: int = 7) -> dict[str, Any]:
    """汇总近 N 天智能体质量看板：轨迹、检索、工具、决策与灰度指标。"""
    since = datetime.now(timezone.utc) - timedelta(days=max(1, min(days, 90)))
    traces = db.query(AgentTrace).filter(AgentTrace.created_at >= since).all()
    retrievals = db.query(AgentRetrievalLog).filter(AgentRetrievalLog.created_at >= since).all()
    actions = db.query(AgentActionLog).filter(AgentActionLog.created_at >= since).all()
    jobs = db.query(AIIndexJob).filter(AIIndexJob.created_at >= since).all()

    def average(values: list[int | float | None]) -> float:
        clean = [float(value) for value in values if value is not None]
        return round(sum(clean) / len(clean), 2) if clean else 0.0

    citation_failures = sum(
        1 for trace in traces
        if (trace.quality_flags or {}).get("empty_citation_after_retrieval")
    )
    all_flags = [trace.quality_flags or {} for trace in traces]
    # 灰度期看板：决策层接管率、回退原因分布、与老分类器的一致率（阶段B §4.6）。
    decision_flags = [flags for flags in all_flags if flags.get("decision_routing_mode")]
    agreements = [
        flags.get("decision_tool_agreement")
        for flags in decision_flags
        if flags.get("decision_tool_agreement") is not None
    ]
    fallback_reasons: dict[str, int] = {}
    for flags in decision_flags:
        reason = flags.get("decision_fallback_reason") or flags.get("decision_not_applied_reason")
        if reason:
            # 只保留 code 前缀，避免把置信度、工具名这类可变尾巴打散成上百个分桶。
            key = _reason_code(reason)
            fallback_reasons[key] = fallback_reasons.get(key, 0) + 1
    return {
        "window_days": days,
        "versions": {
            "prompt": settings.AI_PROMPT_VERSION,
            "orchestrator": settings.AI_ORCHESTRATOR_VERSION,
            "index": settings.AI_INDEX_VERSION,
        },
        "traces": {
            "total": len(traces),
            "fallback_rate": round(sum(trace.fallback_used for trace in traces) / len(traces), 4) if traces else 0.0,
            # 降级率：模型不可用、回复由平台兜底的比例。持续大于 0 说明该查 provider 配置或额度。
            "degraded_rate": round(
                sum(1 for flags in all_flags if flags.get("provider_degraded")) / len(traces), 4
            ) if traces else 0.0,
            "citation_failure_rate": round(citation_failures / len(traces), 4) if traces else 0.0,
            "avg_total_latency_ms": average([trace.total_latency_ms for trace in traces]),
            "avg_input_tokens": average([trace.input_tokens for trace in traces]),
            "avg_output_tokens": average([trace.output_tokens for trace in traces]),
        },
        "retrieval": {
            "total": len(retrievals),
            "success_rate": round(sum(item.status == "success" for item in retrievals) / len(retrievals), 4) if retrievals else 0.0,
            "avg_latency_ms": average([item.latency_ms for item in retrievals]),
        },
        "tools": {
            "total": len(actions),
            "success_rate": round(sum(item.status in {"success", "completed"} for item in actions) / len(actions), 4) if actions else 0.0,
        },
        "decisions": {
            "total": len(decision_flags),
            "routing_mode": settings.AGENT_ROUTING_MODE,
            "applied_rate": round(
                sum(1 for flags in decision_flags if flags.get("decision_applied")) / len(decision_flags), 4
            ) if decision_flags else 0.0,
            "fallback_rate": round(
                sum(1 for flags in decision_flags if flags.get("decision_fallback")) / len(decision_flags), 4
            ) if decision_flags else 0.0,
            "tool_agreement_rate": round(
                sum(1 for value in agreements if value) / len(agreements), 4
            ) if agreements else 0.0,
            "avg_latency_ms": average([flags.get("decision_latency_ms") for flags in decision_flags]),
            "fallback_reasons": dict(
                sorted(fallback_reasons.items(), key=lambda item: item[1], reverse=True)[:10]
            ),
        },
        # 阶段C §4-C.2、§4-C.3：灰度覆盖率与五项灰度指标。
        "rollout": rollout_coverage(all_flags),
        "rollout_metrics": decision_rollout_metrics(all_flags),
        "index_jobs": {
            "total": len(jobs),
            "pending": sum(item.status == "pending" for item in jobs),
            "failed": sum(item.status == "failed" for item in jobs),
            "completed": sum(item.status == "completed" for item in jobs),
        },
    }
