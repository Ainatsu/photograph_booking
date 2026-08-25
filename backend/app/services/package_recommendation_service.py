"""套餐推荐：加载套餐、统计热度并按多因子加权排序。"""

import math
import uuid
import logging
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from time import perf_counter

from sqlalchemy.orm import Session

from backend.app.core.cache import cache_get, cache_set
from backend.app.models.analytics import AnalyticsEvent
from backend.app.models.favorite import Favorite
from backend.app.models.photographer import PhotographerProfile
from backend.app.models.recommendation import RecommendationItemStats
from backend.app.models.user import User
from backend.app.schemas.recommendation import PackageRecommendationQuery
from backend.app.services.availability_service import batch_list_bookable_slots, get_day_availability
from backend.app.services.location_service import distance_label, haversine_km, package_coordinates, validate_coordinates
from backend.app.services.joint_recommendation_gate import is_joint_recommendation_enabled
from backend.app.services.photographer_service import _fix_missing_ids, _package_styles, _tag_id
from backend.app.services.recommendation_profile_service import build_user_profile, normalize_tag
from backend.app.services.recommendation_service import _decode_cursor, _encode_cursor, _load_works

PACKAGE_ALGORITHM_VERSION = "package_rec_v2_joint_availability"
LEGACY_PACKAGE_ALGORITHM_VERSION = "package_hybrid_v1"
JOINT_WEIGHTS = {
    "style_score": .30,
    "budget_score": .20,
    "availability_score": .18,
    "distance_score": .12,
    "quality_score": .08,
    "affinity_score": .07,
    "freshness_score": .03,
    "exploration_score": .02,
}
logger = logging.getLogger(__name__)


def invalidate_package_recommendation_cache(photographer_id: int | None = None) -> None:
    """Invalidate recommendation snapshots after profile/schedule/order changes."""
    from backend.app.core.cache import cache_delete_pattern

    cache_delete_pattern("rec:packages:*")


def _load_packages(db: Session) -> list[dict]:
    """加载全部在架摄影师的可用套餐并规范化字段。"""
    _fix_missing_ids(db)
    packages = []
    profiles = db.query(PhotographerProfile).join(User).filter(User.is_active.is_(True), User.is_banned.is_(False), User.role == "photographer").all()
    for profile in profiles:
        for raw in profile.packages or []:
            if not isinstance(raw, dict) or raw.get("is_active", True) is False:
                continue
            name = str(raw.get("name") or "").strip()
            try:
                price = float(raw.get("price") or 0)
                duration = int(raw.get("duration") or 0)
            except (TypeError, ValueError):
                price, duration = 0, 0
            if not name or price <= 0 or duration <= 0:
                continue
            styles = _package_styles(raw)
            packages.append({
                "id": _tag_id(raw), "package_name": name, "price": price,
                "duration": duration, "image_count": int(raw.get("image_count") or 0),
                "description": raw.get("description", ""), "includes": raw.get("includes") or [],
                "styles": styles, "normalized_styles": {normalize_tag(x) for x in styles if x},
                "city": raw.get("service_city") or raw.get("city") or profile.service_city or profile.location or "", "samples": raw.get("samples") or [],
                "sample_thumbnails": raw.get("sample_thumbnails") or [], "photographer_id": profile.user_id,
                "photographer_name": profile.user.display_name, "photographer_avatar": profile.user.avatar_url,
                "photographer_location": profile.location, "profile": profile, "created_at": profile.created_at,
                "raw_package": raw,
            })
    return packages


