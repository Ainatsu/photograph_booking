"""统一 Agent 表单卡片协议与提交边界。

普通页面仍然是业务写入的唯一真相；本模块只负责把卡片协议转换成
现有 schema/service 可接受的输入，并把结果重新包装成只读卡片。
"""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.app.models.ai_conversation import AIMessage
from backend.app.models.photographer import PhotographerProfile
from backend.app.schemas.photographer import PortfolioItemUpdate
from backend.app.schemas.project import ProjectApplicationCreate
from backend.app.services import project_service
from backend.app.services.ai_agent_tool_service import (
    create_booking,
    create_project,
    publish_package,
)


TASK_TYPES = {
    "create_project",
    "publish_package",
    "publish_work",
    "project_application",
    "create_booking",
}
FORM_ACTIONS = {"publish", "save_draft", "cancel"}
EDITABLE_STATUSES = {"editing", "invalid", "draft_unavailable"}


def infer_initial_task_type(content: str | None, page_context: dict[str, Any] | None) -> str | None:
    """只依据当前消息和当前页面上下文识别作品发布/企划申请入口。"""
    text = (content or "").strip()
    resource_type = (page_context or {}).get("resource_type")
    if resource_type == "portfolio_item" and re.search(r"(发布|上传|编辑).*(作品|到作品集)|发布作品", text):
        return "publish_work"
    return None


def initial_form_result(task_type: str, page_context: dict[str, Any]) -> dict[str, Any]:
    """从当前页面的可信上下文建立第一张可编辑卡片。"""
    if task_type == "publish_work":
        values = {
            "work_id": page_context.get("resource_id"),
            "title": page_context.get("title", ""),
            "tags": page_context.get("tags") or page_context.get("styles") or [],
            "description": page_context.get("description", ""),
            "media_refs": [page_context.get("current_object", {}).get("image_url")] if page_context.get("current_object", {}).get("image_url") else [],
        }
        target = {"work_id": page_context.get("resource_id")}
        copy = "作品信息已载入卡片，请检查标题、标签和说明后确认发布。"
    else:
        values = {
            "project_id": page_context.get("resource_id"),
            "proposal_text": "",
            "price_quote": "",
            "package_snapshot": page_context.get("package_name") or "",
            "portfolio_refs": [],
            "revision_note": "",
        }
        target = {"project_id": page_context.get("resource_id")}
        copy = "企划已载入卡片，请填写应邀说明和报价后确认申请。"
    card = make_form_card(task_type, values=values, status="editing", target=target)
    return {
        "content": copy,
        "metadata": {
            "agent_form_card": card,
            "task_state": {
                "task_type": task_type,
                "status": "awaiting_details",
                "slots": values,
                "missing_slots": [],
                "task_id": card["task_id"],
                "revision": card["revision"],
                "pending_action": None,
            },
        },
    }


