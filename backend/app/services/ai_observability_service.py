"""AI 检索运行观测：记录每次检索的诊断与引用信息。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from backend.app.models.ai_conversation import AgentRetrievalLog


def log_retrieval_run(
    db: Session,
    *,
    user_id: int,
    conversation_id: int,
    message_id: int,
    query_text: str,
    intent: dict[str, Any],
    retrieval: dict[str, Any] | None,
) -> AgentRetrievalLog:
    """记录一次检索运行的诊断与引用数据，返回保存后的日志。"""
    diagnostics = (retrieval or {}).get("diagnostics") or {}
    references = (retrieval or {}).get("references") or {}
    criteria = (retrieval or {}).get("criteria") or {}
    resource_ids = {
        key: [
            item.get("id") or item.get("resource_id") or item.get("user_id")
            for item in values or []
            if item.get("id") or item.get("resource_id") or item.get("user_id")
        ]
        for key, values in references.items()
    }
    log = AgentRetrievalLog(
        user_id=user_id,
        conversation_id=conversation_id,
        message_id=message_id,
        intent=intent,
        query_text=query_text or "",
        criteria=criteria,
        requested_resource_types=criteria.get("resource_types") or [],
        document_counts=diagnostics.get("document_counts") or {},
        candidate_counts=diagnostics.get("candidate_counts") or {},
        result_counts=diagnostics.get("result_counts") or {},
        referenced_resource_ids=resource_ids,
        ranking_diagnostics={
            "retrieval_mode": diagnostics.get("retrieval_mode"),
            "semantic_backend": diagnostics.get("semantic_backend"),
            "embedding": diagnostics.get("embedding") or {},
            "score_weights": diagnostics.get("score_weights") or {},
            "multimodal": diagnostics.get("multimodal") or {},
            "conversion_feedback": diagnostics.get("conversion_feedback") or {},
            # 多轮追问诊断：本轮由意图确认了哪些条件、继承了哪些条件、排除了哪些已推荐资源。
            "refinement": {
                "explicit_fields": diagnostics.get("explicit_fields") or [],
                "inherited_fields": diagnostics.get("inherited_fields") or [],
                "excluded_resource_ids": diagnostics.get("excluded_resource_ids") or [],
            },
        },
        latency_ms=int(diagnostics.get("latency_ms") or 0),
        status="success" if retrieval is not None else "skipped",
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log
