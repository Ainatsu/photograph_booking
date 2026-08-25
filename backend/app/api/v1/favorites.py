"""
收藏相关 API 路由

提供作品与套餐的收藏/取消收藏、列表查询和状态批量查询等功能。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.api.deps import (
    get_current_active_user,
    get_current_active_user_optional,
)
from backend.app.core.database import get_db
from backend.app.models.user import User
from backend.app.schemas.favorite import (
    FavoriteToggleRequest,
    FavoriteToggleResponse,
    FavoriteListResponse,
    FavoritePackageListResponse,
)
from backend.app.services.favorite_service import (
    toggle_favorite,
    toggle_package_favorite,
    get_user_favorites,
    get_user_package_favorites,
    batch_favorite_status,
    batch_package_favorite_status,
)

router = APIRouter(prefix="/favorites", tags=["favorites"])


@router.post("/toggle", response_model=FavoriteToggleResponse, summary="Toggle work favorite")
def toggle(
    req: FavoriteToggleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """收藏或取消收藏作品/套餐"""
    if not req.work_id and not req.package_id:
        raise HTTPException(status_code=400, detail="work_id or package_id required")
    if req.work_id:
        if not req.photographer_id:
            raise HTTPException(status_code=400, detail="photographer_id required")
        return toggle_favorite(
            db, current_user.id, req.work_id.strip(),
            req.photographer_id, req.work_data,
        )
    if req.package_id:
        return toggle_package_favorite(
            db, current_user.id, req.package_id.strip(),
            req.photographer_id or 0, req.package_data,
        )


@router.get("", response_model=FavoriteListResponse, summary="Get user work favorites")
def list_favorites(
    skip: int = Query(0, ge=0),
    limit: int = Query(60, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """分页获取当前用户收藏的作品列表"""
    return get_user_favorites(db, current_user.id, skip=skip, limit=limit)


@router.get("/packages", response_model=FavoritePackageListResponse, summary="Get user package favorites")
def list_package_favorites(
    skip: int = Query(0, ge=0),
    limit: int = Query(60, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """分页获取当前用户收藏的套餐列表"""
    return get_user_package_favorites(db, current_user.id, skip=skip, limit=limit)


@router.get("/status", summary="Batch work favorite status")
def status(
    ids: str = Query(..., description="Comma-separated work ids"),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_active_user_optional),
):
    """批量查询当前用户对作品的收藏状态"""
    work_ids = [w.strip() for w in (ids or "").split(",") if w.strip()]
    if not work_ids:
        return {}
    if current_user is None:
        return {wid: False for wid in work_ids}
    return batch_favorite_status(db, current_user.id, work_ids)


@router.get("/packages/status", summary="Batch package favorite status")
def package_status(
    ids: str = Query(..., description="Comma-separated package ids"),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_active_user_optional),
):
    """批量查询当前用户对套餐的收藏状态"""
    package_ids = [p.strip() for p in (ids or "").split(",") if p.strip()]
    if not package_ids:
        return {}
    if current_user is None:
        return {pid: False for pid in package_ids}
    return batch_package_favorite_status(db, current_user.id, package_ids)
