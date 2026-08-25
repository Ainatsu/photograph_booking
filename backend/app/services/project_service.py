"""企划项目的业务逻辑服务。"""

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import cast, or_, String
from sqlalchemy.orm import Session, joinedload

from backend.app.models.order import Order, OrderStatus
from backend.app.models.photographer import PhotographerProfile
from backend.app.models.project import (
    ProjectApplication,
    ProjectApplicationStatus,
    ProjectEvent,
    ProjectStatus,
    ShootProject,
)
from backend.app.models.user import User
from backend.app.schemas.project import (
    ProjectApplicationCreate,
    ProjectApplicationUpdate,
    ProjectCreate,
    ProjectUpdate,
)
from backend.app.services.order_service import (
    _ensure_photographer_available,
    _normalize_appointment,
    record_order_event,
)
from backend.app.services.order_contract_service import (
    build_project_contract_snapshot,
    contract_to_order_fields,
)


def _status_value(value) -> str:
    """返回枚举值或字符串形式的状态值。"""
    return value.value if hasattr(value, "value") else str(value)


def _now_naive_utc() -> datetime:
    """返回不带时区信息的当前 UTC 时间。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _normalize_datetime(value: datetime | None) -> datetime | None:
    """将可选的 datetime 统一规范化，None 原样返回。"""
    if value is None:
        return None
    return _normalize_appointment(value)


def _require_owner(project: ShootProject, customer_id: int) -> None:
    """校验当前用户是否为项目所有者，否则抛出 403。"""
    if project.customer_id != customer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the project owner can perform this action",
        )


def _validate_project_payload(
    values: dict,
    *,
    require_public_fields: bool = False,
    allow_past_expiry: bool = False,
    allow_past_schedule: bool = False,
) -> None:
    """校验预算、拍摄时间、截止时间等字段的合法性。"""
    now = _now_naive_utc()
    budget_min = values.get("budget_min")
    budget_max = values.get("budget_max")
    if budget_min is not None and budget_max is not None and budget_min > budget_max:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="budget_min must be less than or equal to budget_max",
        )

    shoot_start = _normalize_datetime(values.get("shoot_date_start"))
    shoot_end = _normalize_datetime(values.get("shoot_date_end"))
    expires_at = _normalize_datetime(values.get("expires_at"))

    if shoot_start and shoot_start < now and not allow_past_schedule:
        raise HTTPException(status_code=400, detail="shoot_date_start cannot be in the past")
    if shoot_end and shoot_end < now and not allow_past_schedule:
        raise HTTPException(status_code=400, detail="shoot_date_end cannot be in the past")
    if shoot_start and shoot_end and shoot_start > shoot_end:
        raise HTTPException(status_code=400, detail="shoot_date_start cannot be after shoot_date_end")
    if expires_at and expires_at < now and not allow_past_expiry:
        raise HTTPException(status_code=400, detail="expires_at cannot be in the past")
    if expires_at and shoot_start and expires_at >= shoot_start:
        raise HTTPException(status_code=400, detail="expires_at must be before shoot_date_start")

    if require_public_fields:
        required_fields = ["title", "category", "city", "description"]
        missing = [field for field in required_fields if not str(values.get(field) or "").strip()]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required fields for publishing: {', '.join(missing)}",
            )


def _project_values(data: ProjectCreate | ProjectUpdate) -> dict:
    """提取并规范化项目创建/更新的字段值。"""
    values = data.model_dump(exclude_unset=True)
    values.pop("publish", None)
    for field in ["shoot_date_start", "shoot_date_end", "expires_at"]:
        if field in values:
            values[field] = _normalize_datetime(values[field])
    return values


def record_project_event(
    db: Session,
    project_id: int,
    application_id: int | None,
    actor_id: int | None,
    actor_role: str | None,
    event_type: str,
    status_value: ProjectStatus | str,
    note: str | None = None,
) -> ProjectEvent:
    """记录一条项目事件到数据库。"""
    event = ProjectEvent(
        project_id=project_id,
        application_id=application_id,
        actor_id=actor_id,
        actor_role=actor_role,
        event_type=event_type,
        status=_status_value(status_value),
        note=note,
    )
    db.add(event)
    db.flush()
    db.refresh(event)
    return event


def _enqueue_project_notification(
    db: Session,
    *,
    project_id: int,
    event_id: int | None,
    event_type: str,
    recipient_ids: list[int],
    content: str,
    application_id: int | None = None,
) -> None:
    """排队发送项目相关的站内通知。"""
    from backend.app.services.notification_service import enqueue_project_notification

    enqueue_project_notification(
        db,
        project_id=project_id,
        event_key=f"event:{event_id or event_type}:{event_type}",
        event_type=event_type,
        recipient_ids=recipient_ids,
        content=content,
        application_id=application_id,
    )


def _is_project_expired(project: ShootProject) -> bool:
    """判断公开项目是否已超过截止时间或拍摄时间。"""
    if project.status != ProjectStatus.OPEN:
        return False
    expires_at = _normalize_datetime(project.expires_at)
    shoot_start = _normalize_datetime(project.shoot_date_start)
    now = _now_naive_utc()
    return bool((expires_at and expires_at <= now) or (shoot_start and shoot_start <= now))


def _mark_project_expired(db: Session, project: ShootProject) -> None:
    """将项目标记为已过期并拒绝所有待处理应邀。"""
    project.status = ProjectStatus.EXPIRED
    pending_ids = [row[0] for row in db.query(ProjectApplication.photographer_id).filter(
        ProjectApplication.project_id == project.id,
        ProjectApplication.status == ProjectApplicationStatus.SUBMITTED,
    ).all()]
    (
        db.query(ProjectApplication)
        .filter(
            ProjectApplication.project_id == project.id,
            ProjectApplication.status == ProjectApplicationStatus.SUBMITTED,
        )
        .update({"status": ProjectApplicationStatus.REJECTED}, synchronize_session=False)
    )
    event = record_project_event(
        db,
        project.id,
        None,
        None,
        "system",
        "expired",
        ProjectStatus.EXPIRED,
        "Project expired after its deadline",
    )
    _enqueue_project_notification(
        db,
        project_id=project.id,
        event_id=event.id,
        event_type="project_expired",
        recipient_ids=pending_ids,
        content=f"企划「{project.title}」已到招募截止时间，未选中的应邀已关闭。",
    )


def expire_project_if_needed(db: Session, project: ShootProject) -> bool:
    """若项目已过期则执行过期处理，返回是否发生处理。"""
    if not _is_project_expired(project):
        return False
    _mark_project_expired(db, project)
    db.commit()
    db.refresh(project)
    return True


def expire_open_projects(db: Session) -> int:
    """批量过期所有到期未处理的公开项目，返回处理数量。"""
    now = _now_naive_utc()
    projects = (
        db.query(ShootProject)
        .filter(
            ShootProject.status == ProjectStatus.OPEN,
            or_(
                ShootProject.expires_at <= now,
                ShootProject.shoot_date_start <= now,
            ),
        )
        .all()
    )
    if not projects:
        return 0

    for project in projects:
        _mark_project_expired(db, project)
    db.commit()
    return len(projects)


def _project_summary(project: ShootProject) -> dict:
    """生成项目的简要信息字典。"""
    return {
        "id": project.id,
        "title": project.title,
        "category": project.category,
        "city": project.city,
        "status": _status_value(project.status),
        "budget_min": project.budget_min,
        "budget_max": project.budget_max,
        "shoot_date_start": project.shoot_date_start,
        "converted_order_id": project.converted_order_id,
    }


def _format_deliverables_for_response(value):
    """将交付物字段格式化为便于展示的字符串。"""
    if value is None:
        return None
    if isinstance(value, str):
        normalized = value.strip()
        return normalized or None
    if not isinstance(value, dict):
        return str(value).strip() or None

    if isinstance(value.get("text"), str) and value["text"].strip():
        return value["text"].strip()

    parts = []
    if value.get("retouched") is not None:
        parts.append(f"精修 {value['retouched']} 张")
    if value.get("raw"):
        parts.append("交付底片")
    if value.get("video"):
        parts.append("包含短视频")

    known_keys = {"retouched", "raw", "video", "text", "source", "people_count"}
    for key, item in value.items():
        if key in known_keys or item in (None, "", [], {}):
            continue
        parts.append(f"{key}：{item}")

    return "，".join(parts) if parts else None


def serialize_project(
    db: Session,
    project: ShootProject,
    current_user: User | None = None,
) -> dict:
    """序列化项目为接口响应字典。"""
    application_count = (
        db.query(ProjectApplication)
        .filter(
            ProjectApplication.project_id == project.id,
            ProjectApplication.status != ProjectApplicationStatus.WITHDRAWN,
        )
        .count()
    )
    my_application_id = None
    if current_user and current_user.role == "photographer":
        my_application = (
            db.query(ProjectApplication)
            .filter(
                ProjectApplication.project_id == project.id,
                ProjectApplication.photographer_id == current_user.id,
            )
            .first()
        )
        my_application_id = my_application.id if my_application else None

    return {
        "id": project.id,
        "customer_id": project.customer_id,
        "customer_name": project.customer.display_name if project.customer else None,
        "customer_avatar_url": project.customer.avatar_url if project.customer else None,
        "title": project.title,
        "description": project.description,
        "category": project.category,
        "style_tags": project.style_tags or [],
        "city": project.city,
        "location_text": project.location_text,
        "location_name": project.location_name,
        "location_address": project.location_address,
        "location_latitude": project.location_latitude,
        "location_longitude": project.location_longitude,
        "location_place_id": project.location_place_id,
        "location_provider": project.location_provider,
        "coordinate_system": project.coordinate_system,
        "location_precision": project.location_precision,
        "shoot_date_start": project.shoot_date_start,
        "shoot_date_end": project.shoot_date_end,
        "duration_minutes": project.duration_minutes,
        "budget_min": project.budget_min,
        "budget_max": project.budget_max,
        "deliverables": _format_deliverables_for_response(project.deliverables),
        "reference_images": project.reference_images or [],
        "visibility": project.visibility,
        "status": _status_value(project.status),
        "selected_application_id": project.selected_application_id,
        "converted_order_id": project.converted_order_id,
        "expires_at": project.expires_at,
        "application_count": application_count,
        "my_application_id": my_application_id,
        "created_at": project.created_at,
        "updated_at": project.updated_at,
    }


def serialize_application(
    db: Session,
    application: ProjectApplication,
    include_project: bool = False,
) -> dict:
    """序列化项目应邀为接口响应字典。"""
    photographer = application.photographer
    profile = (
        db.query(PhotographerProfile)
        .filter(PhotographerProfile.user_id == application.photographer_id)
        .first()
    )
    proposal_text = application.proposal_text or ""
    if application.included_items:
        included = application.included_items
        if isinstance(included, list):
            included = "、".join(str(item) for item in included if item)
        if included and str(included) not in proposal_text:
            proposal_text = f"{proposal_text}\n\n包含内容：{included}"
    payload = {
        "id": application.id,
        "project_id": application.project_id,
        "photographer_id": application.photographer_id,
        "photographer_name": photographer.display_name if photographer else None,
        "photographer_avatar_url": photographer.avatar_url if photographer else None,
        "photographer_city": profile.location if profile else None,
        "photographer_equipment": profile.equipment if profile else None,
        "photographer_styles": profile.styles if profile else None,
        "photographer_portfolio": profile.portfolio if profile else None,
        "status": _status_value(application.status),
        "proposal_text": proposal_text,
        "price_quote": application.price_quote,
        "package_snapshot": application.package_snapshot,
        "portfolio_refs": application.portfolio_refs,
        "revision_note": application.revision_note,
        "created_at": application.created_at,
        "updated_at": application.updated_at,
    }
    if include_project and application.project:
        payload["project"] = _project_summary(application.project)
    return payload


def serialize_event(event: ProjectEvent) -> dict:
    """序列化项目事件为接口响应字典。"""
    return {
        "id": event.id,
        "project_id": event.project_id,
        "application_id": event.application_id,
        "actor_id": event.actor_id,
        "actor_role": event.actor_role,
        "event_type": event.event_type,
        "status": event.status,
        "note": event.note,
        "created_at": event.created_at,
    }


def create_project(db: Session, customer_id: int, data: ProjectCreate) -> ShootProject:
    """创建新的拍摄企划项目。"""
    values = _project_values(data)
    _validate_project_payload(values, require_public_fields=data.publish)
    project = ShootProject(
        customer_id=customer_id,
        status=ProjectStatus.OPEN if data.publish else ProjectStatus.DRAFT,
        **values,
    )
    db.add(project)
    db.flush()
    record_project_event(
        db,
        project.id,
        None,
        customer_id,
        "customer",
        "published" if data.publish else "created",
        project.status,
        "Project published" if data.publish else "Project draft created",
    )
    db.commit()
    db.refresh(project)
    return project


def publish_project(db: Session, project: ShootProject, customer_id: int) -> ShootProject:
    """发布企划项目，使其对摄影师公开可见。"""
    _require_owner(project, customer_id)
    expire_project_if_needed(db, project)
    if project.status == ProjectStatus.OPEN:
        return project
    if project.status not in [ProjectStatus.DRAFT, ProjectStatus.EXPIRED]:
        raise HTTPException(status_code=400, detail="Only draft or expired projects can be published")
    values = {
        "title": project.title,
        "description": project.description,
        "category": project.category,
        "city": project.city,
        "budget_min": project.budget_min,
        "budget_max": project.budget_max,
        "shoot_date_start": project.shoot_date_start,
        "shoot_date_end": project.shoot_date_end,
        "expires_at": project.expires_at,
    }
    _validate_project_payload(values, require_public_fields=True)
    project.status = ProjectStatus.OPEN
    record_project_event(
        db,
        project.id,
        None,
        customer_id,
        "customer",
        "published",
        ProjectStatus.OPEN,
        "Project published",
    )
    db.commit()
    db.refresh(project)
    return project


def update_project(
    db: Session,
    project: ShootProject,
    customer_id: int,
    data: ProjectUpdate,
) -> ShootProject:
    """更新企划项目的字段内容。"""
    _require_owner(project, customer_id)
    expire_project_if_needed(db, project)
    if project.status not in [ProjectStatus.DRAFT, ProjectStatus.OPEN, ProjectStatus.EXPIRED]:
        raise HTTPException(status_code=400, detail="This project can no longer be edited")

    values = _project_values(data)
    merged = {
        "title": project.title,
        "description": project.description,
        "category": project.category,
        "city": project.city,
        "budget_min": project.budget_min,
        "budget_max": project.budget_max,
        "shoot_date_start": project.shoot_date_start,
        "shoot_date_end": project.shoot_date_end,
        "expires_at": project.expires_at,
    }
    merged.update(values)
    _validate_project_payload(
        merged,
        require_public_fields=project.status == ProjectStatus.OPEN,
        allow_past_expiry=project.status == ProjectStatus.EXPIRED,
        allow_past_schedule=project.status == ProjectStatus.EXPIRED,
    )

    for key, value in values.items():
        setattr(project, key, value)
    record_project_event(
        db,
        project.id,
        None,
        customer_id,
        "customer",
        "updated",
        project.status,
        "Project updated",
    )
    db.commit()
    db.refresh(project)
    return project


def close_project(
    db: Session,
    project: ShootProject,
    customer_id: int,
    reason: str | None = None,
) -> ShootProject:
    """关闭企划项目并拒绝所有待处理应邀。"""
    _require_owner(project, customer_id)
    expire_project_if_needed(db, project)
    if project.status not in [ProjectStatus.DRAFT, ProjectStatus.OPEN]:
        raise HTTPException(status_code=400, detail="This project cannot be closed")
    project.status = ProjectStatus.CLOSED
    pending_ids = [row[0] for row in db.query(ProjectApplication.photographer_id).filter(
        ProjectApplication.project_id == project.id,
        ProjectApplication.status == ProjectApplicationStatus.SUBMITTED,
    ).all()]
    (
        db.query(ProjectApplication)
        .filter(
            ProjectApplication.project_id == project.id,
            ProjectApplication.status == ProjectApplicationStatus.SUBMITTED,
        )
        .update({"status": ProjectApplicationStatus.REJECTED}, synchronize_session=False)
    )
    event = record_project_event(
        db,
        project.id,
        None,
        customer_id,
        "customer",
        "closed",
        ProjectStatus.CLOSED,
        reason or "Project closed",
    )
    _enqueue_project_notification(
        db,
        project_id=project.id,
        event_id=event.id,
        event_type="project_closed",
        recipient_ids=pending_ids,
        content=f"企划「{project.title}」已关闭，当前应邀不再继续处理。",
    )
    db.commit()
    db.refresh(project)
    return project


def get_project_by_id(db: Session, project_id: int) -> ShootProject | None:
    """按 ID 查询企划项目。"""
    return (
        db.query(ShootProject)
        .options(joinedload(ShootProject.customer))
        .filter(ShootProject.id == project_id)
        .first()
    )


def ensure_project_visible(project: ShootProject, user: User | None, db: Session) -> None:
    """校验当前用户是否有权查看该项目，否则抛出 403。"""
    expire_project_if_needed(db, project)
    if project.status == ProjectStatus.OPEN and project.visibility == "public":
        return
    if user and (user.is_admin or project.customer_id == user.id):
        return
    if user and user.role == "photographer":
        has_application = (
            db.query(ProjectApplication.id)
            .filter(
                ProjectApplication.project_id == project.id,
                ProjectApplication.photographer_id == user.id,
            )
            .first()
        )
        if has_application:
            return
    raise HTTPException(status_code=403, detail="You cannot view this project")


def list_open_projects(
    db: Session,
    city: str | None = None,
    category: str | None = None,
    budget_min: int | None = None,
    budget_max: int | None = None,
    style_tags: str | None = None,
    customer_id: int | None = None,
    skip: int = 0,
    limit: int = 20,
    query_text: str | None = None,
) -> list[ShootProject]:
    """按筛选条件分页查询公开的企划项目。"""
    expire_open_projects(db)
    query = (
        db.query(ShootProject)
        .options(joinedload(ShootProject.customer))
        .filter(
            ShootProject.status == ProjectStatus.OPEN,
            ShootProject.visibility == "public",
        )
    )
    if city:
        query = query.filter(ShootProject.city.ilike(f"%{city}%"))
    if category:
        query = query.filter(ShootProject.category == category)
    if style_tags:
        query = query.filter(cast(ShootProject.style_tags, String).contains(style_tags))
    if query_text and query_text.strip():
        pattern = f"%{query_text.strip()}%"
        query = query.filter(or_(
            ShootProject.title.ilike(pattern),
            ShootProject.description.ilike(pattern),
            ShootProject.category.ilike(pattern),
            ShootProject.city.ilike(pattern),
            ShootProject.location_text.ilike(pattern),
            ShootProject.location_name.ilike(pattern),
            ShootProject.location_address.ilike(pattern),
            cast(ShootProject.style_tags, String).ilike(pattern),
        ))
    if budget_min is not None:
        query = query.filter(or_(ShootProject.budget_max.is_(None), ShootProject.budget_max >= budget_min))
    if budget_max is not None:
        query = query.filter(or_(ShootProject.budget_min.is_(None), ShootProject.budget_min <= budget_max))
    if customer_id is not None:
        query = query.filter(ShootProject.customer_id == customer_id)
    return query.order_by(ShootProject.created_at.desc()).offset(skip).limit(limit).all()


def list_my_projects(
    db: Session,
    customer_id: int,
    project_status: ProjectStatus | None = None,
    skip: int = 0,
    limit: int = 20,
) -> list[ShootProject]:
    """分页查询当前用户创建的企划项目。"""
    expire_open_projects(db)
    query = (
        db.query(ShootProject)
        .options(joinedload(ShootProject.customer))
        .filter(ShootProject.customer_id == customer_id)
    )
    if project_status:
        query = query.filter(ShootProject.status == project_status)
    return query.order_by(ShootProject.created_at.desc()).offset(skip).limit(limit).all()


def apply_project(
    db: Session,
    project: ShootProject,
    photographer_id: int,
    data: ProjectApplicationCreate,
) -> ProjectApplication:
    """摄影师提交或重新提交企划应邀。"""
    expire_project_if_needed(db, project)
    if project.status != ProjectStatus.OPEN:
        raise HTTPException(status_code=400, detail="Only open projects can receive applications")
    if project.customer_id == photographer_id:
        raise HTTPException(status_code=400, detail="You cannot apply to your own project")

    existing = (
        db.query(ProjectApplication)
        .filter(
            ProjectApplication.project_id == project.id,
            ProjectApplication.photographer_id == photographer_id,
        )
        .first()
    )
    if existing:
        if existing.status not in [ProjectApplicationStatus.REJECTED, ProjectApplicationStatus.WITHDRAWN]:
            raise HTTPException(status_code=409, detail="You have already applied to this project")

    values = data.model_dump()

    if existing:
        for key, value in values.items():
            setattr(existing, key, value)
        existing.status = ProjectApplicationStatus.SUBMITTED
        application = existing
        event_type = "application_resubmitted"
        note = "Application resubmitted"
    else:
        application = ProjectApplication(
            project_id=project.id,
            photographer_id=photographer_id,
            status=ProjectApplicationStatus.SUBMITTED,
            **values,
        )
        db.add(application)
        db.flush()
        event_type = "applied"
        note = "Application submitted"
    event = record_project_event(
        db,
        project.id,
        application.id,
        photographer_id,
        "photographer",
        event_type,
        project.status,
        note,
    )
    _enqueue_project_notification(
        db,
        project_id=project.id,
        event_id=event.id,
        event_type="project_application_submitted",
        recipient_ids=[project.customer_id],
        application_id=application.id,
        content=f"摄影师已提交「{project.title}」的应邀方案，点击查看并比较候选方案。",
    )
    db.commit()
    db.refresh(application)
    return application


def get_my_application(
    db: Session,
    project_id: int,
    photographer_id: int,
) -> ProjectApplication | None:
    """查询摄影师对某企划的应邀记录。"""
    return (
        db.query(ProjectApplication)
        .options(joinedload(ProjectApplication.project), joinedload(ProjectApplication.photographer))
        .filter(
            ProjectApplication.project_id == project_id,
            ProjectApplication.photographer_id == photographer_id,
        )
        .first()
    )


def update_application(
    db: Session,
    application: ProjectApplication,
    photographer_id: int,
    data: ProjectApplicationUpdate,
) -> ProjectApplication:
    """摄影师更新自己的企划应邀内容。"""
    expire_project_if_needed(db, application.project)
    if application.photographer_id != photographer_id:
        raise HTTPException(status_code=403, detail="You can only update your own application")
    if application.project.status != ProjectStatus.OPEN:
        raise HTTPException(status_code=400, detail="This project no longer accepts application updates")
    if application.status != ProjectApplicationStatus.SUBMITTED:
        raise HTTPException(status_code=400, detail="This application can no longer be updated")
    values = data.model_dump(exclude_unset=True)
    for key, value in values.items():
        setattr(application, key, value)
    if "proposal_text" in values:
        application.included_items = None
    event = record_project_event(
        db,
        application.project_id,
        application.id,
        photographer_id,
        "photographer",
        "application_updated",
        application.project.status,
        application.revision_note or "Application updated",
    )
    _enqueue_project_notification(
        db,
        project_id=application.project_id,
        event_id=event.id,
        event_type="project_application_updated",
        recipient_ids=[application.project.customer_id],
        application_id=application.id,
        content=f"摄影师更新了「{application.project.title}」的应邀方案。",
    )
    db.commit()
    db.refresh(application)
    return application


def withdraw_application(
    db: Session,
    application: ProjectApplication,
    photographer_id: int,
) -> ProjectApplication:
    """摄影师撤回自己的企划应邀。"""
    expire_project_if_needed(db, application.project)
    if application.photographer_id != photographer_id:
        raise HTTPException(status_code=403, detail="You can only withdraw your own application")
    if application.project.status != ProjectStatus.OPEN:
        raise HTTPException(status_code=400, detail="This project can no longer be updated")
    if application.status != ProjectApplicationStatus.SUBMITTED:
        raise HTTPException(status_code=400, detail="This application cannot be withdrawn")
    application.status = ProjectApplicationStatus.WITHDRAWN
    event = record_project_event(
        db,
        application.project_id,
        application.id,
        photographer_id,
        "photographer",
        "application_withdrawn",
        application.project.status,
        "Application withdrawn",
    )
    _enqueue_project_notification(
        db,
        project_id=application.project_id,
        event_id=event.id,
        event_type="project_application_withdrawn",
        recipient_ids=[application.project.customer_id],
        application_id=application.id,
        content=f"摄影师撤回了「{application.project.title}」的应邀方案。",
    )
    db.commit()
    db.refresh(application)
    return application


def list_project_applications(
    db: Session,
    project: ShootProject,
    customer_id: int,
) -> list[ProjectApplication]:
    """列出某企划下的全部应邀。"""
    _require_owner(project, customer_id)
    expire_project_if_needed(db, project)
    return (
        db.query(ProjectApplication)
        .options(joinedload(ProjectApplication.photographer), joinedload(ProjectApplication.project))
        .filter(ProjectApplication.project_id == project.id)
        .order_by(ProjectApplication.created_at.asc(), ProjectApplication.id.asc())
        .all()
    )


def list_my_applications(
    db: Session,
    photographer_id: int,
    application_status: ProjectApplicationStatus | None = None,
    skip: int = 0,
    limit: int = 20,
) -> list[ProjectApplication]:
    """分页查询摄影师提交过的企划应邀。"""
    expire_open_projects(db)
    query = (
        db.query(ProjectApplication)
        .options(joinedload(ProjectApplication.project), joinedload(ProjectApplication.photographer))
        .filter(ProjectApplication.photographer_id == photographer_id)
    )
    if application_status:
        query = query.filter(ProjectApplication.status == application_status)
    return query.order_by(ProjectApplication.created_at.desc()).offset(skip).limit(limit).all()


def get_application_by_id(db: Session, application_id: int) -> ProjectApplication | None:
    """按 ID 查询企划应邀。"""
    return (
        db.query(ProjectApplication)
        .options(joinedload(ProjectApplication.project), joinedload(ProjectApplication.photographer))
        .filter(ProjectApplication.id == application_id)
        .first()
    )


def build_package_snapshot(project: ShootProject, application: ProjectApplication) -> str:
    """根据企划与应邀生成订单套餐快照文本。"""
    duration = project.duration_minutes
    duration_text = f"/{duration} minutes" if duration else ""
    base = application.package_snapshot or project.title
    return f"{base} - CNY {application.price_quote}{duration_text}"


def build_order_notes(project: ShootProject, application: ProjectApplication) -> str:
    """根据企划与应邀生成订单备注文本。"""
    proposal_text = application.proposal_text
    if application.included_items:
        included = application.included_items
        if isinstance(included, list):
            included = "、".join(str(item) for item in included if item)
        if included and str(included) not in proposal_text:
            proposal_text = f"{proposal_text}\n\n包含内容：{included}"
    parts = [
        f"【用户的需求】\n{project.description}",
        f"【自己的提供】\n{proposal_text}",
    ]
    if application.revision_note:
        parts.append(f"【条款事项】\n{application.revision_note}")
    return "\n\n".join(parts)


def select_application(
    db: Session,
    project: ShootProject,
    application: ProjectApplication,
    customer_id: int,
) -> tuple[ShootProject, ProjectApplication, Order]:
    """选定应邀并将企划转化为订单。"""
    _require_owner(project, customer_id)
    expire_project_if_needed(db, project)
    if project.status != ProjectStatus.OPEN:
        raise HTTPException(status_code=400, detail="Only open projects can be converted")
    if application.project_id != project.id:
        raise HTTPException(status_code=400, detail="Application does not belong to this project")
    if application.status != ProjectApplicationStatus.SUBMITTED:
        raise HTTPException(status_code=400, detail="Only submitted applications can be selected")

    appointment_time = project.shoot_date_start
    duration_minutes = project.duration_minutes
    if not appointment_time or not duration_minutes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A confirmed appointment time and duration are required before converting to an order",
        )

    appointment_time = _normalize_datetime(appointment_time)
    _ensure_photographer_available(
        db,
        application.photographer_id,
        appointment_time,
        duration_minutes,
    )

    contract_snapshot = build_project_contract_snapshot(
        project=project,
        application=application,
        appointment_time=appointment_time,
        duration_minutes=duration_minutes,
    )
    order = Order(
        customer_id=project.customer_id,
        photographer_id=application.photographer_id,
        package_snapshot=build_package_snapshot(project, application),
        appointment_time=appointment_time,
        duration_minutes=duration_minutes,
        notes=build_order_notes(project, application),
        status=OrderStatus.PENDING,
        **contract_to_order_fields(contract_snapshot),
    )
    db.add(order)
    db.flush()

    rejected_ids = [row[0] for row in db.query(ProjectApplication.photographer_id).filter(
        ProjectApplication.project_id == project.id,
        ProjectApplication.id != application.id,
        ProjectApplication.status == ProjectApplicationStatus.SUBMITTED,
    ).all()]
    application.status = ProjectApplicationStatus.SELECTED
    (
        db.query(ProjectApplication)
        .filter(
            ProjectApplication.project_id == project.id,
            ProjectApplication.id != application.id,
            ProjectApplication.status == ProjectApplicationStatus.SUBMITTED,
        )
        .update({"status": ProjectApplicationStatus.REJECTED}, synchronize_session=False)
    )
    project.status = ProjectStatus.CONVERTED
    project.selected_application_id = application.id
    project.converted_order_id = order.id

    selected_event = record_project_event(
        db,
        project.id,
        application.id,
        customer_id,
        "customer",
        "selected",
        ProjectStatus.CONVERTED,
        "Application selected and project converted",
    )
    _enqueue_project_notification(
        db,
        project_id=project.id,
        event_id=selected_event.id,
        event_type="project_application_selected",
        recipient_ids=[application.photographer_id],
        application_id=application.id,
        content=f"你的「{project.title}」应邀方案已被选定，订单已经创建。",
    )
    _enqueue_project_notification(
        db,
        project_id=project.id,
        event_id=selected_event.id,
        event_type="project_application_rejected",
        recipient_ids=rejected_ids,
        content=f"「{project.title}」已选定其他摄影师，感谢你的参与。",
    )
    record_project_event(
        db,
        project.id,
        application.id,
        None,
        "system",
        "converted",
        ProjectStatus.CONVERTED,
        f"Converted to order #{order.id}",
    )
    record_order_event(
        db,
        order.id,
        customer_id,
        "customer",
        "project_converted",
        OrderStatus.PENDING,
        f"Created from project #{project.id} and application #{application.id}",
    )

    db.commit()
    db.refresh(project)
    db.refresh(application)
    db.refresh(order)
    return project, application, order


def list_project_events(
    db: Session,
    project: ShootProject,
    current_user: User,
) -> list[ProjectEvent]:
    """列出企划的事件记录（仅项目所有者可见）。"""
    if not (current_user.is_admin or current_user.id == project.customer_id):
        raise HTTPException(status_code=403, detail="Only the project owner can view project events")
    return (
        db.query(ProjectEvent)
        .filter(ProjectEvent.project_id == project.id)
        .order_by(ProjectEvent.created_at.asc(), ProjectEvent.id.asc())
        .all()
    )