def _sync_package_stats(db: Session, packages: list[dict]) -> None:
    """同步套餐的收藏、点击等统计并更新质量分与趋势分。"""
    favorites, events = defaultdict(int), defaultdict(list)
    for item in db.query(Favorite).filter(Favorite.favorite_type == "package").all():
        favorites[str(item.package_id)] += 1
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    for event in db.query(AnalyticsEvent).filter(AnalyticsEvent.target_type == "package", AnalyticsEvent.created_at >= cutoff).all():
        events[str(event.target_id)].append(event)
    total_impressions = sum(e.event_type == "package_impression" for values in events.values() for e in values)
    total_positive = sum(favorites.values()) + sum(e.event_type in {"package_view", "package_booking_intent"} for values in events.values() for e in values)
    global_rate = total_positive / max(1, total_impressions)
    now = datetime.now(timezone.utc)
    package_ids = [str(package["id"]) for package in packages]
    stats_by_id = {
        str(stats.target_id): stats
        for stats in db.query(RecommendationItemStats).filter(
            RecommendationItemStats.target_type == "package",
            RecommendationItemStats.target_id.in_(package_ids),
        ).all()
    } if package_ids else {}
    new_stats: list[RecommendationItemStats] = []
    for package in packages:
        stats = stats_by_id.get(str(package["id"]))
        if not stats:
            stats = RecommendationItemStats(target_type="package", target_id=str(package["id"]), owner_user_id=package["photographer_id"])
            new_stats.append(stats)
        recent = events[str(package["id"])]
        stats.impression_count = max(stats.impression_count or 0, sum(e.event_type == "package_impression" for e in recent))
        stats.favorite_count = favorites[str(package["id"])]
        stats.click_count = max(stats.click_count or 0, sum(e.event_type in {"package_click", "package_view"} for e in recent))
        stats.booking_intent_count = max(stats.booking_intent_count or 0, sum(e.event_type == "package_booking_intent" for e in recent))
        positive = stats.favorite_count + stats.click_count + 3 * stats.booking_intent_count
        stats.smoothed_ctr = (positive + global_rate * 50) / (stats.impression_count + 50)
        completeness = sum(bool(package.get(key)) for key in ("package_name", "description", "styles", "samples")) / 4
        stats.quality_score = min(1.0, .6 * stats.smoothed_ctr + .4 * completeness)
        trend = sum({"package_click": 1, "package_view": 1.5, "package_favorite": 3, "package_booking_intent": 8}.get(e.event_type, 0) * math.exp(-max(0, (now - (e.created_at if e.created_at.tzinfo else e.created_at.replace(tzinfo=timezone.utc))).total_seconds()) / (120 * 3600)) for e in recent)
        stats.trend_score = 1 - math.exp(-math.log1p(trend) / 3)
        package.update(impression_count=stats.impression_count, conversion_quality=stats.quality_score, trend_score=stats.trend_score)
    if new_stats:
        db.bulk_save_objects(new_stats)
    db.commit()


def _budget_fit(price: float, budget_min: float | None, budget_max: float | None) -> float:
    """计算价格相对预算区间的匹配度得分。"""
    if budget_min is None and budget_max is None:
        return .5
    low = budget_min if budget_min is not None else 0
    high = budget_max if budget_max is not None else max(price, low)
    if low <= price <= high:
        center = (low + high) / 2
        return 1 - .25 * abs(price - center) / max(1, (high - low) / 2)
    distance = low - price if price < low else price - high
    return max(0, 1 - distance / max(price, high, 1))


def _time_minutes(value: str | None) -> int | None:
    """将 HH:MM 字符串转为当天分钟数，非法时抛错。"""
    if not value:
        return None
    try:
        hour, minute = (int(part) for part in value.split(":"))
    except (TypeError, ValueError):
        raise ValueError("时间必须使用 HH:MM 格式")
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValueError("时间必须使用 HH:MM 格式")
    return hour * 60 + minute


def _distance_score(distance: float | None) -> float | None:
    """将距离（公里）映射为分段距离得分。"""
    if distance is None:
        return None
    if distance <= 3:
        return 1.0
    if distance <= 10:
        return 1 - (distance - 3) / 7 * .2
    if distance <= 20:
        return .8 - (distance - 10) / 10 * .3
    if distance <= 40:
        return .5 - (distance - 20) / 20 * .4
    return 0.0


def _weighted_score(features: dict[str, float | None]) -> float:
    """按联合权重对各特征得分加权平均。"""
    active = [(JOINT_WEIGHTS[key], value) for key, value in features.items() if value is not None]
    denominator = sum(weight for weight, _ in active)
    return sum(weight * float(value) for weight, value in active) / denominator if denominator else 0.0


