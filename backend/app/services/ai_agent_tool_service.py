"""AI 智能体工具服务：封装关注、建单、发布套餐等工具调用，并记录执行日志。"""

from time import perf_counter
from datetime import date
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.app.core.cache import cache_delete, cache_delete_pattern
from backend.app.models.ai_conversation import AgentActionLog
from backend.app.models.photographer import PhotographerProfile
from backend.app.models.user import User
from backend.app.schemas.photographer import PackageSchema
from backend.app.schemas.recommendation import PackageRecommendationQuery
from backend.app.schemas.project import ProjectCreate
from backend.app.schemas.order import OrderCreateRequest
from backend.app.schemas.inspiration import InspirationCreate
from backend.app.services import follow_service
from backend.app.services import photographer_service
from backend.app.services import project_service
from backend.app.services.order_service import create_order as create_order_service
from backend.app.services.package_recommendation_service import recommend_packages
from backend.app.services import inspiration_service
from backend.app.services.ai_tool_policy_service import (
    ToolExecutionPreparation,
    prepare_tool_execution,
    replay_tool_call,
)
from backend.app.utils.file_upload import create_thumbnail_for_url


def log_agent_action(
    db: Session,
    *,
    user_id: int,
    conversation_id: int,
    message_id: int | None,
    tool_name: str,
    tool_input: dict[str, Any],
    tool_result: dict[str, Any],
    status: str,
    preparation: ToolExecutionPreparation | None = None,
    confirmation_count: int = 0,
    duration_ms: int | None = None,
    error_code: str | None = None,
    commit: bool = True,
) -> AgentActionLog:
    """记录一次智能体工具调用的执行日志。"""
    log = AgentActionLog(
        user_id=user_id,
        conversation_id=conversation_id,
        message_id=message_id,
        tool_name=tool_name,
        tool_input=tool_input,
        tool_result=tool_result,
        status=status,
        tool_schema_version=preparation.spec.schema_version if preparation else None,
        risk_level=preparation.spec.risk_level.value if preparation else None,
        confirmation_policy=preparation.spec.confirmation_policy.value if preparation else None,
        confirmation_count=confirmation_count,
        idempotency_key=preparation.idempotency_key if preparation else None,
        duration_ms=duration_ms,
        error_code=error_code,
    )
    db.add(log)
    if commit:
        db.commit()
        db.refresh(log)
    else:
        db.flush()
    return log


def _policy_metadata(
    preparation: ToolExecutionPreparation,
    *,
    confirmation_count: int,
) -> dict[str, Any]:
    """提取工具执行策略元数据（风险等级、确认策略、幂等键等）。"""
    return {
        "schema_version": preparation.spec.schema_version,
        "risk_level": preparation.spec.risk_level.value,
        "confirmation_policy": preparation.spec.confirmation_policy.value,
        "confirmation_count": confirmation_count,
        "idempotency_key": preparation.idempotency_key,
        "retryable": preparation.spec.retryable,
        "timeout_seconds": preparation.spec.timeout_seconds,
        "compensation": preparation.spec.compensation,
        "action_summary": preparation.action_summary,
        "replayed": False,
    }