def normalize_submission(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    """规范化新旧提交字段，不信任客户端提供的路由或服务名称。"""
    if not isinstance(payload, dict):
        return None
    task_type = payload.get("task_type")
    action = payload.get("action")
    if task_type not in TASK_TYPES or action not in FORM_ACTIONS:
        raise ValueError("unsupported_agent_form_task")

    raw_data = payload.get("form_data")
    if raw_data is None:
        raw_data = payload.get("slots") or {}
    if not isinstance(raw_data, dict):
        raise ValueError("form_data_must_be_object")

    task_id = payload.get("task_id")
    if task_id:
        try:
            task_id = str(UUID(str(task_id)))
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid_task_id") from exc

    revision = payload.get("revision", 1)
    if not isinstance(revision, int) or revision < 1:
        raise ValueError("invalid_task_revision")

    idempotency_key = payload.get("idempotency_key") or str(uuid4())
    try:
        idempotency_key = str(UUID(str(idempotency_key)))
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid_idempotency_key") from exc

    return {
        "task_id": task_id,
        "task_type": task_type,
        "action": action,
        "revision": revision,
        "form_data": dict(raw_data),
        "media_refs": [str(item) for item in payload.get("media_refs") or [] if item],
        "idempotency_key": idempotency_key,
        "legacy": "form_data" not in payload,
    }


def latest_form_card(db: Session, conversation_id: int, task_type: str | None = None) -> dict[str, Any] | None:
    message = (
        db.query(AIMessage)
        .filter(AIMessage.conversation_id == conversation_id, AIMessage.role == "assistant")
        .order_by(AIMessage.created_at.desc(), AIMessage.id.desc())
        .first()
    )
    card = (message.message_metadata or {}).get("agent_form_card") if message else None
    if not isinstance(card, dict):
        return None
    if task_type and card.get("task_type") != task_type:
        return None
    return card


def validate_revision(db: Session, conversation_id: int, submission: dict[str, Any]) -> dict[str, Any] | None:
    """校验任务归属和乐观并发版本；旧 slots 请求不受新版本约束。"""
    if submission.get("legacy"):
        return None
    card = latest_form_card(db, conversation_id, submission["task_type"])
    if not card:
        raise ValueError("agent_task_not_found")
    if submission.get("task_id") != card.get("task_id"):
        raise ValueError("agent_task_not_owned")
    if submission["revision"] != int(card.get("revision") or 1):
        if submission.get("idempotency_key") == card.get("idempotency_key"):
            return card
        raise ValueError("agent_task_revision_conflict")
    return card


def form_fields(task_type: str, values: dict[str, Any]) -> dict[str, Any]:
    """把旧 Agent 槽位整理成前端可直接编辑的普通表单字段。"""
    if task_type == "create_project":
        style_tags = values.get("style_tags", values.get("style", []))
        if isinstance(style_tags, str):
            style_tags = [item.strip() for item in style_tags.replace("，", ",").split(",") if item.strip()]
        date_value = values.get("shoot_date_start") or values.get("date")
        if date_value and len(str(date_value)) == 10 and values.get("time"):
            date_value = f"{date_value}T{values['time']}:00"
        return {
            "title": values.get("title", ""),
            "description": values.get("description", ""),
            "category": values.get("category", "other"),
            "style_tags": style_tags or [],
            "city": values.get("city", ""),
            "location_text": values.get("location_text"),
            "location_name": values.get("location_name"),
            "location_address": values.get("location_address"),
            "location_latitude": values.get("location_latitude"),
            "location_longitude": values.get("location_longitude"),
            "location_place_id": values.get("location_place_id"),
            "location_provider": values.get("location_provider"),
            "coordinate_system": values.get("coordinate_system"),
            "location_precision": values.get("location_precision"),
            "shoot_date_start": date_value,
            "shoot_date_end": values.get("shoot_date_end"),
            "duration_minutes": values.get("duration_minutes"),
            "budget_min": values.get("budget_min"),
            "budget_max": values.get("budget_max"),
            "deliverables": values.get("deliverables"),
            "reference_images": values.get("reference_images") or [],
            "visibility": values.get("visibility", "public"),
            "expires_at": values.get("expires_at"),
        }
    if task_type == "publish_package":
        return {
            "name": values.get("name", values.get("package_name", "")),
            "price": values.get("price", 0),
            "duration": values.get("duration", values.get("duration_minutes", 0)),
            "description": values.get("description", values.get("package_description", "")),
            "includes": values.get("includes", values.get("package_includes", [])) or [],
            "styles": values.get("styles", values.get("style", [])) or [],
            "city": values.get("city", ""),
            "service_location": values.get("service_location", ""),
            "samples": values.get("samples", values.get("sample_images", [])) or [],
            "sample_thumbnails": values.get("sample_thumbnails", []) or [],
            "original_image_count": values.get("original_image_count", 0),
            "retouched_image_count": values.get("retouched_image_count", values.get("image_count", 0)),
            "image_count": values.get("image_count", 0),
            "delivery_formats": values.get("delivery_formats", ["JPG"]) or ["JPG"],
            "included_revision_count": values.get("included_revision_count", 0),
            "delivery_days": values.get("delivery_days", 7),
            "commercial_license": bool(values.get("commercial_license", False)),
            "terms_rules": values.get("terms_rules"),
            "is_active": values.get("is_active", True),
            "payment_mode": values.get("payment_mode", "full"),
            "deposit_rate": values.get("deposit_rate", 0.3),
            "fulfillment_mode": values.get("fulfillment_mode", "single_delivery"),
        }
    if task_type == "project_application":
        return {
            "project_id": values.get("project_id"),
            "proposal_text": values.get("proposal_text", ""),
            "price_quote": values.get("price_quote", 0),
            "package_snapshot": values.get("package_snapshot"),
            "portfolio_refs": values.get("portfolio_refs") or [],
            "revision_note": values.get("revision_note"),
        }
    if task_type == "publish_work":
        return {
            "work_id": values.get("work_id"),
            "title": values.get("title", ""),
            "tags": values.get("tags", []) or [],
            "description": values.get("description", ""),
            "media_refs": values.get("media_refs", []) or [],
        }
    return {
        "package_id": values.get("package_id"),
        "photographer_id": values.get("photographer_id"),
        "appointment_time": values.get("appointment_time"),
        "notes": str(values.get("notes") or "")[:500],
    }


def make_form_card(
    task_type: str,
    *,
    values: dict[str, Any],
    status: str = "editing",
    task_id: str | None = None,
    revision: int = 1,
    field_errors: dict[str, str] | None = None,
    target: dict[str, Any] | None = None,
    result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    card: dict[str, Any] = {
        "task_id": task_id or str(uuid4()),
        "task_type": task_type,
        "status": status,
        "schema_version": 1,
        "target": target or {},
        "initial_fields": form_fields(task_type, values),
        "field_errors": field_errors or {},
        "media": {"existing": form_fields(task_type, values).get("media_refs", []), "limits": {}},
        "actions": ["publish", "save_draft", "cancel"] if status in EDITABLE_STATUSES else [],
        "revision": revision,
    }
    if result is not None:
        card["result"] = result
    return card


def card_from_task_state(task_state: dict[str, Any], conversation_id: int) -> dict[str, Any]:
    """给旧 Agent 状态补上新卡片，不改变旧 task_state。"""
    task_type = task_state.get("task_type")
    values = task_state.get("slots") or {}
    status_map = {
        "awaiting_details": "editing",
        "awaiting_reference_images": "editing",
        "awaiting_confirmation": "editing",
        "completed": "published",
        "cancelled": "cancelled",
        "failed": "failed",
    }
    card = make_form_card(
        task_type,
        values=values,
        status=status_map.get(task_state.get("status"), task_state.get("status", "editing")),
        task_id=task_state.get("task_id"),
        revision=int(task_state.get("revision") or 1),
        field_errors={},
        target={key: values[key] for key in ("project_id", "work_id", "package_id", "photographer_id") if values.get(key)},
    )
    task_state["task_id"] = card["task_id"]
    task_state["revision"] = card["revision"]
    card["initial_fields"] = form_fields(task_type, values)
    card["conversation_id"] = conversation_id
    return card


def submit_form_task(
    db: Session,
    *,
    user_id: int,
    conversation_id: int,
    message_id: int,
    submission: dict[str, Any],
) -> dict[str, Any]:
    """执行新协议提交，所有业务写入仍委托现有 service/tool。"""
    current = validate_revision(db, conversation_id, submission)
    task_type = submission["task_type"]
    values = form_fields(task_type, submission["form_data"])
    task_id = submission.get("task_id") or (current or {}).get("task_id") or str(uuid4())
    next_revision = submission["revision"] + 1

    if submission["action"] == "cancel":
        card = make_form_card(task_type, values=values, status="cancelled", task_id=task_id, revision=next_revision)
        return {"content": "已取消当前任务，已回到普通聊天。", "metadata": {"agent_form_card": card, "task_state": {"task_type": task_type, "status": "cancelled", "task_id": task_id, "revision": next_revision}}}
    if submission["action"] == "save_draft":
        card = make_form_card(task_type, values=values, status="draft_unavailable", task_id=task_id, revision=next_revision)
        return {"content": "草稿箱暂未开放，当前内容仍保留在这张卡片中。", "metadata": {"agent_form_card": card, "task_state": {"task_type": task_type, "status": "blocked", "task_id": task_id, "revision": next_revision}}}

    tool_call: dict[str, Any] | None = None
    result: dict[str, Any] = {}
    try:
        if task_type == "create_project":
            payload = dict(values)
            payload["publish"] = True
            tool_call = create_project(db, user_id=user_id, conversation_id=conversation_id, message_id=message_id, project_payload=payload, idempotency_key=submission["idempotency_key"])
        elif task_type == "publish_package":
            tool_call = publish_package(db, user_id=user_id, conversation_id=conversation_id, message_id=message_id, package_payload=values, idempotency_key=submission["idempotency_key"])
        elif task_type == "create_booking":
            tool_call = create_booking(db, user_id=user_id, conversation_id=conversation_id, message_id=message_id, booking_payload=values, idempotency_key=submission["idempotency_key"])
        elif task_type == "project_application":
            project = project_service.get_project_by_id(db, int(values["project_id"]))
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            application = project_service.apply_project(db, project, user_id, ProjectApplicationCreate(**{key: values[key] for key in ("proposal_text", "price_quote", "package_snapshot", "portfolio_refs", "revision_note")}))
            result = {"application_id": application.id, "project_id": application.project_id, "status": str(application.status.value if hasattr(application.status, "value") else application.status)}
        elif task_type == "publish_work":
            profile = db.query(PhotographerProfile).filter(PhotographerProfile.user_id == user_id).first()
            if not profile:
                raise HTTPException(status_code=404, detail="摄影师资料不存在")
            found = False
            portfolio = []
            for item in list(profile.portfolio or []):
                next_item = dict(item)
                if str(next_item.get("id") or "") == str(values["work_id"]):
                    next_item.update(PortfolioItemUpdate(**{key: values[key] for key in ("title", "tags", "description")}).model_dump())
                    found = True
                portfolio.append(next_item)
            if not found:
                raise HTTPException(status_code=404, detail="作品不存在")
            profile.portfolio = portfolio
            db.commit()
            result = {"work_id": values["work_id"], "title": values["title"]}
    except (HTTPException, ValueError, TypeError, KeyError) as exc:
        error = getattr(exc, "detail", None) or str(exc)
        card = make_form_card(task_type, values=values, status="invalid", task_id=task_id, revision=next_revision, field_errors={"_form": error})
        return {"content": f"提交失败：{error}。请修改卡片后重试。", "metadata": {"agent_form_card": card, "task_state": {"task_type": task_type, "status": "failed", "task_id": task_id, "revision": next_revision, "field_errors": {"_form": error}}}}

    if tool_call is not None:
        result = tool_call.get("result") or {}
        success = tool_call.get("status") == "success"
    else:
        success = True
    status = "published" if success else "invalid"
    error = result.get("error") if not success else None
    card = make_form_card(task_type, values=values, status=status, task_id=task_id, revision=next_revision, field_errors={"_form": str(error)} if error else {}, result=result)
    card["idempotency_key"] = submission["idempotency_key"]
    content = "提交成功，业务资源已经创建。" if success else f"提交失败：{error or '业务校验未通过'}。"
    return {"content": content, "metadata": {"agent_form_card": card, "task_state": {"task_type": task_type, "status": "completed" if success else "failed", "task_id": task_id, "revision": next_revision, "pending_action": None}, "form_result": result}}