def _diversify_candidates(candidates: list[dict], first_screen_size: int = 6, per_photographer: int = 2) -> list[dict]:
    """首屏限制每位摄影师数量，其余候选顺延至末尾。"""
    selected, deferred, counts = [], [], defaultdict(int)
    for candidate in candidates:
        photographer_id = candidate["photographer_id"]
        if len(selected) < first_screen_size and counts[photographer_id] >= per_photographer:
            deferred.append(candidate)
            continue
        selected.append(candidate)
        if len(selected) <= first_screen_size:
            counts[photographer_id] += 1
    return selected + deferred


def _matching_availability(snapshot: dict | None, query: PackageRecommendationQuery) -> dict | None:
    """从可约快照中筛出匹配查询时间窗的时段。"""
    if not query.shoot_date:
        return None
    if not snapshot:
        return None
    slots = (snapshot.get("days") or [{}])[0].get("slots") or []
    start_limit, end_limit = _time_minutes(query.time_start), _time_minutes(query.time_end)
    if start_limit is not None and end_limit is not None:
        slots = [
            slot for slot in slots
            if datetime.fromisoformat(slot["start_at"]).hour * 60 + datetime.fromisoformat(slot["start_at"]).minute >= start_limit
            and datetime.fromisoformat(slot["end_at"]).hour * 60 + datetime.fromisoformat(slot["end_at"]).minute <= end_limit
        ]
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=90)
    return {
        "date": query.shoot_date.isoformat(),
        "timezone": snapshot["timezone"],
        "matching_slots": slots[:6],
        "snapshot_expires_at": expires_at.isoformat(),
    }


def _next_distance_tier(value: float | None) -> float | None:
    """返回下一个更大的距离档位，用于逐级放宽。"""
    if value is None:
        return None
    for tier in (5.0, 10.0, 20.0, 30.0, 50.0, 100.0):
        if tier > value:
            return tier
    return value * 1.5