def follow_photographer(
    db: Session,
    *,
    user_id: int,
    conversation_id: int,
    message_id: int | None,
    photographer_id: int,
    confirmation_count: int = 1,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """关注摄影师：带确认与幂等控制，并记录工具执行日志。"""
    started_at = perf_counter()
    preparation = prepare_tool_execution(
        db,
        tool_name="follow_photographer",
        tool_input={"photographer_id": photographer_id},
        user_id=user_id,
        conversation_id=conversation_id,
        confirmation_count=confirmation_count,
        idempotency_key=idempotency_key,
    )
    if preparation.existing_log:
        return replay_tool_call(preparation.existing_log)
    tool_input = preparation.normalized_input
    target = db.query(User).filter(User.id == photographer_id).first()
    if not target:
        result = {"followed": False, "error": "photographer_not_found"}
        log_agent_action(
            db,
            user_id=user_id,
            conversation_id=conversation_id,
            message_id=message_id,
            tool_name="follow_photographer",
            tool_input=tool_input,
            tool_result=result,
            status="failed",
            preparation=preparation,
            confirmation_count=confirmation_count,
            duration_ms=round((perf_counter() - started_at) * 1000),
            error_code="photographer_not_found",
        )
        return {
            "tool": "follow_photographer",
            "status": "failed",
            "input": tool_input,
            "result": result,
            "policy": _policy_metadata(preparation, confirmation_count=confirmation_count),
        }

    try:
        follow_result = follow_service.follow_user(db, user_id, photographer_id)
    except ValueError as exc:
        result = {"followed": False, "error": str(exc)}
        status = "failed"
    else:
        result = {
            "followed": follow_result["following"],
            "created": follow_result["created"],
            "photographer_id": photographer_id,
            "photographer_name": target.display_name,
            "follower_count": follow_result["follower_count"],
            "following_count": follow_result["following_count"],
        }
        status = "success"

    log_agent_action(
        db,
        user_id=user_id,
        conversation_id=conversation_id,
        message_id=message_id,
        tool_name="follow_photographer",
        tool_input=tool_input,
        tool_result=result,
        status=status,
        preparation=preparation,
        confirmation_count=confirmation_count,
        duration_ms=round((perf_counter() - started_at) * 1000),
        error_code=result.get("error") if status == "failed" else None,
    )
    return {
        "tool": "follow_photographer",
        "status": status,
        "input": tool_input,
        "result": result,
        "policy": _policy_metadata(preparation, confirmation_count=confirmation_count),
    }


def create_project(
    db: Session,
    *,
    user_id: int,
    conversation_id: int,
    message_id: int | None,
    project_payload: dict[str, Any],
    confirmation_count: int = 1,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """创建拍摄企划：带确认与幂等控制，并记录工具执行日志。"""
    started_at = perf_counter()
    preparation = prepare_tool_execution(
        db,
        tool_name="create_project",
        tool_input=project_payload,
        user_id=user_id,
        conversation_id=conversation_id,
        confirmation_count=confirmation_count,
        idempotency_key=idempotency_key,
    )
    if preparation.existing_log:
        return replay_tool_call(preparation.existing_log)
    tool_input = preparation.normalized_input
    try:
        data = ProjectCreate(**tool_input)
        project = project_service.create_project(db, user_id, data)
    except (HTTPException, ValueError) as exc:
        result = {
            "created": False,
            "error": getattr(exc, "detail", None) or str(exc),
        }
        status = "failed"
    else:
        status_value = project.status.value if hasattr(project.status, "value") else str(project.status)
        result = {
            "created": True,
            "project_id": project.id,
            "title": project.title,
            "city": project.city,
            "status": status_value,
            "budget_min": project.budget_min,
            "budget_max": project.budget_max,
            "shoot_date_start": project.shoot_date_start.isoformat() if project.shoot_date_start else None,
            "shoot_date_end": project.shoot_date_end.isoformat() if project.shoot_date_end else None,
        }
        status = "success"

    log_agent_action(
        db,
        user_id=user_id,
        conversation_id=conversation_id,
        message_id=message_id,
        tool_name="create_project",
        tool_input=tool_input,
        tool_result=result,
        status=status,
        preparation=preparation,
        confirmation_count=confirmation_count,
        duration_ms=round((perf_counter() - started_at) * 1000),
        error_code=str(result.get("error")) if status == "failed" else None,
    )
    return {
        "tool": "create_project",
        "status": status,
        "input": tool_input,
        "result": result,
        "policy": _policy_metadata(preparation, confirmation_count=confirmation_count),
    }


def publish_package(
    db: Session,
    *,
    user_id: int,
    conversation_id: int,
    message_id: int | None,
    package_payload: dict[str, Any],
    confirmation_count: int = 1,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """发布摄影师套餐：带确认与幂等控制，并记录工具执行日志。"""
    started_at = perf_counter()
    preparation = prepare_tool_execution(
        db,
        tool_name="publish_package",
        tool_input=package_payload,
        user_id=user_id,
        conversation_id=conversation_id,
        confirmation_count=confirmation_count,
        idempotency_key=idempotency_key,
    )
    if preparation.existing_log:
        return replay_tool_call(preparation.existing_log)
    tool_input = preparation.normalized_input
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user or user.role != "photographer":
            raise ValueError("only_photographer_can_publish_package")

        package_data = PackageSchema(**tool_input).model_dump(exclude_none=True)
        samples = package_data.get("samples") or []
        if samples:
            package_data["sample_thumbnails"] = [
                create_thumbnail_for_url(url) or ""
                for url in samples
            ]

        profile = db.query(PhotographerProfile).filter(
            PhotographerProfile.user_id == user_id
        ).first()
        packages = list((profile.packages if profile else None) or [])
        packages.append(package_data)
        profile = photographer_service.create_or_update_profile(
            db,
            user_id,
            {"packages": packages},
        )
        saved_package = (profile.packages or [])[-1]

        cache_delete(f"photographer:{user_id}")
        cache_delete_pattern("photographer_packages*")
        cache_delete_pattern("photographer_list:*")

        result = {
            "published": True,
            "package_id": saved_package.get("id"),
            "package_name": saved_package.get("name"),
            "price": saved_package.get("price"),
            "duration": saved_package.get("duration"),
            "image_count": saved_package.get("image_count"),
            "city": saved_package.get("city"),
        }
        status = "success"
    except (HTTPException, ValueError) as exc:
        result = {
            "published": False,
            "error": getattr(exc, "detail", None) or str(exc),
        }
        status = "failed"

    log_agent_action(
        db,
        user_id=user_id,
        conversation_id=conversation_id,
        message_id=message_id,
        tool_name="publish_package",
        tool_input=tool_input,
        tool_result=result,
        status=status,
        preparation=preparation,
        confirmation_count=confirmation_count,
        duration_ms=round((perf_counter() - started_at) * 1000),
        error_code=str(result.get("error")) if status == "failed" else None,
    )
    return {
        "tool": "publish_package",
        "status": status,
        "input": tool_input,
        "result": result,
        "policy": _policy_metadata(preparation, confirmation_count=confirmation_count),
    }


def get_available_slots(
    db: Session,
    *,
    photographer_id: int,
    package_duration: int = 120,
    date_str: str | None = None,
) -> dict[str, Any]:
    """查询摄影师的可用时间段（只读操作，不记录 action log）"""
    from backend.app.services.ai_booking_service import get_available_slots as _query_slots
    return _query_slots(
        db,
        photographer_id=photographer_id,
        package_duration=package_duration,
        date_str=date_str,
    )


def create_booking(
    db: Session,
    *,
    user_id: int,
    conversation_id: int,
    message_id: int | None,
    booking_payload: dict[str, Any],
    confirmation_count: int = 1,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """创建预约订单（写操作，记录 action log）"""
    started_at = perf_counter()
    preparation = prepare_tool_execution(
        db,
        tool_name="create_booking",
        tool_input=booking_payload,
        user_id=user_id,
        conversation_id=conversation_id,
        confirmation_count=confirmation_count,
        idempotency_key=idempotency_key,
    )
    if preparation.existing_log:
        return replay_tool_call(preparation.existing_log)
    tool_input = preparation.normalized_input
    try:
        # 构造 OrderCreateRequest
        photographer_id = tool_input.get("photographer_id")
        package_id = tool_input.get("package_id")
        package_description = tool_input.get("package_description", "")
        appointment_date_str = tool_input.get("appointment_date")
        if not appointment_date_str:
            legacy_time = tool_input.get("appointment_time")
            appointment_date_str = str(legacy_time)[:10] if legacy_time else None
        duration_minutes = tool_input.get("duration_minutes", 120)
        notes = tool_input.get("notes")

        appointment_date = _parse_booking_date(appointment_date_str)
        if not appointment_date or not photographer_id:
            raise ValueError("缺少必要参数：photographer_id, appointment_date")

        data = OrderCreateRequest(
            package_id=package_id,
            photographer_id=photographer_id,
            package_description=package_description,
            appointment_date=appointment_date,
            duration_minutes=duration_minutes,
            notes=notes,
        )
        order = create_order_service(db, user_id, data)

        result = {
            "order_id": order.id,
            "status": order.status.value if hasattr(order.status, "value") else str(order.status),
            "photographer_id": order.photographer_id,
            "appointment_date": order.appointment_time.date().isoformat(),
            "duration_minutes": order.duration_minutes,
            "package_snapshot": order.package_snapshot,
        }
        status = "success"
    except (HTTPException, ValueError) as exc:
        result = {
            "order_id": None,
            "error": getattr(exc, "detail", None) or str(exc),
        }
        status = "failed"

    log_agent_action(
        db,
        user_id=user_id,
        conversation_id=conversation_id,
        message_id=message_id,
        tool_name="create_booking",
        tool_input=tool_input,
        tool_result=result,
        status=status,
        preparation=preparation,
        confirmation_count=confirmation_count,
        duration_ms=round((perf_counter() - started_at) * 1000),
        error_code=str(result.get("error")) if status == "failed" else None,
    )
    return {
        "tool": "create_booking",
        "status": status,
        "input": tool_input,
        "result": result,
        "policy": _policy_metadata(preparation, confirmation_count=confirmation_count),
    }


def _parse_booking_date(value: Any) -> date | None:
    """Normalize current and legacy agent date values without requiring a time."""
    if not value:
        return None
    if isinstance(value, date):
        return value

    raw = str(value).strip()
    try:
        return date.fromisoformat(raw)
    except ValueError:
        pass

    try:
        month, day = (int(part) for part in raw.split("-", 1))
        today = date.today()
        parsed = date(today.year, month, day)
        if parsed < today:
            parsed = date(today.year + 1, month, day)
        return parsed
    except (TypeError, ValueError):
        return None


def search_bookable_packages(
    db: Session,
    *,
    query_payload: dict[str, Any],
    viewer_user_id: int | None = None,
    session_id: str | None = None,
    cursor: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """Read-only joint recommendation tool for the booking agent."""
    query = PackageRecommendationQuery.model_validate(query_payload)
    result = recommend_packages(db, viewer_user_id, cursor, limit, query, session_id)
    return {
        "tool": "search_bookable_packages",
        "status": "success" if result["items"] else "empty",
        "input": query.model_dump(mode="json", exclude_none=True),
        "result": result,
        "policy": {
            "risk_level": "read_only",
            "confirmation_policy": "none",
            "retryable": True,
            "idempotent": True,
            "timeout_seconds": 15,
        },
    }


def create_inspiration_draft(
    db: Session,
    *,
    user_id: int,
    conversation_id: int,
    message_id: int | None,
    inspiration_payload: dict[str, Any],
    idempotency_key: str | None = None,
    commit: bool = True,
) -> dict[str, Any]:
    """Create a private draft from trusted URLs and validated Agent content."""
    started_at = perf_counter()
    payload = {**inspiration_payload, "status": "draft"}
    preparation = prepare_tool_execution(
        db,
        tool_name="create_inspiration_draft",
        tool_input=payload,
        user_id=user_id,
        conversation_id=conversation_id,
        confirmation_count=0,
        idempotency_key=idempotency_key,
    )
    if preparation.existing_log:
        return replay_tool_call(preparation.existing_log)
    tool_input = preparation.normalized_input
    try:
        inspiration = inspiration_service.create_inspiration(
            db, user_id, InspirationCreate.model_validate(tool_input), commit=commit
        )
        result = {
            "created": True,
            "inspiration_id": inspiration.id,
            "status": "draft",
            "title": inspiration.title,
            "cover_url": inspiration.cover_url,
        }
        call_status = "success"
    except (HTTPException, ValueError, TypeError) as exc:
        result = {"created": False, "error": getattr(exc, "detail", None) or str(exc)}
        call_status = "failed"
    log_agent_action(
        db,
        user_id=user_id,
        conversation_id=conversation_id,
        message_id=message_id,
        tool_name="create_inspiration_draft",
        tool_input=tool_input,
        tool_result=result,
        status=call_status,
        preparation=preparation,
        confirmation_count=0,
        duration_ms=round((perf_counter() - started_at) * 1000),
        error_code=str(result.get("error")) if call_status == "failed" else None,
        commit=commit,
    )
    return {
        "tool": "create_inspiration_draft",
        "status": call_status,
        "input": tool_input,
        "result": result,
        "policy": _policy_metadata(preparation, confirmation_count=0),
    }
