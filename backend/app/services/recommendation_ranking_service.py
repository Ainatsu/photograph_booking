"""推荐候选排序与多样性打散服务。"""

import math
from collections import Counter
from datetime import datetime, timezone

def rank_candidates(candidates, profile, city=None):
    """结合画像偏好与新鲜度等因素计算候选的 rank_score 并排序。"""
    tags, authors = profile.get("tag_preferences", {}), profile.get("author_preferences", {})
    max_tag, max_author = max([abs(v) for v in tags.values()] or [1]), max([abs(v) for v in authors.values()] or [1])
    now = datetime.now(timezone.utc)
    for item in candidates:
        content = min(1, sum(max(0, tags.get(tag, 0)) for tag in item["normalized_tags"]) / max_tag)
        author = min(1, max(0, authors.get(str(item["user_id"]), 0)) / max_author)
        created = item.get("created_at")
        if created: created = created if created.tzinfo else created.replace(tzinfo=timezone.utc)
        fresh = math.exp(-max(0, (now-created).total_seconds())/(86400*30)) if created else .35
        explore = 1 if item.get("is_new") or item.get("impression_count", 0) < 10 else 0
        item["rank_score"] = .33*content + .14*author + .18*item.get("quality_score", 0) + .17*item.get("trend_score", 0) + .08*fresh + .05*bool(city and city == item.get("photographer_location")) + .10*explore
    return sorted(candidates, key=lambda x: (x["rank_score"], str(x["id"])), reverse=True)

def diversify(ranked):
    """对排序结果做多样性打散，控制同一作者的重复出现。"""
    ranked, selected, counts = list(ranked), [], Counter()
    while ranked:
        best_i, best = 0, -999
        recent_tags = set().union(*(x["normalized_tags"] for x in selected[-6:])) if selected else set()
        for i, item in enumerate(ranked[:80]):
            if len(selected) < 10 and counts[item["user_id"]] >= 2: continue
            overlap = len(item["normalized_tags"] & recent_tags) / max(1, len(item["normalized_tags"] | recent_tags))
            score = item["rank_score"] - .20*min(counts[item["user_id"]], 1) - .12*overlap + .08*bool(item["normalized_tags"]-recent_tags)
            if score > best: best_i, best = i, score
        item = ranked.pop(best_i); selected.append(item); counts[item["user_id"]] += 1
    return selected
