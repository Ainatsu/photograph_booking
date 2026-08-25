"""评论相关 API 路由。"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_active_user
from backend.app.core.database import get_db
from backend.app.models.user import User
from backend.app.schemas.comment import CommentCreateRequest, CommentItem, CommentListResponse
from backend.app.services.comment_service import create_comment, list_comments

router = APIRouter(prefix="/comments", tags=["comments"])


@router.get("", response_model=CommentListResponse, summary="List comments")
def list_target_comments(
    target_type: str = Query(..., description="portfolio or package"),
    target_id: str = Query(..., description="Target item id"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """分页查询指定目标的评论列表。"""
    return list_comments(db, target_type, target_id, skip=skip, limit=limit)


@router.post("", response_model=CommentItem, status_code=status.HTTP_201_CREATED, summary="Create comment")
def create_target_comment(
    req: CommentCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """为指定目标创建一条评论。"""
    return create_comment(db, current_user.id, req.target_type, req.target_id, req.content)
