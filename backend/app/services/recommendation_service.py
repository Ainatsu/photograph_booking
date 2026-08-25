"""作品推荐服务：加载作品、同步统计并基于混合策略排序返回推荐结果。"""

import base64, json, math, uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from backend.app.core.cache import cache_get, cache_set
from backend.app.models.analytics import AnalyticsEvent
from backend.app.models.comment import Comment
from backend.app.models.favorite import Favorite
from backend.app.models.like import Like
from backend.app.models.photographer import PhotographerProfile
from backend.app.models.recommendation import RecommendationItemStats
from backend.app.models.user import User
from backend.app.services.photographer_service import _fix_missing_ids, _split_tags, _tag_id, _work_images, _work_thumbnail_urls
from backend.app.services.recommendation_candidate_service import collect_candidates
from backend.app.services.recommendation_profile_service import build_user_profile
from backend.app.services.recommendation_ranking_service import diversify, rank_candidates

ALGORITHM_VERSION = "work_hybrid_v1"

def _encode_cursor(offset):
    """将分页偏移量编码为游标字符串。"""
    return base64.urlsafe_b64encode(json.dumps({"offset": offset}).encode()).decode().rstrip("=")


def _decode_cursor(value):
    """解码游标字符串得到分页偏移量，失败时返回 0。"""
    try: return max(0, int(json.loads(base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)))["offset"])) if value else 0
    except Exception: return 0

def _load_works(db):
    """加载所有活跃摄影师的作品列表。"""
    _fix_missing_ids(db); works = []
    for p in db.query(PhotographerProfile).join(User).filter(User.is_active.is_(True), User.is_banned.is_(False)).all():
        for raw in p.portfolio or []:
            media = raw.get("media_type") or "image"; images = _work_images(raw); thumbs = _work_thumbnail_urls(raw, media)
            works.append({"id": _tag_id(raw), "url": raw.get("url", "") or (images[0] if images else ""), "images": images, "media_type": media, "thumbnail_url": raw.get("thumbnail_url") or (thumbs[0] if thumbs else ""), "thumbnail_urls": thumbs, "compressed_url": raw.get("compressed_url", ""), "duration": raw.get("duration"), "compressed_duration": raw.get("compressed_duration"), "tag": raw.get("tag", ""), "tags": raw.get("tags") or _split_tags(raw.get("tag", "")), "title": raw.get("title", ""), "description": raw.get("description", ""), "user_id": p.user_id, "user_display_name": p.user.display_name, "user_avatar_url": p.user.avatar_url, "photographer_location": p.location, "photographer_styles": p.styles or [], "created_at": p.created_at})
    return works

def _sync_stats(db, works):
    """同步作品的点赞、收藏、评论与热度统计，并更新质量分与趋势分。"""
    likes, favorites, comments, events = defaultdict(int), defaultdict(int), defaultdict(int), defaultdict(list)
    for x in db.query(Like).filter(Like.target_type == "portfolio").all(): likes[str(x.target_id)] += 1
    for x in db.query(Favorite).filter(Favorite.favorite_type == "work").all(): favorites[str(x.work_id)] += 1
    for x in db.query(Comment).filter(Comment.target_type == "portfolio").all(): comments[str(x.target_id)] += 1
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    for x in db.query(AnalyticsEvent).filter(AnalyticsEvent.target_type == "portfolio", AnalyticsEvent.created_at >= cutoff).all(): events[str(x.target_id)].append(x)
    global_rate = (sum(likes.values()) + sum(favorites.values()) + sum(comments.values())) / max(1, sum(x.event_type == "portfolio_impression" for values in events.values() for x in values)); now = datetime.now(timezone.utc)
    for work in works:
        item = db.query(RecommendationItemStats).filter_by(target_type="portfolio", target_id=str(work["id"])).first()
        if not item: item = RecommendationItemStats(target_type="portfolio", target_id=str(work["id"]), owner_user_id=work["user_id"]); db.add(item)
        item.like_count, item.favorite_count, item.comment_count = likes[str(work["id"])], favorites[str(work["id"])], comments[str(work["id"])]
        item.impression_count = max(item.impression_count or 0, sum(x.event_type == "portfolio_impression" for x in events[str(work["id"])]))
        positive = item.like_count + 2*item.favorite_count + item.comment_count; item.smoothed_ctr = (positive + global_rate*50)/(item.impression_count+50)
        completeness = sum(bool(work.get(k)) for k in ("title", "description", "tag", "thumbnail_url"))/4; item.quality_score = min(1, .55*item.smoothed_ctr + .45*completeness)
        trend_raw = sum({"portfolio_click":1,"portfolio_view":1.5,"portfolio_like":3,"portfolio_favorite":5,"portfolio_comment":4}.get(x.event_type,0)*math.exp(-max(0,(now-(x.created_at if x.created_at.tzinfo else x.created_at.replace(tzinfo=timezone.utc))).total_seconds())/(72*3600)) for x in events[str(work["id"])]); item.trend_score = 1-math.exp(-math.log1p(trend_raw)/3)
        created = work.get("created_at"); aware = created if created and created.tzinfo else created.replace(tzinfo=timezone.utc) if created else None
        work.update(impression_count=item.impression_count, quality_score=item.quality_score, trend_score=item.trend_score, is_new=bool(aware and now-aware < timedelta(days=2)))
    db.commit()

def recommend_works(db: Session, viewer_user_id, scene, cursor, limit, city, seed_work_id, session_id):
    """按场景混合召回并排序作品，返回带缓存的分页推荐结果。"""
    offset = _decode_cursor(cursor); identity = str(viewer_user_id or session_id or "anonymous")
    key = f"rec:works:{ALGORITHM_VERSION}:{identity}:{scene}:{city or '-'}:{seed_work_id or '-'}:{offset}:{limit}"
    cached = cache_get(key)
    if cached is not None: return cached
    works = _load_works(db); _sync_stats(db, works); by_id = {str(x["id"]):x for x in works}
    profile = build_user_profile(db, viewer_user_id, by_id) if viewer_user_id else {"tag_preferences":{},"author_preferences":{},"city_preferences":{},"event_count":0}
    ranked = diversify(rank_candidates(collect_candidates(works, profile, city, by_id.get(str(seed_work_id)) if seed_work_id else None), profile, city)); page = ranked[offset:offset+limit]
    reasons = {"similar_works":"与当前作品风格相似","followed_author":"你关注的摄影师作品","content_similarity":"与你喜欢的作品风格相似","local_trending":f"{city}地区近期热门","exploration":"为你探索的新锐摄影师作品","trending":"平台近期热门作品"}
    items=[]
    for item in page:
        public={k:item.get(k) for k in ("id","title","tags","url","images","media_type","thumbnail_url","thumbnail_urls","compressed_url","duration","compressed_duration","tag","description","user_id","user_display_name","user_avatar_url")}; public.update(photographer_id=item["user_id"], candidate_source=item["candidate_source"], recommendation_reason=reasons[item["candidate_source"]]); items.append(public)
    result={"recommendation_id":str(uuid.uuid4()),"algorithm_version":ALGORITHM_VERSION,"next_cursor":_encode_cursor(offset+limit) if offset+limit<len(ranked) else None,"items":items}; cache_set(key,result,300); return result
