"""构建用户画像：根据浏览、点赞、评论等行为信号生成标签/作者/城市偏好。"""

import math
from collections import defaultdict
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from backend.app.models.analytics import AnalyticsEvent
from backend.app.models.comment import Comment
from backend.app.models.favorite import Favorite
from backend.app.models.follow import Follow
from backend.app.models.like import Like

EVENT_WEIGHTS = {"portfolio_click": (1.0, 7), "portfolio_view": (1.5, 7), "portfolio_dwell": (2.0, 7), "portfolio_like": (3.0, 30), "portfolio_comment": (4.0, 30), "portfolio_favorite": (5.0, 90), "portfolio_unlike": (-2.0, 30), "portfolio_unfavorite": (-4.0, 90), "portfolio_not_interested": (-8.0, 30)}

def normalize_tag(value: str) -> str:
    """规范化标签名称，将别名映射为统一标签。"""
    tag = "".join(str(value or "").lower().split())
    return {"日系写真": "日系", "日系人像": "日系", "人物": "人像", "婚礼跟拍": "婚礼", "复古人像": "复古"}.get(tag, tag)

def _decay(created_at, half_life: int) -> float:
    """按半衰期对事件时间做指数衰减，返回衰减权重。"""
    if not created_at: return 1.0
    now = datetime.now(timezone.utc)
    value = created_at if created_at.tzinfo else created_at.replace(tzinfo=timezone.utc)
    return math.exp(-math.log(2) * max(0, (now - value).total_seconds() / 86400) / half_life)

def build_user_profile(db: Session, user_id: int, works_by_id: dict[str, dict]) -> dict:
    """汇总用户行为信号，返回标签/作者/城市偏好画像。"""
    tags, authors, cities = defaultdict(float), defaultdict(float), defaultdict(float)
    signals = [(e.target_id, e.event_type, e.created_at) for e in db.query(AnalyticsEvent).filter(AnalyticsEvent.actor_id == user_id, AnalyticsEvent.target_type == "portfolio").all()]
    signals += [(x.target_id, "portfolio_like", x.created_at) for x in db.query(Like).filter(Like.user_id == user_id, Like.target_type == "portfolio").all()]
    signals += [(x.work_id, "portfolio_favorite", x.created_at) for x in db.query(Favorite).filter(Favorite.user_id == user_id, Favorite.favorite_type == "work").all()]
    signals += [(x.target_id, "portfolio_comment", x.created_at) for x in db.query(Comment).filter(Comment.user_id == user_id, Comment.target_type == "portfolio").all()]
    count = 0
    for work_id, event_type, created_at in signals:
        work, config = works_by_id.get(str(work_id)), EVENT_WEIGHTS.get(event_type)
        if not work or not config: continue
        count += 1; weight = config[0] * _decay(created_at, config[1])
        primary = normalize_tag(work.get("tag", ""))
        if primary: tags[primary] += weight
        for tag in work.get("tags") or []:
            if normalize_tag(tag): tags[normalize_tag(tag)] += weight * .8
        for style in work.get("photographer_styles") or []:
            if normalize_tag(style): tags[normalize_tag(style)] += weight * .5
        authors[str(work["user_id"])] += weight
        if work.get("photographer_location"): cities[work["photographer_location"]] += weight
    for follow in db.query(Follow).filter(Follow.follower_id == user_id).all(): authors[str(follow.following_id)] += 6; count += 1
    top = lambda values, limit: dict(sorted(values.items(), key=lambda x: x[1], reverse=True)[:limit])
    return {"tag_preferences": top(tags, 50), "author_preferences": top(authors, 30), "city_preferences": top(cities, 20), "event_count": count}
