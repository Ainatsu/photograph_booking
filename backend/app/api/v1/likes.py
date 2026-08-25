"""
点赞相关 API 路由

提供对作品与套餐的点赞/取消点赞、状态查询和热门统计等功能。
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
from backend.app.schemas.like import LikeToggleRequest, LikeToggleResponse, LikedWorkListResponse
from backend.app.services.like_service import (
    batch_like_summary,
    batch_like_count,
    batch_like_status,
    get_like_targets_for_user,
    get_liked_works_for_user,
    get_popular_like_targets,
    set_like_state,
    toggle_like,
)

router = APIRouter(prefix="/likes", tags=["likes"])
VALID_TARGET_TYPES = {"portfolio", "package"}


def _normalize_target_type(target_type: str) -> str:
    """规范化点赞目标类型，非法值返回 400"""
    normalized = (target_type or "").strip()
    if normalized not in VALID_TARGET_TYPES:
        raise HTTPException(status_code=400, detail="target_type must be 'portfolio' or 'package'")
    return normalized


def _parse_ids(ids: str) -> list[str]:
    """解析逗号分隔的目标 ID 列表"""
    id_list = [item.strip() for item in (ids or "").split(",") if item.strip()]
    if not id_list:
        raise HTTPException(status_code=400, detail="ids cannot be empty")
    return id_list


@router.post("/toggle", response_model=LikeToggleResponse, summary="Toggle like state")
def toggle(
    req: LikeToggleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """切换点赞状态（已赞则取消，未赞则点赞）"""
    target_type = _normalize_target_type(req.target_type)
    target_id = (req.target_id or "").strip()
    if not target_id:
        raise HTTPException(status_code=400, detail="target_id cannot be empty")
    return toggle_like(db, current_user.id, target_type, target_id)


@router.post("/set", response_model=LikeToggleResponse, summary="Set explicit like state")
def set_state(
    req: LikeToggleRequest,
    liked: bool = Query(..., description="Desired like state"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """显式设置点赞或取消点赞状态"""
    target_type = _normalize_target_type(req.target_type)
    target_id = (req.target_id or "").strip()
    if not target_id:
        raise HTTPException(status_code=400, detail="target_id cannot be empty")
    return set_like_state(db, current_user.id, target_type, target_id, liked)


@router.get("/status", summary="Batch current-user like status")
def status(
    target_type: str = Query(..., description="portfolio or package"),
    ids: str = Query(..., description="Comma-separated ids"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_optional),
):
    """批量查询当前用户对目标的点赞状态"""
    normalized_type = _normalize_target_type(target_type)
    id_list = _parse_ids(ids)
    if current_user is None:
        return {target_id: False for target_id in id_list}
    return batch_like_status(db, current_user.id, normalized_type, id_list)


@router.get("/count", summary="Batch like counts")
def count(
    target_type: str = Query(..., description="portfolio or package"),
    ids: str = Query(..., description="Comma-separated ids"),
    db: Session = Depends(get_db),
):
    """批量查询目标的点赞数量"""
    normalized_type = _normalize_target_type(target_type)
    id_list = _parse_ids(ids)
    return batch_like_count(db, normalized_type, id_list)


@router.get("/summary", summary="Batch like summary")
def summary(
    target_type: str = Query(..., description="portfolio or package"),
    ids: str = Query(..., description="Comma-separated ids"),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_active_user_optional),
):
    """批量获取目标的点赞数及当前用户点赞状态"""
    normalized_type = _normalize_target_type(target_type)
    id_list = _parse_ids(ids)
    user_id = current_user.id if current_user is not None else None
    return {"items": batch_like_summary(db, normalized_type, id_list, user_id=user_id)}


@router.get("/targets", summary="List liked targets for current user")
def targets(
    target_type: str = Query(..., description="portfolio or package"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """列出当前用户点赞过的目标"""
    normalized_type = _normalize_target_type(target_type)
    return {"items": get_like_targets_for_user(db, current_user.id, normalized_type)}


@router.get("/works", response_model=LikedWorkListResponse, summary="List liked works for current user")
def liked_works(
    skip: int = Query(0, ge=0),
    limit: int = Query(60, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """分页列出当前用户点赞过的作品"""
    return get_liked_works_for_user(db, current_user.id, skip=skip, limit=limit)


@router.get("/popular", summary="Popular liked targets")
def popular(
    target_type: str = Query(..., description="portfolio or package"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """获取点赞数量最高的热门目标"""
    normalized_type = _normalize_target_type(target_type)
    return {"items": get_popular_like_targets(db, normalized_type, limit=limit)}
