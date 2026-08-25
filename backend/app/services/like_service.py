"""Like service backed directly by the database.

This implementation intentionally avoids Redis for like state so that reads and
writes always come from a single source of truth.
"""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.models.like import Like
from backend.app.models.photographer import PhotographerProfile
from backend.app.models.user import User

VALID_TARGET_TYPES = {"portfolio", "package"}


def _normalize_target(target_type: str, target_id: str) -> tuple[str, str]:
    """校验并规范化点赞目标类型与目标 ID。"""
    normalized_type = (target_type or "").strip()
    normalized_id = (target_id or "").strip()
    if normalized_type not in VALID_TARGET_TYPES:
        raise ValueError("invalid target_type")
    if not normalized_id:
        raise ValueError("target_id cannot be empty")
    return normalized_type, normalized_id


def _normalize_target_type(target_type: str) -> str:
    """校验目标类型是否合法并返回规范化结果。"""
    normalized_type = (target_type or "").strip()
    if normalized_type not in VALID_TARGET_TYPES:
        raise ValueError("invalid target_type")
    return normalized_type


def _clean_ids(target_type: str, ids: list[str]) -> list[str]:
    """规范化并去重目标 ID 列表。"""
    normalized_type = _normalize_target_type(target_type)
    result: list[str] = []
    seen: set[str] = set()
    for raw_id in ids:
        _, normalized_id = _normalize_target(normalized_type, raw_id)
        if normalized_id not in seen:
            seen.add(normalized_id)
            result.append(normalized_id)
    return result


def _db_like_exists(db: Session, user_id: int, target_type: str, target_id: str) -> bool:
    """判断用户是否已点赞指定目标。"""
    return (
        db.query(Like.id)
        .filter_by(user_id=user_id, target_type=target_type, target_id=target_id)
        .first()
        is not None
    )


def _get_count_map(db: Session, target_type: str, ids: list[str]) -> dict[str, int]:
    """批量统计各目标的点赞数。"""
    normalized_ids = _clean_ids(target_type, ids)
    if not normalized_ids:
        return {}

    rows = (
        db.query(Like.target_id, func.count(Like.id).label("count"))
        .filter(Like.target_type == target_type, Like.target_id.in_(normalized_ids))
        .group_by(Like.target_id)
        .all()
    )
    counts = {target_id: count for target_id, count in rows}
    return {target_id: int(counts.get(target_id, 0)) for target_id in normalized_ids}


def warmup_like_cache(db: Session) -> int:
    """统计不同点赞目标总数，用于缓存预热。"""
    return (
        db.query(Like.target_type, Like.target_id)
        .distinct()
        .count()
    )


def set_like_state(db: Session, user_id: int, target_type: str, target_id: str, liked: bool) -> dict:
    """设置用户对目标的点赞状态并返回最新点赞数与状态。"""
    target_type, target_id = _normalize_target(target_type, target_id)

    if liked:
        if not _db_like_exists(db, user_id, target_type, target_id):
            db.add(Like(user_id=user_id, target_type=target_type, target_id=target_id))
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
    else:
        (
            db.query(Like)
            .filter_by(user_id=user_id, target_type=target_type, target_id=target_id)
            .delete()
        )
        db.commit()

    count = get_like_count(db, target_type, target_id)
    return {"liked": liked, "count": count}


def toggle_like(db: Session, user_id: int, target_type: str, target_id: str) -> dict:
    """切换点赞状态（已赞则取消，未赞则点赞）。"""
    target_type, target_id = _normalize_target(target_type, target_id)
    liked_now = not _db_like_exists(db, user_id, target_type, target_id)
    return set_like_state(db, user_id, target_type, target_id, liked_now)


def batch_like_status(
    db: Session,
    user_id: int,
    target_type: str,
    ids: list[str],
) -> dict[str, bool]:
    """批量查询用户对各目标的点赞状态。"""
    normalized_ids = _clean_ids(target_type, ids)
    if not normalized_ids:
        return {}

    rows = (
        db.query(Like.target_id)
        .filter(
            Like.user_id == user_id,
            Like.target_type == target_type,
            Like.target_id.in_(normalized_ids),
        )
        .all()
    )
    liked_ids = {target_id for (target_id,) in rows}
    return {target_id: target_id in liked_ids for target_id in normalized_ids}


def batch_like_count(db: Session, target_type: str, ids: list[str]) -> dict[str, int]:
    """批量查询各目标的点赞数。"""
    return _get_count_map(db, target_type, ids)


