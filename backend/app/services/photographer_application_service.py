"""摄影师申请服务：提交、审核与查询摄影师入驻申请。"""

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from backend.app.models.photographer import PhotographerProfile
from backend.app.models.photographer_application import PhotographerApplication
from backend.app.models.user import User
from backend.app.schemas.photographer_application import PhotographerApplicationSubmit

PENDING = "pending"
APPROVED = "approved"
REJECTED = "rejected"


def serialize_application(application: PhotographerApplication) -> dict:
    """将摄影师申请模型序列化为字典。"""
    return {
        "id": application.id,
        "user_id": application.user_id,
        "user_display_name": application.user.display_name if application.user else None,
        "user_email": application.user.email if application.user else None,
        "user_avatar_url": application.user.avatar_url if application.user else None,
        "status": application.status,
        "profile_intro": application.profile_intro,
        "location": application.location,
        "equipment": application.equipment,
        "styles": application.styles or [],
        "portfolio_refs": application.portfolio_refs or [],
        "review_note": application.review_note,
        "reviewed_by": application.reviewed_by,
        "reviewed_at": application.reviewed_at,
        "created_at": application.created_at,
        "updated_at": application.updated_at,
    }


def get_application_by_user_id(db: Session, user_id: int) -> PhotographerApplication | None:
    """按用户 ID 查询申请记录。"""
    return db.query(PhotographerApplication).filter(PhotographerApplication.user_id == user_id).first()


def submit_application(
    db: Session,
    user: User,
    data: PhotographerApplicationSubmit,
) -> PhotographerApplication:
    """提交或更新摄影师入驻申请。"""
    if user.role == "photographer":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="您已经是摄影师，无需重复申请",
        )

    application = get_application_by_user_id(db, user.id)
    payload = data.model_dump()
    if application and application.status == APPROVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="申请已通过，无需重复提交",
        )

    if not payload.get("portfolio_refs"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请至少提交一个作品用于审核",
        )

    if application:
        for key, value in payload.items():
            setattr(application, key, value)
        application.status = PENDING
        application.review_note = None
        application.reviewed_by = None
        application.reviewed_at = None
    else:
        application = PhotographerApplication(
            user_id=user.id,
            status=PENDING,
            **payload,
        )
        db.add(application)

    db.commit()
    db.refresh(application)
    return application


def list_applications(
    db: Session,
    application_status: str | None = None,
    skip: int = 0,
    limit: int = 50,
) -> list[PhotographerApplication]:
    """分页查询申请列表，可按状态过滤。"""
    query = db.query(PhotographerApplication)
    if application_status:
        query = query.filter(PhotographerApplication.status == application_status)
    return query.order_by(PhotographerApplication.created_at.desc()).offset(skip).limit(limit).all()


def get_application_by_id(db: Session, application_id: int) -> PhotographerApplication | None:
    """按申请 ID 查询申请记录。"""
    return db.query(PhotographerApplication).filter(PhotographerApplication.id == application_id).first()


def _merge_portfolio(existing: list, submitted: list) -> list:
    """合并已有与提交的作品集，按 id/url 去重。"""
    merged = list(existing or [])
    seen = {
        item.get("id") or item.get("url")
        for item in merged
        if isinstance(item, dict) and (item.get("id") or item.get("url"))
    }
    for item in submitted or []:
        if not isinstance(item, dict):
            continue
        key = item.get("id") or item.get("url")
        if key and key in seen:
            continue
        merged.append(item)
        if key:
            seen.add(key)
    return merged


def approve_application(
    db: Session,
    application_id: int,
    reviewer_id: int | None = None,
    review_note: str | None = None,
) -> PhotographerApplication | None:
    """审核通过申请：创建摄影师档案并升级用户角色。"""
    application = get_application_by_id(db, application_id)
    if not application:
        return None

    user = application.user
    if not user:
        raise HTTPException(status_code=404, detail="申请用户不存在")

    profile = db.query(PhotographerProfile).filter(
        PhotographerProfile.user_id == application.user_id
    ).first()
    if not profile:
        profile = PhotographerProfile(user_id=application.user_id)
        db.add(profile)

    profile.location = application.location
    profile.equipment = application.equipment
    profile.styles = application.styles or []
    profile.portfolio = _merge_portfolio(profile.portfolio or [], application.portfolio_refs or [])
    flag_modified(profile, "portfolio")

    if application.profile_intro:
        user.bio = application.profile_intro
    user.role = "photographer"

    application.status = APPROVED
    application.review_note = review_note
    application.reviewed_by = reviewer_id
    application.reviewed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(application)
    return application


def reject_application(
    db: Session,
    application_id: int,
    reviewer_id: int | None = None,
    review_note: str | None = None,
) -> PhotographerApplication | None:
    """驳回摄影师入驻申请。"""
    application = get_application_by_id(db, application_id)
    if not application:
        return None

    application.status = REJECTED
    application.review_note = review_note or "未通过审核"
    application.reviewed_by = reviewer_id
    application.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(application)
    return application
