"""评论服务：校验评论目标并实现评论的查询与创建。"""

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from backend.app.models.comment import Comment
from backend.app.services.photographer_service import get_package_by_id, get_work_by_id


VALID_TARGET_TYPES = {"portfolio", "package"}
MAX_COMMENT_LENGTH = 500


def normalize_comment_target(target_type: str, target_id: str) -> tuple[str, str]:
    """规范化并校验评论目标类型与目标 ID。"""
    normalized_type = (target_type or "").strip()
    normalized_id = (target_id or "").strip()

    if normalized_type not in VALID_TARGET_TYPES:
        raise HTTPException(status_code=400, detail="target_type must be 'portfolio' or 'package'")
    if not normalized_id:
        raise HTTPException(status_code=400, detail="target_id cannot be empty")

    return normalized_type, normalized_id


def _serialize_comment(comment: Comment) -> dict:
    """将评论对象序列化为响应字典。"""
    user = comment.user
    return {
        "id": comment.id,
        "user_id": comment.user_id,
        "user_display_name": user.display_name if user else None,
        "user_avatar_url": user.avatar_url if user else None,
        "target_type": comment.target_type,
        "target_id": comment.target_id,
        "content": comment.content,
        "created_at": comment.created_at,
    }


def _target_exists(db: Session, target_type: str, target_id: str) -> bool:
    """判断评论目标（作品或套餐）是否存在。"""
    if target_type == "portfolio":
        return get_work_by_id(db, target_id) is not None
    return get_package_by_id(db, target_id) is not None


def list_comments(
    db: Session,
    target_type: str,
    target_id: str,
    skip: int = 0,
    limit: int = 20,
) -> dict:
    """分页查询指定目标的评论列表。"""
    normalized_type, normalized_id = normalize_comment_target(target_type, target_id)

    query = (
        db.query(Comment)
        .options(joinedload(Comment.user))
        .filter(
            Comment.target_type == normalized_type,
            Comment.target_id == normalized_id,
        )
    )
    total = query.count()
    rows = (
        query.order_by(Comment.created_at.desc(), Comment.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return {
        "items": [_serialize_comment(comment) for comment in rows],
        "total": total,
    }


def create_comment(
    db: Session,
    user_id: int,
    target_type: str,
    target_id: str,
    content: str,
) -> dict:
    """创建评论：校验内容与目标后写入并返回序列化结果。"""
    normalized_type, normalized_id = normalize_comment_target(target_type, target_id)
    normalized_content = (content or "").strip()

    if not normalized_content:
        raise HTTPException(status_code=400, detail="content cannot be empty")
    if len(normalized_content) > MAX_COMMENT_LENGTH:
        raise HTTPException(status_code=400, detail=f"content cannot exceed {MAX_COMMENT_LENGTH} characters")
    if not _target_exists(db, normalized_type, normalized_id):
        raise HTTPException(status_code=404, detail="target does not exist")

    comment = Comment(
        user_id=user_id,
        target_type=normalized_type,
        target_id=normalized_id,
        content=normalized_content,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)

    hydrated = (
        db.query(Comment)
        .options(joinedload(Comment.user))
        .filter(Comment.id == comment.id)
        .one()
    )
    return _serialize_comment(hydrated)
