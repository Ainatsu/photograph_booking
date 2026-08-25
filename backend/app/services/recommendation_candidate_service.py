"""推荐候选收集：为作品集挑选候选作品并标注来源。"""

from backend.app.services.recommendation_profile_service import normalize_tag

def collect_candidates(works, profile, city=None, seed_work=None):
    """根据用户画像与种子作品筛选候选，并标注候选来源。"""
    preferred, authors = set(profile.get("tag_preferences", {})), set(profile.get("author_preferences", {}))
    seed_tags = {normalize_tag(x) for x in ([seed_work.get("tag")] + (seed_work.get("tags") or [])) if x} if seed_work else set()
    result, seen = [], set()
    for work in works:
        work_id = str(work.get("id") or "")
        if not work_id or work_id in seen or not (work.get("url") or work.get("thumbnail_url")) or not work.get("user_id"): continue
        seen.add(work_id); tags = {normalize_tag(x) for x in ([work.get("tag")] + (work.get("tags") or [])) if x}
        if seed_work and work_id == str(seed_work.get("id")): continue
        source = "similar_works" if seed_tags & tags else "followed_author" if str(work["user_id"]) in authors else "content_similarity" if tags & preferred else "local_trending" if city and city == work.get("photographer_location") else "exploration" if work.get("is_new") else "trending"
        item = dict(work); item.update(candidate_source=source, normalized_tags=tags); result.append(item)
    return result
