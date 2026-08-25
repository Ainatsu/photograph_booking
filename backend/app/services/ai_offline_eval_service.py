"""阶段C §4-C.5：把规则识别和决策日志用于离线评估，而不是继续当线上主路由。

两个入口，都不调用任何 LLM，可以在任何环境（含 mock provider）跑：

- `replay_agent_traces`：回放已落库的 AgentTrace + 消息元数据，算出灰度五项指标，
  并用规则识别重跑同一条用户消息，给出"规则 vs 决策"的离线一致率。
  这是"新协议是否已经稳定"的判断依据（§4-C.4 的收口前置条件）。
- `evaluate_rules_tool_selection`：对 JSONL 固定集跑"规则应当选哪个工具"，
  作为回归门禁——规则退到兜底角色之后，仍然要保证它选得出正确的工具。

隐私：默认不输出用户原文，只输出 trace id、工具名与差异字段（§5.5）。
需要人工看分歧时再显式打开 include_text。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from sqlalchemy.orm import Session

from backend.app.models.ai_conversation import AIMessage
from backend.app.models.ai_production import AgentTrace
from backend.app.services.ai_agent_decision_contracts import (
    DECISION_SCHEMA_VERSION,
    AgentDecision,
)
from backend.app.services.ai_agent_decision_service import (
    AgentDecisionOutcome,
    compare_decision_with_intent,
    expected_tool_for_intent,
)
from backend.app.services.ai_orchestrator_service import recognize_intent
from backend.app.services.ai_trace_service import (
    decision_rollout_metrics,
    rollout_coverage,
)


OFFLINE_EVAL_SCHEMA_VERSION = "agent_offline_eval_v1"

# 人工复核用的分歧样本上限：报告是给人看的，不是导出全量日志。
MAX_DISAGREEMENT_SAMPLES = 20

# 样本里保留的原文长度，仅在 include_text=True 时输出。
SAMPLE_TEXT_LIMIT = 80


def replay_agent_traces(
    db: Session,
    *,
    days: int = 7,
    limit: int | None = None,
    include_text: bool = False,
) -> dict[str, Any]:
    """回放灰度期的决策日志，产出指标 + 规则对齐报告。"""
    since = datetime.now(timezone.utc) - timedelta(days=max(1, min(days, 90)))
    query = (
        db.query(AgentTrace)
        .filter(AgentTrace.created_at >= since)
        .order_by(AgentTrace.id.desc())
    )
    if limit:
        query = query.limit(max(1, limit))
    traces = list(reversed(query.all()))

    message_ids = {trace.user_message_id for trace in traces if trace.user_message_id}
    message_ids |= {trace.assistant_message_id for trace in traces if trace.assistant_message_id}
    messages = (
        {
            row.id: row
            for row in db.query(AIMessage).filter(AIMessage.id.in_(message_ids)).all()
        }
        if message_ids
        else {}
    )

    compared = 0
    tool_agreements = 0
    intent_agreements = 0
    intent_compared = 0
    unparseable = 0
    samples: list[dict[str, Any]] = []
    for trace in traces:
        assistant = messages.get(trace.assistant_message_id)
        decision_trace = ((assistant.message_metadata or {}) if assistant else {}).get(
            "agent_decision"
        ) or {}
        if decision_trace.get("parser") != "model":
            continue
        user_message = messages.get(trace.user_message_id)
        content = (user_message.content if user_message else "") or ""
        if not content.strip():
            continue
        decision = _rebuild_decision(decision_trace)
        if decision is None:
            unparseable += 1
            continue

        rules_intent = recognize_intent(content)
        diff = compare_decision_with_intent(
            AgentDecisionOutcome(decision=decision, parser="model"),
            rules_intent,
        )
        compared += 1
        if diff["tool_agreement"]:
            tool_agreements += 1
        if diff["intent_agreement"] is not None:
            intent_compared += 1
            if diff["intent_agreement"]:
                intent_agreements += 1
        if not diff["tool_agreement"] and len(samples) < MAX_DISAGREEMENT_SAMPLES:
            sample = {
                "trace_id": trace.id,
                "rules_intent": diff["legacy_intent"],
                "rules_tool": diff["legacy_tool"],
                "decision_mode": diff["decision_mode"],
                "decision_tool": diff["decision_tool"],
                "slot_diff_fields": sorted(diff["slot_diff"]),
            }
            if include_text:
                sample["content"] = content[:SAMPLE_TEXT_LIMIT]
            samples.append(sample)

    all_flags = [trace.quality_flags or {} for trace in traces]
    return {
        "schema_version": OFFLINE_EVAL_SCHEMA_VERSION,
        "window_days": days,
        "traces": len(traces),
        "rollout": rollout_coverage(all_flags),
        "metrics": decision_rollout_metrics(all_flags),
        "rules_vs_decision": {
            "compared": compared,
            "unparseable": unparseable,
            "tool_agreement_rate": round(tool_agreements / compared, 4) if compared else 0.0,
            "intent_agreement_rate": (
                round(intent_agreements / intent_compared, 4) if intent_compared else 0.0
            ),
            "disagreements": samples,
        },
    }


def _rebuild_decision(decision_trace: dict[str, Any]) -> AgentDecision | None:
    """从落库的诊断切片还原决策对象，好复用同一套差异逻辑。"""
    payload = {
        "schema_version": decision_trace.get("protocol_version") or DECISION_SCHEMA_VERSION,
        "mode": decision_trace.get("mode"),
        "tool": decision_trace.get("tool"),
        "arguments": decision_trace.get("arguments") or {},
        "question": decision_trace.get("question"),
        "confidence": decision_trace.get("confidence"),
        "reason": decision_trace.get("reason"),
    }
    try:
        return AgentDecision.model_validate(
            {key: value for key, value in payload.items() if value is not None}
        )
    except Exception:
        return None


def evaluate_rules_tool_selection(cases: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """规则识别选工具的固定集评估（§4-C.5：规则作为兜底也必须选得对）。

    case 形如 {"id": ..., "input": "...", "expected": {"tool": "search_packages"}}；
    expected.tool 为 null 表示这条消息不该触发任何工具（闲聊/知识问答）。
    """
    results = []
    for case in cases:
        expected = (case.get("expected") or {}).get("tool")
        actual = expected_tool_for_intent(recognize_intent(case.get("input") or ""))
        results.append({
            "id": case.get("id"),
            "input": case.get("input"),
            "expected_tool": expected,
            "actual_tool": actual,
            "passed": actual == expected,
        })
    passed = sum(1 for item in results if item["passed"])
    total = len(results)
    return {
        "schema_version": OFFLINE_EVAL_SCHEMA_VERSION,
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "accuracy": round(passed / total, 4) if total else 0.0,
        "results": results,
    }
