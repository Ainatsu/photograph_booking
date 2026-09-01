"""管理后台服务：用户、订单与平台运行数据的管理操作。"""

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.app.models.user import User
from backend.app.models.order import Order
from backend.app.models.image_generation import ImageGenerationAsset, ImageGenerationJob
from backend.app.services.order_service import admin_cancel_order_transition


def get_dashboard_stats(db: Session) -> dict:
    """仪表盘统计数据"""
    total_users = db.query(func.count(User.id)).scalar() or 0
    total_photographers = db.query(func.count(User.id)).filter(User.role == "photographer").scalar() or 0
    total_customers = db.query(func.count(User.id)).filter(User.role == "customer").scalar() or 0
    total_orders = db.query(func.count(Order.id)).scalar() or 0
    pending_orders = db.query(func.count(Order.id)).filter(Order.status == "pending").scalar() or 0
    today_orders = db.query(func.count(Order.id)).filter(
        func.date(Order.created_at) == func.date(func.now())
    ).scalar() or 0

    return {
        "total_users": total_users,
        "total_photographers": total_photographers,
        "total_customers": total_customers,
        "total_orders": total_orders,
        "pending_orders": pending_orders,
        "today_orders": today_orders,
    }


def get_image_generation_overview(db: Session, *, days: int = 7, recent_limit: int = 20) -> dict:
    """Return a compact operational overview without exposing prompts or media."""
    since = datetime.now(timezone.utc) - timedelta(days=max(1, min(days, 90)))
    jobs = (
        db.query(ImageGenerationJob)
        .filter(ImageGenerationJob.created_at >= since)
        .order_by(ImageGenerationJob.created_at.desc(), ImageGenerationJob.id.desc())
        .all()
    )
    status_counts: dict[str, int] = {}
    mode_counts: dict[str, int] = {}
    provider_counts: dict[str, int] = {}
    latency_values: list[int] = []
    regenerated = 0
    for job in jobs:
        status_counts[job.status] = status_counts.get(job.status, 0) + 1
        mode_counts[job.mode] = mode_counts.get(job.mode, 0) + 1
        provider = job.provider or "pending"
        provider_counts[provider] = provider_counts.get(provider, 0) + 1
        parameters = job.parameters or {}
        if parameters.get("regenerated_from_job_id"):
            regenerated += 1
        audit = (job.usage_metadata or {}).get("audit") or {}
        latency = audit.get("total_latency_ms")
        if isinstance(latency, (int, float)) and latency >= 0:
            latency_values.append(round(latency))

    successful = status_counts.get("completed", 0) + status_counts.get("partial", 0)
    terminal = successful + status_counts.get("failed", 0) + status_counts.get("cancelled", 0)
    job_ids = [job.id for job in jobs]
    generated_assets = 0
    if job_ids:
        generated_assets = (
            db.query(func.count(ImageGenerationAsset.id))
            .filter(ImageGenerationAsset.job_id.in_(job_ids), ImageGenerationAsset.role == "result")
            .scalar()
            or 0
        )

    recent = []
    for job in jobs[:max(1, min(recent_limit, 50))]:
        audit = (job.usage_metadata or {}).get("audit") or {}
        recent.append({
            "job_id": job.id,
            "owner_id": job.owner_id,
            "mode": job.mode,
            "status": job.status,
            "provider": job.provider,
            "model": job.model,
            "attempts": job.attempts,
            "requested_count": int((job.parameters or {}).get("count", 1)),
            "saved_count": int(audit.get("saved_count", 0)),
            "latency_ms": audit.get("total_latency_ms"),
            "error_code": job.last_error_code,
            "is_regenerated": bool((job.parameters or {}).get("regenerated_from_job_id")),
            "created_at": job.created_at,
        })

    return {
        "period_days": max(1, min(days, 90)),
        "total_jobs": len(jobs),
        "generated_assets": generated_assets,
        "successful_jobs": successful,
        "success_rate": round(successful / terminal * 100, 1) if terminal else 0.0,
        "average_latency_ms": round(sum(latency_values) / len(latency_values)) if latency_values else None,
        "regenerated_jobs": regenerated,
        "status_counts": status_counts,
        "mode_counts": mode_counts,
        "provider_counts": provider_counts,
        "recent_jobs": recent,
    }


def get_all_users(db: Session, skip: int = 0, limit: int = 50) -> list[User]:
    """分页查询全部用户。"""
    return db.query(User).offset(skip).limit(limit).all()


def ban_user(db: Session, user_id: int) -> User | None:
    """封禁指定用户。"""
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        user.is_banned = True
        db.commit()
        db.refresh(user)
    return user


def unban_user(db: Session, user_id: int) -> User | None:
    """解除对指定用户的封禁。"""
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        user.is_banned = False
        db.commit()
        db.refresh(user)
    return user


def get_all_orders(db: Session, skip: int = 0, limit: int = 50) -> list[Order]:
    """按创建时间倒序分页查询全部订单。"""
    return db.query(Order).order_by(Order.created_at.desc()).offset(skip).limit(limit).all()


def admin_cancel_order(db: Session, order_id: int, admin_id: int, reason: str) -> Order | None:
    """管理员取消指定订单并记录原因。"""
    order = db.query(Order).filter(Order.id == order_id).first()
    if order:
        return admin_cancel_order_transition(db, order, admin_id, reason)
    return order