def _rank_package_candidates(
    db: Session,
    packages: list[dict],
    profile: dict,
    query: PackageRecommendationQuery,
    *,
    enforce_style: bool,
    budget_overage_ratio: float = 1.0,
    metrics: dict | None = None,
) -> list[dict]:
    """按查询条件过滤并多因子排序套餐候选，返回去重后列表。"""
    requested_styles = {normalize_tag(x) for x in query.styles if x}
    preferred_styles = set(profile.get("tag_preferences", {}))
    author_preferences = profile.get("author_preferences", {})
    max_author = max([abs(x) for x in author_preferences.values()] or [1])
    now = datetime.now(timezone.utc)
    candidates = []
    query_coordinates = validate_coordinates(query.latitude, query.longitude)
    coarse_candidates = []
    after_city = after_budget = 0
    for package in packages:
        if query.city and not any(query.city in str(value or "") for value in (package["city"], package["photographer_location"], package["profile"].service_city)):
            continue
        after_city += 1
        if enforce_style and requested_styles and not package["normalized_styles"] & requested_styles:
            continue
        if query.budget_min is not None and package["price"] < query.budget_min * .6:
            continue
        if query.budget_max is not None and package["price"] > query.budget_max * budget_overage_ratio:
            continue
        after_budget += 1
        if query.shoot_date and get_day_availability(package["profile"], query.shoot_date).get("status") == "busy":
            continue
        coarse_candidates.append(package)
    availability_started = perf_counter()
    availability_by_package = batch_list_bookable_slots(db, [
        {"key": str(package["id"]), "profile": package["profile"], "start_date": query.shoot_date, "days": 1, "duration_minutes": query.duration_minutes or package["duration"]}
        for package in coarse_candidates
    ]) if query.shoot_date else {}
    availability_query_ms = round((perf_counter() - availability_started) * 1000, 3)
    after_availability = after_distance = 0
    for package in coarse_candidates:
        availability = _matching_availability(availability_by_package.get(str(package["id"])), query) if query.shoot_date else None
        if query.require_exact_availability and (not availability or not availability["matching_slots"]):
            continue
        after_availability += 1
        style_target = requested_styles or preferred_styles
        style_match = len(package["normalized_styles"] & style_target) / max(1, len(style_target))
        style_score = style_match if requested_styles else max(.35, style_match)
        budget_fit = _budget_fit(package["price"], query.budget_min, query.budget_max)
        affinity = max(0, author_preferences.get(str(package["photographer_id"]), 0)) / max_author
        created = package.get("created_at")
        aware = created if created and created.tzinfo else created.replace(tzinfo=timezone.utc) if created else None
        freshness = math.exp(-max(0, (now - aware).total_seconds()) / (86400 * 60)) if aware else .3
        exploration = 1 if package["impression_count"] < 10 else 0
        service_coordinates = package_coordinates(package["raw_package"], package["profile"])
        distance = haversine_km(*query_coordinates, *service_coordinates) if query_coordinates and service_coordinates else None
        radius_values = [value for value in (package["raw_package"].get("service_radius_km"), package["profile"].service_radius_km, query.max_distance_km) if value is not None]
        if distance is not None and radius_values and distance > min(float(value) for value in radius_values):
            continue
        after_distance += 1
        availability_score = min(1.0, .85 + .05 * len(availability["matching_slots"])) if availability and availability["matching_slots"] else None
        features = {
            "style_score": style_score,
            "budget_score": budget_fit,
            "availability_score": availability_score,
            "distance_score": _distance_score(distance),
            "quality_score": package["conversion_quality"],
            "affinity_score": affinity,
            "freshness_score": freshness,
            "exploration_score": exploration,
        }
        candidate = dict(package)
        candidate.update(rank_score=_weighted_score(features), match=features, availability=availability, distance_km=distance)
        candidate["candidate_source"] = "requirement_match" if requested_styles or query.city or query.budget_min is not None or query.budget_max is not None else "style_affinity" if style_match else "photographer_affinity" if affinity else "popular_package"
        candidates.append(candidate)
    if query.sort_mode == "nearest":
        candidates.sort(key=lambda x: (x["distance_km"] is None, x["distance_km"] or 0, -x["rank_score"], str(x["id"])))
    elif query.sort_mode == "lowest_price":
        candidates.sort(key=lambda x: (x["price"], -x["rank_score"], str(x["id"])))
    elif query.sort_mode == "earliest_available":
        candidates.sort(key=lambda x: (((x["availability"] or {}).get("matching_slots") or [{"start_at": "9999"}])[0]["start_at"], -x["rank_score"], str(x["id"])))
    else:
        candidates.sort(key=lambda x: (-x["rank_score"], -x["trend_score"], str(x["id"])))
    if metrics is not None:
        metrics.update(
            candidate_count_after_city=after_city,
            candidate_count_after_budget=after_budget,
            candidate_count_after_availability=after_availability,
            candidate_count_after_distance=after_distance,
            availability_query_ms=availability_query_ms,
        )
    return _diversify_candidates(candidates)


def _fallback_attempts(query: PackageRecommendationQuery) -> list[tuple[int, PackageRecommendationQuery, bool, float, list[dict]]]:
    """生成逐级放宽条件的回退查询序列。"""
    attempts: list[tuple[int, PackageRecommendationQuery, bool, float, list[dict]]] = []
    fallback_query = query
    enforce_style = bool(query.styles)
    relaxations: list[dict] = []
    if query.styles:
        enforce_style = False
        relaxations = [{"code": "style_similarity", "label": "已放宽风格相似度"}]
        attempts.append((1, fallback_query, enforce_style, 1.0, list(relaxations)))
    next_distance = _next_distance_tier(query.max_distance_km)
    if next_distance is not None and next_distance > float(query.max_distance_km or 0):
        fallback_query = fallback_query.model_copy(update={"max_distance_km": next_distance})
        relaxations.append({
            "code": "max_distance_km", "label": f"距离范围已由 {query.max_distance_km:g} 公里扩大到 {next_distance:g} 公里",
            "from": query.max_distance_km, "to": next_distance,
        })
        attempts.append((2, fallback_query, enforce_style, 1.0, list(relaxations)))
    if query.shoot_date and query.time_start and query.time_end:
        fallback_query = fallback_query.model_copy(update={"time_start": None, "time_end": None})
        relaxations.append({"code": "same_date_other_times", "label": "已改为查看同日其他可预约时间"})
        attempts.append((3, fallback_query, enforce_style, 1.0, list(relaxations)))
    return attempts


