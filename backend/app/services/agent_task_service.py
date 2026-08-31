"""Lifecycle and serialization service for persistent Agent task drafts."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.app.models.agent_task import AgentTaskDraft
from backend.app.models.ai_conversation import AIMessage
from backend.app.models.order import Order
from backend.app.models.photographer import PhotographerProfile
from backend.app.models.project import ProjectApplication, ShootProject
from backend.app.services.agent_task_extraction_service import TASK_FIELDS, apply_operations

ACTIVE_STATUSES = {"collecting", "editing_page", "submitting", "generating", "saving", "failed"}
TERMINAL_STATUSES = {"completed", "cancelled", "expired"}
TASK_TYPES = set(TASK_FIELDS)

REQUIRED_TASK_FIELDS: dict[str, tuple[str, ...]] = {
    "create_project": ("title", "description", "city"),
    "publish_package": ("name", "price", "duration"),
    "publish_work": ("media_assets",),
    "project_application": ("project_id", "proposal_text", "price_quote"),
    "create_booking": ("photographer_id", "package_id", "appointment_date"),
    "create_inspiration": ("inspiration_id",),
    "generate_image": ("prompt", "mode"),
}

FIELD_LABELS = {
    "title": "标题", "description": "说明", "city": "城市", "shoot_date_start": "拍摄时间",
    "budget_max": "预算", "name": "方案名称", "price": "价格", "duration": "拍摄时长",
    "media_assets": "作品素材", "project_id": "目标企划", "proposal_text": "应邀说明",
    "price_quote": "报价", "photographer_id": "摄影师", "package_id": "摄影方案",
    "appointment_date": "预约日期",
}

NEXT_QUESTIONS = {
    "title": "这次内容想用什么标题？",
    "description": "请补充一句需求或内容说明。",
    "city": "拍摄或服务城市是哪里？",
    "shoot_date_start": "希望安排在哪一天、几点拍摄？",
    "budget_max": "预算上限是多少？",
    "name": "这个摄影方案叫什么名字？",
    "price": "方案价格是多少？",
    "duration": "预计拍摄多长时间？",
    "media_assets": "请进入编辑页选择要发布的图片或视频。",
    "project_id": "请先从企划详情进入 Agent，让我确认应邀目标。",
    "proposal_text": "你希望怎样完成这份拍摄需求？",
    "price_quote": "这次应邀报价是多少？",
    "photographer_id": "请先选择一位摄影师。",
    "package_id": "请先选择一个真实可预约的摄影方案。",
    "appointment_date": "请选择一个可预约日期。",
}

COMMIT_LABELS = {
    "create_project": "确认发布企划",
    "publish_package": "确认发布方案",
    "project_application": "提交应邀",
    "create_booking": "提交预约申请",
    "create_inspiration": "保存灵感",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _task_value(task: AgentTaskDraft, field: str) -> Any:
    if field == "media_assets":
        return task.media_assets or []
    if field in {"project_id", "photographer_id", "package_id", "work_id"}:
        return (task.target or {}).get(field)
    return (task.fields or {}).get(field)


def missing_required_fields(task: AgentTaskDraft) -> list[str]:
    return [
        field for field in REQUIRED_TASK_FIELDS.get(task.task_type, ())
        if _task_value(task, field) in (None, "", [], {})
    ]


def _owned(db: Session, user_id: int, conversation_id: int, task_id: str) -> AgentTaskDraft:
    task = (
        db.query(AgentTaskDraft)
        .filter(
            AgentTaskDraft.id == str(task_id),
            AgentTaskDraft.user_id == user_id,
            AgentTaskDraft.conversation_id == conversation_id,
        )
        .first()
    )
    if not task:
        raise HTTPException(status_code=404, detail="Agent task not found")
    return task


def get_active_task(db: Session, user_id: int, conversation_id: int) -> AgentTaskDraft | None:
    return (
        db.query(AgentTaskDraft)
        .filter(
            AgentTaskDraft.user_id == user_id,
            AgentTaskDraft.conversation_id == conversation_id,
            AgentTaskDraft.status.in_(ACTIVE_STATUSES),
        )
        .order_by(AgentTaskDraft.updated_at.desc(), AgentTaskDraft.created_at.desc())
        .first()
    )


def ensure_task(db: Session, *, user_id: int, conversation_id: int, task_type: str, target: dict[str, Any] | None = None) -> AgentTaskDraft:
    if task_type not in TASK_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported agent task type")
    current = get_active_task(db, user_id, conversation_id)
    if current:
        if current.task_type != task_type:
            raise HTTPException(status_code=409, detail="Another agent task is already active")
        if target:
            current.target = {**(current.target or {}), **target}
        return current
    task = AgentTaskDraft(
        id=str(uuid4()), user_id=user_id, conversation_id=conversation_id, task_type=task_type,
        status="collecting", schema_version=2, revision=0, target=target or {}, fields={},
        field_sources={}, media_assets=[],
    )
    db.add(task)
    db.flush()
    return task


def _summary(task: AgentTaskDraft) -> dict[str, Any]:
    fields = task.fields or {}
    priority = {
        "create_project": [("地点", "city"), ("风格", "style_tags"), ("预算", "budget_max"), ("拍摄时间", "shoot_date_start")],
        "publish_package": [("方案名", "name"), ("价格", "price"), ("时长", "duration"), ("城市", "city")],
        "publish_work": [("标题", "title"), ("标签", "tags"), ("说明", "description")],
        "project_application": [("报价", "price_quote"), ("申请说明", "proposal_text"), ("关联方案", "package_snapshot")],
        "create_booking": [("方案", "package_id"), ("预约日期", "appointment_date"), ("备注", "notes")],
        "create_inspiration": [("标题", "title"), ("摘要", "summary"), ("标签", "tags")],
        "generate_image": [("模式", "mode"), ("描述", "prompt"), ("宽高比", "aspect_ratio")],
    }.get(task.task_type, [])
    lines = []
    for label, field in priority:
        value = fields.get(field)
        if field == "package_id" and value in (None, "", [], {}):
            value = (task.target or {}).get("package_id")
        if value in (None, "", [], {}):
            continue
        if isinstance(value, list):
            value = "、".join(str(item) for item in value)
        if field == "budget_max" and fields.get("budget_min") is not None:
            value = f"HK${fields['budget_min']:,}–{value:,}" if isinstance(value, (int, float)) else value
        lines.append({"label": label, "value": str(value)[:120]})
    collected = sum(value not in (None, "", [], {}) for value in fields.values())
    collected += sum(
        value not in (None, "", [], {})
        for value in (task.target or {}).values()
    )
    missing = missing_required_fields(task)
    requires_editor = task.task_type == "publish_work"
    can_commit = not missing and not requires_editor and task.status not in TERMINAL_STATUSES
    return {
        "title": {
            "create_project": "发布企划", "publish_package": "发布方案", "publish_work": "发布作品",
            "project_application": "申请企划", "create_booking": "预约拍摄", "create_inspiration": "创建灵感",
            "generate_image": "图片生成",
        }.get(task.task_type, "Agent 任务"),
        "lines": lines[:4], "collected_count": collected,
        "missing_required_count": len(missing),
        "missing_required_fields": missing,
        "missing_required_labels": [FIELD_LABELS.get(field, field) for field in missing],
        "media_count": len(task.media_assets or []),
        "can_commit": can_commit,
        "requires_editor": requires_editor,
        "next_question": NEXT_QUESTIONS.get(missing[0]) if missing else None,
        "commit_label": COMMIT_LABELS.get(task.task_type),
        "edit_label": "进入编辑",
    }


def serialize_task(task: AgentTaskDraft | None) -> dict[str, Any] | None:
    if not task:
        return None
    return {
        "task_id": task.id, "conversation_id": task.conversation_id, "task_type": task.task_type,
        "status": task.status, "schema_version": task.schema_version, "revision": task.revision,
        "target": task.target or {}, "fields": task.fields or {}, "media_assets": task.media_assets or [], "summary": _summary(task),
        "result": task.result, "updated_at": task.updated_at.isoformat() if task.updated_at else None,
    }


def patch_task(db: Session, *, user_id: int, conversation_id: int, task_id: str, revision: int, operations: list[dict[str, Any]], source_message_id: int | None = None) -> AgentTaskDraft:
    task = _owned(db, user_id, conversation_id, task_id)
    if task.status in TERMINAL_STATUSES:
        raise HTTPException(status_code=409, detail="Agent task is already closed")
    if revision != task.revision:
        raise HTTPException(status_code=409, detail={"code": "revision_conflict", "task": serialize_task(task)})
    fields, accepted = apply_operations(task.fields or {}, operations, TASK_FIELDS[task.task_type])
    if accepted:
        task.fields = fields
        sources = dict(task.field_sources or {})
        now = _now().isoformat()
        for operation in accepted:
            sources[operation["field"]] = {
                "source_message_id": source_message_id, "updated_at": now,
                "confidence": operation.get("confidence", 0), "evidence": operation.get("evidence"),
            }
        task.field_sources = sources
        task.revision += 1
        task.updated_at = _now()
    return task


def sync_task_snapshot(db: Session, *, user_id: int, conversation_id: int, task_type: str, fields: dict[str, Any], target: dict[str, Any] | None = None, media_assets: list[Any] | None = None, status: str = "collecting", source_message_id: int | None = None) -> AgentTaskDraft:
    current = get_active_task(db, user_id, conversation_id)
    # A second publish/booking intent is ordinary chat while another task is active;
    # it must never replace or mutate the existing draft.
    if current and current.task_type != task_type:
        return current
    task = ensure_task(db, user_id=user_id, conversation_id=conversation_id, task_type=task_type, target=target)
    if task.status in TERMINAL_STATUSES:
        return task
    operations = [{"field": key, "op": "set", "value": value, "confidence": 1.0, "evidence": "agent task snapshot"} for key, value in (fields or {}).items() if key in TASK_FIELDS[task_type] and value not in (None, "")]
    task = patch_task(db, user_id=user_id, conversation_id=conversation_id, task_id=task.id, revision=task.revision, operations=operations, source_message_id=source_message_id)
    if media_assets is not None:
        task.media_assets = list(media_assets)
    if status in ACTIVE_STATUSES or status in TERMINAL_STATUSES:
        task.status = status
        if status == "completed":
            task.completed_at = _now()
    return task


def open_task(db: Session, *, user_id: int, conversation_id: int, task_id: str) -> AgentTaskDraft:
    task = _owned(db, user_id, conversation_id, task_id)
    if task.status in TERMINAL_STATUSES:
        return task
    task.opened_at = task.opened_at or _now()
    task.updated_at = _now()
    return task


def commit_task(
    db: Session,
    *,
    user_id: int,
    conversation_id: int,
    task_id: str,
    revision: int,
    idempotency_key: str,
) -> tuple[AgentTaskDraft, dict[str, Any]]:
    """Execute one explicit structured commit against the authoritative task draft."""
    task = _owned(db, user_id, conversation_id, task_id)
    if task.status == "completed":
        return task, {"status": "success", "content": "该任务已经提交，无需重复操作。", "result": task.result or {}}
    if task.status in {"cancelled", "expired"}:
        raise HTTPException(status_code=409, detail="Agent task is already closed")
    if task.revision != revision:
        raise HTTPException(status_code=409, detail={"code": "revision_conflict", "task": serialize_task(task)})
    missing = missing_required_fields(task)
    if missing:
        raise HTTPException(
            status_code=422,
            detail={"code": "task_incomplete", "missing_fields": missing, "task": serialize_task(task)},
        )
    if task.task_type == "publish_work":
        raise HTTPException(status_code=409, detail={"code": "editor_required", "task": serialize_task(task)})

    from backend.app.schemas.project import ProjectApplicationCreate
    from backend.app.services import project_service
    from backend.app.services.ai_agent_tool_service import (
        create_booking as create_booking_tool,
        create_project as create_project_tool,
        publish_package as publish_package_tool,
    )

    fields = dict(task.fields or {})
    target = dict(task.target or {})
    task.status = "submitting"
    task.updated_at = _now()
    db.flush()

    result: dict[str, Any] = {}
    success = False
    try:
        if task.task_type == "create_project":
            payload = {
                **fields,
                "category": fields.get("category") or "other",
                "visibility": fields.get("visibility") or "public",
                "reference_images": fields.get("reference_images") or list(task.media_assets or []),
                "publish": True,
            }
            call = create_project_tool(
                db, user_id=user_id, conversation_id=conversation_id, message_id=None,
                project_payload=payload, confirmation_count=1, idempotency_key=idempotency_key,
            )
            result = call.get("result") or {}
            success = call.get("status") == "success"
        elif task.task_type == "publish_package":
            payload = {
                **fields,
                "samples": fields.get("samples") or list(task.media_assets or []),
            }
            if payload.get("retouched_image_count") is not None and payload.get("image_count") is None:
                payload["image_count"] = payload["retouched_image_count"]
            call = publish_package_tool(
                db, user_id=user_id, conversation_id=conversation_id, message_id=None,
                package_payload=payload, confirmation_count=1, idempotency_key=idempotency_key,
            )
            result = call.get("result") or {}
            success = call.get("status") == "success"
        elif task.task_type == "create_booking":
            payload = {
                "photographer_id": target["photographer_id"],
                "package_id": target["package_id"],
                "appointment_date": fields["appointment_date"],
                "duration_minutes": fields.get("duration_minutes") or target.get("duration_minutes") or 120,
                "notes": fields.get("notes"),
            }
            call = create_booking_tool(
                db, user_id=user_id, conversation_id=conversation_id, message_id=None,
                booking_payload=payload, confirmation_count=1, idempotency_key=idempotency_key,
            )
            result = call.get("result") or {}
            success = call.get("status") == "success"
        elif task.task_type == "project_application":
            project = project_service.get_project_by_id(db, int(target["project_id"]))
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            application = project_service.apply_project(
                db,
                project,
                user_id,
                ProjectApplicationCreate(**{
                    key: fields.get(key)
                    for key in ("proposal_text", "price_quote", "package_snapshot", "portfolio_refs", "revision_note")
                }),
            )
            result = {
                "application_id": application.id,
                "project_id": application.project_id,
                "status": str(application.status.value if hasattr(application.status, "value") else application.status),
            }
            success = True
    except (HTTPException, ValueError, TypeError, KeyError) as exc:
        result = {"error": getattr(exc, "detail", None) or str(exc)}

    if success:
        task.status = "completed"
        task.result = result
        task.completed_at = _now()
        content = {
            "create_project": f"企划已发布：{result.get('title') or fields.get('title')}。",
            "publish_package": f"方案已发布：{result.get('package_name') or fields.get('name')}。",
            "project_application": "应邀已提交，等待客户查看和选择。",
            "create_booking": f"预约申请已提交，订单编号 {result.get('order_id')}，正在等待摄影师确认。",
        }.get(task.task_type, "任务已提交。")
        receipt_status = "success"
    else:
        task.status = "collecting"
        task.result = result
        content = f"提交失败：{result.get('error') or '业务校验未通过'}。请修改后重试。"
        receipt_status = "failed"
    task.updated_at = _now()
    return task, {"status": receipt_status, "content": content, "result": result}


def cancel_task(db: Session, *, user_id: int, conversation_id: int, task_id: str) -> AgentTaskDraft:
    task = _owned(db, user_id, conversation_id, task_id)
    if task.status not in TERMINAL_STATUSES:
        task.status = "cancelled"
        task.updated_at = _now()
    # The task draft is authoritative for the task card, but older assistant
    # messages also contain workflow snapshots used by the legacy orchestrator.
    # Mark the latest snapshot closed as well; otherwise the next ordinary
    # message can resurrect the cancelled flow from stale metadata.
    message = (
        db.query(AIMessage)
        .filter(AIMessage.conversation_id == conversation_id, AIMessage.role == "assistant")
        .order_by(AIMessage.created_at.desc(), AIMessage.id.desc())
        .first()
    )
    if message:
        metadata = dict(message.message_metadata or {})
        task_state = metadata.get("task_state")
        if isinstance(task_state, dict) and (
            str(task_state.get("task_id") or "") == str(task.id)
            or task_state.get("task_type") == task.task_type
        ):
            metadata["task_state"] = {
                **task_state,
                "task_id": task.id,
                "status": "cancelled",
                "missing_slots": [],
                "pending_action": None,
            }
            metadata["active_task"] = None
            card = metadata.get("agent_form_card")
            if isinstance(card, dict):
                metadata["agent_form_card"] = {**card, "status": "cancelled", "actions": []}
            message.message_metadata = metadata
    return task


def complete_task(db: Session, *, user_id: int, conversation_id: int, task_id: str, result: dict[str, Any] | None = None) -> AgentTaskDraft:
    task = _owned(db, user_id, conversation_id, task_id)
    if task.status == "completed":
        return task
    if task.status in {"cancelled", "expired"}:
        raise HTTPException(status_code=409, detail="Agent task is already closed")
    _validate_result_ownership(db, task, user_id, result or {})
    task.status = "completed"
    task.result = result or task.result or {}
    task.completed_at = _now()
    task.updated_at = _now()
    return task


def _validate_result_ownership(db: Session, task: AgentTaskDraft, user_id: int, result: dict[str, Any]) -> None:
    """Validate IDs supplied after an ordinary business request succeeds."""
    target = task.target or {}
    try:
        if task.task_type == "create_project" and result.get("project_id") is not None:
            resource = db.query(ShootProject).filter(ShootProject.id == int(result["project_id"])).first()
            if not resource or resource.customer_id != user_id:
                raise ValueError
        elif task.task_type == "project_application" and result.get("application_id") is not None:
            resource = db.query(ProjectApplication).filter(ProjectApplication.id == int(result["application_id"])).first()
            if not resource or resource.photographer_id != user_id or (target.get("project_id") is not None and resource.project_id != int(target["project_id"])):
                raise ValueError
        elif task.task_type == "create_booking" and result.get("order_id") is not None:
            resource = db.query(Order).filter(Order.id == int(result["order_id"])).first()
            if not resource or resource.customer_id != user_id:
                raise ValueError
            if target.get("photographer_id") is not None and resource.photographer_id != int(target["photographer_id"]):
                raise ValueError
            if target.get("package_id") is not None and str(resource.package_id) != str(target["package_id"]):
                raise ValueError
        elif task.task_type in {"publish_package", "publish_work"}:
            profile = db.query(PhotographerProfile).filter(PhotographerProfile.user_id == user_id).first()
            key = "package_id" if task.task_type == "publish_package" else "work_id"
            collection = profile.packages if task.task_type == "publish_package" and profile else profile.portfolio if profile else []
            if result.get(key) is not None and not profile:
                raise ValueError
            if result.get(key) is not None and not any(str(item.get("id")) == str(result[key]) for item in collection or [] if isinstance(item, dict)):
                raise ValueError
    except (TypeError, ValueError):
        raise HTTPException(status_code=403, detail="Agent task result does not belong to the current user") from None
