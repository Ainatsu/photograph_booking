"""关注服务：提供关注/取关、关注状态查询与粉丝列表等能力。"""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from backend.app.models.follow import Follow
from backend.app.models.user import User


def toggle_follow(db: Session, follower_id: int, following_id: int) -> dict:
    """切换关注状态：关注 ↔ 取消关注"""
    if follower_id == following_id:
        raise ValueError("不能关注自己")

    existing = db.query(Follow).filter_by(
        follower_id=follower_id, following_id=following_id
    ).first()

    if existing:
        db.delete(existing)
        db.commit()
        following = False
    else:
        follow = Follow(follower_id=follower_id, following_id=following_id)
        db.add(follow)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            following = False
        else:
            following = True

    return {
        "following": following,
        "follower_count": get_follower_count(db, following_id),
        "following_count": get_following_count(db, following_id),
    }


def follow_user(db: Session, follower_id: int, following_id: int) -> dict:
    """幂等关注用户：已关注时保持关注，不会切换为取消。"""
    if follower_id == following_id:
        raise ValueError("不能关注自己")

    target = db.query(User).filter(User.id == following_id).first()
    if not target:
        raise ValueError("关注目标不存在")

    existing = db.query(Follow).filter_by(
        follower_id=follower_id, following_id=following_id
    ).first()
    created = False

    if not existing:
        db.add(Follow(follower_id=follower_id, following_id=following_id))
        try:
            db.commit()
            created = True
        except IntegrityError:
            db.rollback()

    return {
        "following": True,
        "created": created,
        "follower_count": get_follower_count(db, following_id),
        "following_count": get_following_count(db, follower_id),
    }


def is_following(db: Session, follower_id: int, following_id: int) -> bool:
    """判断 follower_id 是否已关注 following_id。"""
    return db.query(Follow).filter_by(
        follower_id=follower_id, following_id=following_id
    ).first() is not None


def get_follower_count(db: Session, user_id: int) -> int:
    """获取用户的粉丝数量。"""
    return db.query(Follow).filter_by(following_id=user_id).count()


def get_following_count(db: Session, user_id: int) -> int:
    """获取用户的关注数量。"""
    return db.query(Follow).filter_by(follower_id=user_id).count()


def get_follower_list(
    db: Session, user_id: int, current_user_id: int, skip: int = 0, limit: int = 30
) -> dict:
    """获取粉丝列表（关注了 user_id 的人）"""
    follows = (
        db.query(Follow)
        .filter_by(following_id=user_id)
        .order_by(Follow.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    total = db.query(Follow).filter_by(following_id=user_id).count()

    items = []
    for f in follows:
        user = db.query(User).filter_by(id=f.follower_id).first()
        if not user:
            continue
        items.append(_build_user_item(db, user, current_user_id, f.created_at))

    return {"items": items, "total": total}


def get_following_list(
    db: Session, user_id: int, current_user_id: int, skip: int = 0, limit: int = 30
) -> dict:
    """获取关注列表（user_id 关注了的人）"""
    follows = (
        db.query(Follow)
        .filter_by(follower_id=user_id)
        .order_by(Follow.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    total = db.query(Follow).filter_by(follower_id=user_id).count()

    items = []
    for f in follows:
        user = db.query(User).filter_by(id=f.following_id).first()
        if not user:
            continue
        items.append(_build_user_item(db, user, current_user_id, f.created_at))

    return {"items": items, "total": total}


def _build_user_item(
    db: Session, user: User, current_user_id: int, followed_at
) -> dict:
    """构造列表项：用户信息及当前用户是否已关注该用户。"""
    return {
        "user_id": user.id,
        "display_name": user.display_name,
        "avatar_url": user.avatar_url,
        "bio": user.bio,
        "role": user.role,
        "is_followed": (
            is_following(db, current_user_id, user.id) if current_user_id else False
        ),
        "followed_at": followed_at.isoformat() if followed_at else None,
    }


def get_follow_counts(db: Session, user_id: int) -> dict:
    """获取用户的粉丝数与关注数。"""
    return {
        "follower_count": get_follower_count(db, user_id),
        "following_count": get_following_count(db, user_id),
    }
