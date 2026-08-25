"""拍摄企划推荐服务：按风格、城市、档期与预算为摄影师匹配开放企划。"""

import math
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session, joinedload

from backend.app.core.cache import cache_get, cache_set
from backend.app.models.photographer import PhotographerProfile
from backend.app.models.project import ProjectApplication, ProjectStatus, ShootProject
from backend.app.models.user import User
from backend.app.services.availability_service import get_day_availability
from backend.app.services.photographer_service import _package_styles
from backend.app.services.project_service import expire_open_projects, serialize_project
from backend.app.services.recommendation_profile_service import normalize_tag
from backend.app.services.recommendation_service import _decode_cursor, _encode_cursor

PROJECT_ALGORITHM_VERSION = "project_match_v1"


def _profile_features(profile: PhotographerProfile) -> tuple[set[str], list[tuple[float, float]]]:
    """提取摄影师风格标签与套餐价格区间特征。"""
    tags = {normalize_tag(x) for x in (profile.styles or []) if x}
    price_ranges = []
    for package in profile.packages or []:
        tags.update(normalize_tag(x) for x in _package_styles(package) if x)
        try:
            price = float(package.get("price") or 0)
        except (TypeError, ValueError):
            price = 0
        if price > 0:
            price_ranges.append((price * .8, price * 1.2))
    for work in profile.portfolio or []:
        for value in [work.get("tag"), *(work.get("tags") or [])]:
            if value:
                tags.add(normalize_tag(value))
    return tags, price_ranges


def _budget_fit(project: ShootProject, price_ranges: list[tuple[float, float]]) -> float:
    """计算项目预算与摄影师价格区间的匹配度。"""
    if not price_ranges or (project.budget_min is None and project.budget_max is None):
        return .5
    project_low = float(project.budget_min or 0)
    project_high = float(project.budget_max or max(project_low, 1))
    best = 0.0
    for low, high in price_ranges:
        overlap = max(0, min(project_high, high) - max(project_low, low))
        union = max(project_high, high) - min(project_low, low)
        best = max(best, overlap / max(1, union))
    return best


def _deliverable_fit(project: ShootProject, profile: PhotographerProfile) -> float:
    """计算项目交付物要求与摄影师套餐的匹配度。"""
    requested = str(project.deliverables or "").lower()
    if not requested:
        return .6
    package_text = " ".join(str(package) for package in (profile.packages or [])).lower()
    tokens = [token for token in ("精修", "底片", "视频", "相册", "retouched", "raw", "video") if token in requested]
    return sum(token in package_text for token in tokens) / max(1, len(tokens)) if tokens else .6


def recommend_projects(db: Session, photographer: User, cursor: str | None, limit: int, city: str | None, styles: list[str], budget_min: int | None, budget_max: int | None, session_id: str | None) -> dict:
    """按多维匹配度为摄影师推荐开放企划，返回带缓存的分页结果。"""
    offset = _decode_cursor(cursor)
    context = f"{city or '-'}:{','.join(styles)}:{budget_min}:{budget_max}"
    cache_key = f"rec:projects:{PROJECT_ALGORITHM_VERSION}:{photographer.id}:{context}:{offset}:{limit}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached
    expire_open_projects(db)
    profile = db.query(PhotographerProfile).filter_by(user_id=photographer.id).first()
    if not profile:
        return {"recommendation_id": str(uuid.uuid4()), "algorithm_version": PROJECT_ALGORITHM_VERSION, "next_cursor": None, "items": []}
    photographer_tags, price_ranges = _profile_features(profile)
    requested_tags = {normalize_tag(x) for x in styles if x}
    applied_ids = {row[0] for row in db.query(ProjectApplication.project_id).filter(ProjectApplication.photographer_id == photographer.id).all()}
    projects = db.query(ShootProject).options(joinedload(ShootProject.customer)).filter(ShootProject.status == ProjectStatus.OPEN, ShootProject.visibility == "public").all()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    candidates = []
    for project in projects:
        if project.id in applied_ids:
            continue
        expires_at = project.expires_at.replace(tzinfo=None) if project.expires_at and project.expires_at.tzinfo else project.expires_at
        if expires_at and expires_at <= now:
            continue
        if budget_min is not None and project.budget_max is not None and project.budget_max < budget_min:
            continue
        if budget_max is not None and project.budget_min is not None and project.budget_min > budget_max:
            continue
        if price_ranges and project.budget_max is not None and all(low > project.budget_max for low, _ in price_ranges):
            continue
        shoot_date = project.shoot_date_start.date() if project.shoot_date_start else None
        day_is_busy = bool(shoot_date and get_day_availability(profile, shoot_date).get("status") == "busy")
        notice_is_short = bool(project.shoot_date_start and profile.advance_notice and project.shoot_date_start < now + timedelta(hours=profile.advance_notice))
        project_tags = {normalize_tag(project.category), *(normalize_tag(x) for x in (project.style_tags or []))}
        target_tags = requested_tags or photographer_tags
        style_match = len(project_tags & target_tags) / max(1, len(project_tags))
        preferred_city = city or profile.location
        city_match = 1.0 if preferred_city and project.city == preferred_city else .55 if not preferred_city else .2
        schedule_fit = .2 if day_is_busy else .35 if notice_is_short else 1.0 if shoot_date else .55
        budget_fit = _budget_fit(project, price_ranges)
        deliverable_fit = _deliverable_fit(project, profile)
        historical_affinity = min(1.0, style_match + .15 * bool(project.category and normalize_tag(project.category) in photographer_tags))
        created = project.created_at
        aware = created if created and created.tzinfo else created.replace(tzinfo=timezone.utc) if created else None
        freshness = math.exp(-max(0, (datetime.now(timezone.utc) - aware).total_seconds()) / (86400 * 14)) if aware else .3
        missing = sum(not getattr(project, key) for key in ("description", "city", "category")) / 3
        unclear_budget = .15 if project.budget_min is None and project.budget_max is None else 0
        schedule_risk = .12 if day_is_busy else .06 if notice_is_short else 0
        risk_penalty = .2 * missing + unclear_budget + schedule_risk
        application_count = db.query(ProjectApplication).filter(ProjectApplication.project_id == project.id).count()
        exploration = 1.0 if application_count == 0 else max(0, 1 - application_count / 10)
        score = .24 * style_match + .20 * city_match + .16 * schedule_fit + .15 * budget_fit + .10 * deliverable_fit + .08 * historical_affinity + .04 * freshness + .03 * exploration - risk_penalty
        source = "style_match" if style_match >= .5 else "local_project" if city_match >= .8 else "new_project"
        candidates.append((score, freshness, project, source))
    candidates.sort(key=lambda item: (item[0], item[1], item[2].id), reverse=True)
    page = candidates[offset:offset + limit]
    reasons = {"style_match": "与你擅长的拍摄类型和风格匹配", "local_project": "位于你的服务城市且档期可匹配", "new_project": "为你探索的新发布拍摄企划"}
    items = []
    for _, _, project, source in page:
        item = serialize_project(db, project, photographer)
        item.update(candidate_source=source, match_reason=reasons[source])
        items.append(item)
    result = {"recommendation_id": str(uuid.uuid4()), "algorithm_version": PROJECT_ALGORITHM_VERSION, "next_cursor": _encode_cursor(offset + limit) if offset + limit < len(candidates) else None, "items": items}
    cache_set(cache_key, result, 300)
    return result
