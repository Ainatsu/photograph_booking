"""Workflow 事件镜像到对话事件流的共享 helper（workflow 阶段 E 抽取）。

原先内嵌在 agent_workflow_appreciation_search.py；search_then_inspire 迁移
（阶段 E）后多个 workflow 模块都需要同样的镜像逻辑，抽到这里共享。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from backend.app.services.ai_event_service import append_event
from backend.app.services.agent_workflow_store import list_workflow_events

# 镜像到对话事件流时使用的 schema 版本。
WORKFLOW_EVENT_MIRROR_SCHEMA_VERSION = "workflow_event_mirror_v1"


def mirror_new_workflow_events(
    db: Session,
    *,
    user_id: int,
    conversation_id: int,
    run: Any,
    after_sequence: int,
    turn_id: str | None,
) -> int:
    """把 run 的 durable workflow 事件镜像进对话事件流（SSE 消费）。

    断线重连由对话事件自身的 sequence 游标保证；workflow 原始 sequence
    保留在 payload.workflow_sequence 中供审计比对。返回已镜像到的
    workflow sequence，调用方下次从这里继续。
    """
    last = after_sequence
    events = list_workflow_events(
        db,
        run_id=run.id,
        user_id=user_id,
        after_sequence=after_sequence,
    )
    for event in events:
        source = dict(event.payload or {})
        # 原 payload 可能自带 schema_version（如 workflow.created 的计划版本），
        # 镜像信封的版本必须放在最后；原始版本保留在 source_schema_version。
        source_schema = source.pop("schema_version", None)
        payload = {
            **source,
            "schema_version": WORKFLOW_EVENT_MIRROR_SCHEMA_VERSION,
            "workflow_run_id": run.id,
            "workflow_type": run.workflow_type,
            "workflow_sequence": event.sequence,
        }
        if source_schema:
            payload["source_schema_version"] = source_schema
        append_event(
            db,
            user_id=user_id,
            conversation_id=conversation_id,
            event_type=event.event_type,
            task_id=run.id,
            turn_id=turn_id,
            payload=payload,
        )
        last = event.sequence
    return last
