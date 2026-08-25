"""
关注系统 API 路由

提供用户关注/取消关注、关注状态查询以及粉丝/关注列表等功能。
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from backend.app.api.deps import (
    get_current_active_user,
    get_current_active_user_optional,
)
from backend.app.core.database import get_db
from backend.app.models.user import User
from backend.app.services import follow_service

router = APIRouter(prefix="/follows", tags=["关注系统"])


@router.post("/toggle/{user_id}", summary="关注/取消关注用户")
def toggle(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """关注或取消关注指定用户"""
    try:
        return follow_service.toggle_follow(db, current_user.id, user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/status/{user_id}", summary="查询是否关注了某用户")
def status(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_optional),
):
    """查询当前用户是否关注了指定用户"""
    if current_user is None:
        return {"following": False}
    return {
        "following": follow_service.is_following(db, current_user.id, user_id)
    }


@router.get("/counts/{user_id}", summary="获取用户的关注数和粉丝数")
def counts(user_id: int, db: Session = Depends(get_db)):
    """获取指定用户的关注数和粉丝数"""
    return follow_service.get_follow_counts(db, user_id)


@router.get("/followers/{user_id}", summary="获取用户的粉丝列表")
def followers(
    user_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_optional),
):
    """分页获取指定用户的粉丝列表"""
    uid = current_user.id if current_user else 0
    return follow_service.get_follower_list(db, user_id, uid, skip, limit)


@router.get("/following/{user_id}", summary="获取用户的关注列表")
def following(
    user_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_optional),
):
    """分页获取指定用户的关注列表"""
    uid = current_user.id if current_user else 0
    return follow_service.get_following_list(db, user_id, uid, skip, limit)