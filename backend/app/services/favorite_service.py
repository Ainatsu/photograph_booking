"""收藏服务：作品与套餐的收藏、查询及批量状态。"""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.models.favorite import Favorite
from backend.app.models.photographer import PhotographerProfile
from backend.app.models.user import User


def _get_photographers_map(db: Session, ids: list[int]) -> dict[int, dict]:
    """根据用户 ID 列表获取摄影师信息映射"""
    if not ids:
        return {}
    profiles = (
        db.query(PhotographerProfile)
        .filter(PhotographerProfile.user_id.in_(ids))
        .all()
    )
    users = (
        db.query(User)
        .filter(User.id.in_(ids))
        .all()
    )
    user_map = {u.id: u for u in users}
    result = {}
    for pid in ids:
        user = user_map.get(pid)
        result[pid] = {
            "photographer_name": user.display_name if user else None,
            "photographer_avatar": user.avatar_url if user else None,
        }
    return result


def toggle_favorite(
    db: Session,
    user_id: int,
    work_id: str,
    photographer_id: int,
    work_data: dict | None = None,
) -> dict:
    """切换作品收藏状态，返回是否已收藏。"""
    existing = (
        db.query(Favorite)
        .filter_by(user_id=user_id, work_id=work_id, favorite_type="work")
        .first()
    )

    if existing:
        db.delete(existing)
        db.commit()
        return {"favorited": False}
    else:
        fav = Favorite(
            user_id=user_id,
            favorite_type="work",
            work_id=work_id,
            photographer_id=photographer_id,
            work_data=work_data,
        )
        db.add(fav)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            return {"favorited": False}
        return {"favorited": True}


def toggle_package_favorite(
    db: Session,
    user_id: int,
    package_id: str,
    photographer_id: int,
    package_data: dict | None = None,
) -> dict:
    """切换套餐收藏状态，返回是否已收藏。"""
    existing = (
        db.query(Favorite)
        .filter_by(user_id=user_id, package_id=package_id, favorite_type="package")
        .first()
    )

    if existing:
        db.delete(existing)
        db.commit()
        return {"favorited": False}
    else:
        fav = Favorite(
            user_id=user_id,
            favorite_type="package",
            package_id=package_id,
            photographer_id=photographer_id,
            package_data=package_data,
        )
        db.add(fav)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            return {"favorited": False}
        return {"favorited": True}


def get_user_favorites(
    db: Session,
    user_id: int,
    skip: int = 0,
    limit: int = 60,
) -> dict:
    """分页查询用户收藏的作品列表。"""
    total = (
        db.query(Favorite)
        .filter_by(user_id=user_id, favorite_type="work")
        .count()
    )

    rows = (
        db.query(Favorite)
        .filter_by(user_id=user_id, favorite_type="work")
        .order_by(Favorite.created_at.desc(), Favorite.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    photographer_ids = list({f.photographer_id for f in rows})
    photographers = _get_photographers_map(db, photographer_ids)

    items = []
    for f in rows:
        info = photographers.get(f.photographer_id, {})
        items.append({
            "work_id": f.work_id,
            "work_data": f.work_data,
            "photographer_id": f.photographer_id,
            "photographer_name": info.get("photographer_name"),
            "photographer_avatar": info.get("photographer_avatar"),
            "created_at": f.created_at,
        })

    return {"items": items, "total": total}


def get_user_package_favorites(
    db: Session,
    user_id: int,
    skip: int = 0,
    limit: int = 60,
) -> dict:
    """分页查询用户收藏的套餐列表。"""
    total = (
        db.query(Favorite)
        .filter_by(user_id=user_id, favorite_type="package")
        .count()
    )

    rows = (
        db.query(Favorite)
        .filter_by(user_id=user_id, favorite_type="package")
        .order_by(Favorite.created_at.desc(), Favorite.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    photographer_ids = list({f.photographer_id for f in rows})
    photographers = _get_photographers_map(db, photographer_ids)

    items = []
    for f in rows:
        info = photographers.get(f.photographer_id, {})
        items.append({
            "package_id": f.package_id,
            "package_data": f.package_data,
            "photographer_id": f.photographer_id,
            "photographer_name": info.get("photographer_name"),
            "photographer_avatar": info.get("photographer_avatar"),
            "created_at": f.created_at,
        })

    return {"items": items, "total": total}


def batch_favorite_status(
    db: Session,
    user_id: int,
    work_ids: list[str],
) -> dict[str, bool]:
    """批量查询作品收藏状态。"""
    if not work_ids:
        return {}

    rows = (
        db.query(Favorite.work_id)
        .filter(
            Favorite.user_id == user_id,
            Favorite.work_id.in_(work_ids),
            Favorite.favorite_type == "work",
        )
        .all()
    )

    fav_set = {r.work_id for r in rows}
    return {wid: (wid in fav_set) for wid in work_ids}


def batch_package_favorite_status(
    db: Session,
    user_id: int,
    package_ids: list[str],
) -> dict[str, bool]:
    """批量查询套餐收藏状态。"""
    if not package_ids:
        return {}

    rows = (
        db.query(Favorite.package_id)
        .filter(
            Favorite.user_id == user_id,
            Favorite.package_id.in_(package_ids),
            Favorite.favorite_type == "package",
        )
        .all()
    )

    fav_set = {r.package_id for r in rows}
    return {pid: (pid in fav_set) for pid in package_ids}