def batch_like_summary(
    db: Session,
    target_type: str,
    ids: list[str],
    user_id: int | None = None,
) -> dict[str, dict[str, int | bool]]:
    """批量返回各目标的点赞数与当前用户点赞状态。"""
    normalized_ids = _clean_ids(target_type, ids)
    if not normalized_ids:
        return {}

    counts = batch_like_count(db, target_type, normalized_ids)
    statuses = batch_like_status(db, user_id, target_type, normalized_ids) if user_id is not None else {}
    return {
        target_id: {
            "count": counts.get(target_id, 0),
            "liked": statuses.get(target_id, False),
        }
        for target_id in normalized_ids
    }


def get_like_count(db: Session, target_type: str, target_id: str) -> int:
    """查询单个目标的点赞数。"""
    target_type, target_id = _normalize_target(target_type, target_id)
    count = (
        db.query(func.count(Like.id))
        .filter_by(target_type=target_type, target_id=target_id)
        .scalar()
    )
    return int(count or 0)


def is_liked(db: Session, user_id: int, target_type: str, target_id: str) -> bool:
    """查询用户是否已点赞该目标。"""
    target_type, target_id = _normalize_target(target_type, target_id)
    return _db_like_exists(db, user_id, target_type, target_id)


def sync_cache_from_db(db: Session) -> int:
    """从数据库同步点赞缓存数据。"""
    return warmup_like_cache(db)


def get_like_targets_for_user(
    db: Session,
    user_id: int,
    target_type: str,
) -> list[str]:
    """按类型返回用户点赞过的目标 ID 列表（按时间倒序）。"""
    normalized_type = _normalize_target_type(target_type)
    rows = (
        db.query(Like.target_id)
        .filter_by(user_id=user_id, target_type=normalized_type)
        .order_by(Like.created_at.desc(), Like.id.desc())
        .all()
    )
    return [target_id for (target_id,) in rows]


def get_liked_works_for_user(
    db: Session,
    user_id: int,
    skip: int = 0,
    limit: int = 60,
) -> dict:
    """分页返回用户点赞过的作品及其摄影师信息。"""
    total = (
        db.query(Like)
        .filter_by(user_id=user_id, target_type="portfolio")
        .count()
    )

    rows = (
        db.query(Like)
        .filter_by(user_id=user_id, target_type="portfolio")
        .order_by(Like.created_at.desc(), Like.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    liked_ids = [row.target_id for row in rows]
    if not liked_ids:
        return {"items": [], "total": total}

    liked_id_set = set(liked_ids)
    profiles = db.query(PhotographerProfile).all()
    users = db.query(User).all()
    user_map = {user.id: user for user in users}
    works_by_id: dict[str, dict] = {}

    for profile in profiles:
        user = user_map.get(profile.user_id)
        for work in (profile.portfolio or []):
            if not isinstance(work, dict):
                continue
            work_id = str(work.get("id") or "").strip()
            if work_id not in liked_id_set:
                continue

            work_data = {
                "id": work_id,
                "url": work.get("url", ""),
                "images": work.get("images") or ([work.get("url", "")] if work.get("url") else []),
                "thumbnail_url": work.get("thumbnail_url") or work.get("url", ""),
                "thumbnail_urls": work.get("thumbnail_urls") or [],
                "media_type": work.get("media_type") or "image",
                "tag": work.get("tag", ""),
                "tags": work.get("tags") or [],
                "title": work.get("title", ""),
                "description": work.get("description", ""),
                "user_id": profile.user_id,
                "user_display_name": user.display_name if user else None,
                "user_avatar_url": user.avatar_url if user else None,
            }
            works_by_id[work_id] = {
                "work_id": work_id,
                "work_data": work_data,
                "photographer_id": profile.user_id,
                "photographer_name": user.display_name if user else None,
                "photographer_avatar": user.avatar_url if user else None,
            }

    items = []
    for row in rows:
        item = works_by_id.get(row.target_id)
        if item:
            items.append({**item, "liked_at": row.created_at})

    return {"items": items, "total": total}


def get_popular_like_targets(
    db: Session,
    target_type: str,
    limit: int = 20,
) -> list[dict[str, int | str]]:
    """按点赞数降序返回热门点赞目标。"""
    normalized_type = _normalize_target_type(target_type)
    rows = (
        db.query(
            Like.target_id,
            func.count(Like.id).label("count"),
        )
        .filter_by(target_type=normalized_type)
        .group_by(Like.target_id)
        .order_by(func.count(Like.id).desc(), Like.target_id.asc())
        .limit(limit)
        .all()
    )
    return [{"target_id": target_id, "count": int(count)} for target_id, count in rows]