def _serialize_package_items(page: list[dict], query: PackageRecommendationQuery) -> list[dict]:
    """将套餐候选序列化为对外展示条目，附推荐理由与警告。"""
    requested_styles = {normalize_tag(x) for x in query.styles if x}
    reasons = {"requirement_match": "符合你的拍摄风格、地区或预算需求", "style_affinity": "与你喜欢的作品风格相符", "photographer_affinity": "来自你关注或喜欢的摄影师", "popular_package": "近期受欢迎的摄影方案"}
    items = []
    for package in page:
        public = {key: package.get(key) for key in ("id", "package_name", "price", "duration", "image_count", "description", "includes", "styles", "city", "samples", "sample_thumbnails", "photographer_id", "photographer_name", "photographer_avatar", "photographer_location")}
        recommendation_reasons = []
        warnings = []
        if requested_styles and package["match"]["style_score"] > 0:
            recommendation_reasons.append("风格标签与你的需求匹配")
        if query.budget_max is not None:
            if package["price"] <= query.budget_max:
                recommendation_reasons.append("价格在预算内")
            else:
                warnings.append(f"超出预算 {package['price'] - query.budget_max:.0f} 元")
        if package["distance_km"] is not None:
            recommendation_reasons.append(f"距拍摄地点{distance_label(package['distance_km']).removeprefix('约')}")
        if package["availability"] and package["availability"]["matching_slots"]:
            recommendation_reasons.append(f"指定日期有 {len(package['availability']['matching_slots'])} 个匹配时段")
        match_public = {key: round(float(value), 4) for key, value in package["match"].items() if value is not None and key in {"style_score", "budget_score", "availability_score", "distance_score", "quality_score"}}
        match_public["overall_score"] = round(package["rank_score"], 4)
        public.update(candidate_source=package["candidate_source"], recommendation_reason=reasons[package["candidate_source"]], distance_km=round(package["distance_km"], 1) if package["distance_km"] is not None else None, distance_label=distance_label(package["distance_km"]), distance_confidence="exact" if package["distance_km"] is not None else "unknown", availability=package["availability"], match=match_public, recommendation_reasons=recommendation_reasons or [reasons[package["candidate_source"]]], warnings=warnings)
        items.append(public)
    return items


def recommend_packages(db: Session, viewer_user_id: int | None, cursor: str | None, limit: int, query: PackageRecommendationQuery, session_id: str | None) -> dict:
    """执行套餐推荐主流程（含缓存与多级回退），返回推荐结果。"""
    request_started = perf_counter()
    offset = _decode_cursor(cursor)
    is_legacy_query = not any((query.shoot_date, query.time_start, query.time_end, query.duration_minutes, query.location_text, query.latitude, query.longitude, query.max_distance_km, query.require_exact_availability, query.budget_strict, query.date_strict, query.sort_mode != "best_match"))
    identity = str(viewer_user_id or session_id or "anonymous")
    feature_enabled = is_joint_recommendation_enabled(identity)
    joint_mode = not is_legacy_query and feature_enabled
    algorithm_version = PACKAGE_ALGORITHM_VERSION if joint_mode else LEGACY_PACKAGE_ALGORITHM_VERSION
    context = query.model_dump_json(exclude_none=True)
    cache_key = f"rec:packages:{algorithm_version}:{identity}:{context}:{offset}:{limit}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached
    packages = _load_packages(db)
    _sync_package_stats(db, packages)
    works = _load_works(db)
    profile = build_user_profile(db, viewer_user_id, {str(x["id"]): x for x in works}) if viewer_user_id else {"tag_preferences": {}, "author_preferences": {}, "event_count": 0}
    observability = {"candidate_count_before_filters": len(packages)}
    ranking_started = perf_counter()
    enforce_style = bool(query.styles) and joint_mode
    candidates = _rank_package_candidates(db, packages, profile, query, enforce_style=enforce_style, metrics=observability)
    fallback_level = 0
    relaxations: list[dict] = []
    if not candidates and joint_mode:
        fallback_attempts = _fallback_attempts(query)
        for level, fallback_query, fallback_style, overage_ratio, applied_relaxations in fallback_attempts:
            fallback_candidates = _rank_package_candidates(
                db, packages, profile, fallback_query,
                enforce_style=fallback_style and bool(query.styles),
                budget_overage_ratio=overage_ratio,
            )
            if fallback_candidates:
                candidates = fallback_candidates
                fallback_level = level
                relaxations = applied_relaxations
                break
        if not candidates and query.shoot_date and not query.date_strict:
            alternate_candidates: list[dict] = []
            seen_package_ids: set[str] = set()
            base_query = query
            enforce_fallback_style = bool(query.styles)
            base_relaxations: list[dict] = []
            if fallback_attempts:
                _, last_query, enforce_fallback_style, _, base_relaxations = fallback_attempts[-1]
                base_query = last_query.model_copy(update={"time_start": query.time_start, "time_end": query.time_end})
            for delta in (-1, 1, -2, 2, -3, 3):
                fallback_query = base_query.model_copy(update={"shoot_date": query.shoot_date + timedelta(days=delta)})
                for candidate in _rank_package_candidates(db, packages, profile, fallback_query, enforce_style=enforce_fallback_style):
                    package_id = str(candidate["id"])
                    if package_id in seen_package_ids:
                        continue
                    candidate["alternate_date_delta"] = delta
                    alternate_candidates.append(candidate)
                    seen_package_ids.add(package_id)
            if alternate_candidates:
                candidates = alternate_candidates
                fallback_level = 4
                relaxations = [
                    item for item in base_relaxations if item["code"] != "same_date_other_times"
                ] + [{"code": "nearby_dates", "label": "已查看前后 3 天的相同时间窗", "from": query.shoot_date.isoformat(), "range_days": 3}]
        if not candidates and query.budget_max is not None and not query.budget_strict:
            budget_candidates = _rank_package_candidates(
                db, packages, profile, query,
                enforce_style=bool(query.styles),
                budget_overage_ratio=1.1,
            )
            if budget_candidates:
                candidates = budget_candidates
                fallback_level = 5
                relaxations = [{
                    "code": "budget_overage", "label": "已展示最多超预算 10% 的方案，选择前请确认价格",
                    "from": query.budget_max, "to": round(query.budget_max * 1.1, 2),
                }]
    page = candidates[offset:offset + limit]
    items = _serialize_package_items(page, query)
    observability.update(
        ranking_ms=round((perf_counter() - ranking_started) * 1000, 3),
        geocoding_source="coordinates" if query.latitude is not None else "city_only" if query.city or query.location_text else "none",
        fallback_level=fallback_level,
        total_ms=round((perf_counter() - request_started) * 1000, 3),
    )
    result = {
        "recommendation_id": str(uuid.uuid4()),
        "algorithm_version": algorithm_version,
        "next_cursor": _encode_cursor(offset + limit) if offset + limit < len(candidates) else None,
        "fallback_level": fallback_level,
        "relaxations": relaxations,
        "no_result": not bool(items),
        "feature_enabled": feature_enabled,
        "observability": observability,
        "items": items,
    }
    logger.info("joint_package_recommendation", extra={"recommendation": {**observability, "recommendation_id": result["recommendation_id"], "algorithm_version": algorithm_version, "feature_enabled": feature_enabled}})
    cache_set(cache_key, result, 90 if query.require_exact_availability else 300)
    return result
