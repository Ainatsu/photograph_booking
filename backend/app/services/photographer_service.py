"""摄影师领域服务：资料维护、作品与套餐查询及默认值规范化。"""

import uuid as _uuid
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy import String, cast, func, or_
from backend.app.models.photographer import PhotographerProfile
from backend.app.models.user import User
from backend.app.models.order import Order, OrderStatus
from backend.app.utils.file_upload import create_thumbnail_for_url
from backend.app.services.follow_service import get_follower_count, get_following_count
from backend.app.services.availability_service import (
    format_time_range,
    normalize_availability_entries,
    parse_time_range,
)


def _assign_ids(items: list) -> list:
    """给 portfolio / packages 中每个条目补上 id 字段（仅在没有 id 时才生成）"""
    for item in items:
        if isinstance(item, dict) and "id" not in item:
            item["id"] = _uuid.uuid4().hex
    return items


def _normalize_package_defaults(packages: list) -> list:
    """为套餐条目补齐默认字段值。"""
    for package in packages:
        if not isinstance(package, dict):
            continue
        package.setdefault("is_active", True)
        package.setdefault("delivery_formats", ["JPG"])
        package.setdefault("included_revision_count", 0)
        package.setdefault("delivery_days", 7)
        package.setdefault("commercial_license", False)
        package.setdefault("payment_mode", "full")
        package.setdefault("deposit_rate", 0.30)
        package.setdefault("fulfillment_mode", "single_delivery")
        if package.get("retouched_image_count") is None and package.get("image_count") is not None:
            package["retouched_image_count"] = package.get("image_count")
    return packages


def _tag_id(item: dict) -> str:
    """获取条目的 id，若无则生成并返回（用于只读场景）"""
    if isinstance(item, dict) and "id" not in item:
        item["id"] = _uuid.uuid4().hex
    return item.get("id", "")


def _split_tags(value: str) -> list[str]:
    """按常见分隔符拆分标签字符串并去除空白。"""
    return [
        tag.strip()
        for tag in (value or "").replace("，", ",").replace("、", ",").replace("\n", ",").split(",")
        if tag.strip()
    ]


def _search_text(*values) -> str:
    """将多个字段拼接为小写搜索文本。"""
    parts: list[str] = []
    for value in values:
        if value is None:
            continue
        if isinstance(value, (list, tuple, set)):
            parts.extend(str(item) for item in value if item is not None)
        else:
            parts.append(str(value))
    return " ".join(parts).casefold()


def _matches_search(term: str | None, *values) -> bool:
    """判断搜索词是否命中给定字段，空词视为全部命中。"""
    normalized = (term or "").strip().casefold()
    return not normalized or normalized in _search_text(*values)


def _normalize_slot_list(slots: list | None) -> list[str]:
    """将时段列表规范化并去重为统一格式。"""
    normalized = []
    for slot in slots or []:
        parsed = parse_time_range(slot)
        if parsed:
            normalized.append(format_time_range(parsed[0], parsed[1]))
    return normalized


def _work_images(item: dict) -> list[str]:
    """提取作品的图片 URL 列表。"""
    images = item.get("images")
    if isinstance(images, list):
        return [url for url in images if isinstance(url, str) and url]
    url = item.get("url")
    return [url] if isinstance(url, str) and url else []


def _work_thumbnail_urls(item: dict, media_type: str) -> list[str]:
    """计算作品缩略图 URL 列表，缺失项用原图补齐。"""
    images = _work_images(item)
    thumbnails = item.get("thumbnail_urls")
    if isinstance(thumbnails, list):
        clean = [url if isinstance(url, str) else "" for url in thumbnails]
    else:
        clean = []

    if len(clean) < len(images):
        clean.extend([""] * (len(images) - len(clean)))

    if item.get("thumbnail_url") and clean:
        clean[0] = item.get("thumbnail_url")
    elif item.get("thumbnail_url"):
        clean = [item.get("thumbnail_url")]

    if media_type != "video":
        clean = [thumb or images[index] for index, thumb in enumerate(clean[:len(images)])]
    return clean


def _normalize_available_hours(entries: list | None) -> list[dict]:
    """规范化每周可约时段，丢弃空条目。"""
    normalized = []
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        day = str(entry.get("day") or "").strip()
        slots = _normalize_slot_list(entry.get("slots") or [])
        if day and slots:
            normalized.append({"day": day, "slots": slots})
    return normalized


def _normalize_availability_exceptions(entries: list | None) -> list[dict]:
    """规范化可用性例外日期列表。"""
    return normalize_availability_entries(entries)


def _package_styles(pkg: dict) -> list[str]:
    """获取套餐风格列表（兼容 includes 字段）。"""
    return pkg.get("styles") or pkg.get("includes") or []


def _ensure_portfolio_thumbnails(portfolio: list) -> bool:
    """为作品图片生成缺失的缩略图，返回是否有变更。"""
    changed = False
    for item in portfolio:
        if not isinstance(item, dict) or not item.get("url"):
            continue
        if item.get("media_type") == "video":
            continue
        images = _work_images(item)
        thumbnails = list(item.get("thumbnail_urls") or [])
        if len(thumbnails) < len(images):
            thumbnails.extend([""] * (len(images) - len(thumbnails)))

        item_changed = False
        for index, image_url in enumerate(images):
            if thumbnails[index] and thumbnails[index] != image_url:
                continue
            thumbnail_url = create_thumbnail_for_url(image_url)
            if thumbnail_url:
                thumbnails[index] = thumbnail_url
                item_changed = True

        if item_changed:
            item["thumbnail_urls"] = thumbnails
            if thumbnails[0]:
                item["thumbnail_url"] = thumbnails[0]
            changed = True
    return changed


def _ensure_package_thumbnails(packages: list) -> bool:
    """为套餐样片生成缺失的缩略图，返回是否有变更。"""
    changed = False
    for pkg in packages:
        if not isinstance(pkg, dict):
            continue
        samples = pkg.get("samples") or []
        if not isinstance(samples, list):
            samples = [samples]
        thumbnails = list(pkg.get("sample_thumbnails") or [])
        if len(thumbnails) < len(samples):
            thumbnails.extend([""] * (len(samples) - len(thumbnails)))

        pkg_changed = False
        for index, sample_url in enumerate(samples):
            if not sample_url:
                continue
            if thumbnails[index] and thumbnails[index] != sample_url:
                continue
            thumbnail_url = create_thumbnail_for_url(sample_url)
            if thumbnail_url:
                thumbnails[index] = thumbnail_url
                pkg_changed = True

        if pkg_changed:
            pkg["sample_thumbnails"] = thumbnails
            changed = True
    return changed


def _get_avg_rating(db: Session, photographer_id: int) -> float | None:
    """计算摄影师的客户平均评分（5 分制）"""
    result = db.query(func.avg(Order.rating)).filter(
        Order.photographer_id == photographer_id,
        Order.rating.isnot(None),
        Order.status != OrderStatus.CANCELLED,
    ).scalar()
    if result is None:
        return None
    return round(result / 2, 1)


def create_or_update_profile(db: Session, user_id: int, data: dict) -> PhotographerProfile:
    """创建或更新摄影师资料并刷新推荐与 AI 索引。"""
    # 自动给 portfolio 和 packages 条目补 id
    if data.get("portfolio"):
        data["portfolio"] = _assign_ids(data["portfolio"])
    if data.get("packages"):
        data["packages"] = _normalize_package_defaults(_assign_ids(data["packages"]))
    if "available_hours" in data and data["available_hours"] is not None:
        data["available_hours"] = _normalize_available_hours(data["available_hours"])
    if "availability_exceptions" in data and data["availability_exceptions"] is not None:
        data["availability_exceptions"] = _normalize_availability_exceptions(data["availability_exceptions"])

    profile = db.query(PhotographerProfile).filter(PhotographerProfile.user_id == user_id).first()
    if profile:
        for key, value in data.items():
            if value is not None:
                setattr(profile, key, value)
    else:
        profile = PhotographerProfile(user_id=user_id, **data)
        db.add(profile)
    db.commit()
    db.refresh(profile)
    from backend.app.services.package_recommendation_service import invalidate_package_recommendation_cache
    invalidate_package_recommendation_cache(user_id)
    from backend.app.services.ai_resource_index_service import refresh_ai_resource_documents_for_user
    refresh_ai_resource_documents_for_user(db, user_id)
    return profile


def get_profile_by_user_id(db: Session, user_id: int) -> dict | None:
    """获取单个摄影师的完整资料，含评分与关注数。"""
    _fix_missing_ids(db)
    profile = db.query(PhotographerProfile).filter(PhotographerProfile.user_id == user_id).first()
    if not profile:
        return None

    portfolio = list(profile.portfolio or [])
    packages = list(profile.packages or [])

    return {
        "id": profile.id,
        "user_id": profile.user_id,
        "user_role": profile.user.role if profile.user else None,
        "user_display_name": profile.user.display_name if profile.user else None,
        "username": profile.user.username if profile.user else None,
        "user_avatar_url": profile.user.avatar_url if profile.user else None,
        "user_bio": profile.user.bio if profile.user else None,
        "public_email": (
            profile.user.email
            if profile.user and profile.user.show_email_on_profile and profile.user.email_verified
            else None
        ),
        "background_url": profile.user.background_url if profile.user else None,
        "cover_image_url": profile.cover_image_url,
        "location": profile.location,
        "service_city": profile.service_city,
        "service_address": profile.service_address,
        "service_latitude": float(profile.service_latitude) if profile.service_latitude is not None else None,
        "service_longitude": float(profile.service_longitude) if profile.service_longitude is not None else None,
        "service_radius_km": profile.service_radius_km,
        "location_source": profile.location_source,
        "styles": (profile.styles or []),
        "equipment": profile.equipment,
        "packages": packages,
        "available_hours": profile.available_hours,
        "availability_exceptions": profile.availability_exceptions,
        "advance_notice": profile.advance_notice,
        "max_daily_bookings": profile.max_daily_bookings,
        "max_booking_date": profile.max_booking_date.isoformat() if profile.max_booking_date else None,
        "portfolio": portfolio,
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
        "avg_rating": _get_avg_rating(db, user_id),
        "follower_count": get_follower_count(db, user_id),
        "following_count": get_following_count(db, user_id),
    }


def get_all_profiles(
    db: Session,
    skip: int = 0,
    limit: int = 20,
    query_text: str | None = None,
    city: str | None = None,
    style: str | None = None,
) -> list[dict]:
    """分页查询摄影师列表，支持关键词、城市与风格过滤。"""
    profile_query = (
        db.query(PhotographerProfile)
        .join(User, PhotographerProfile.user_id == User.id)
        .filter(User.role == "photographer")
    )
    if query_text and query_text.strip():
        pattern = f"%{query_text.strip()}%"
        profile_query = profile_query.filter(or_(
            User.display_name.ilike(pattern),
            User.username.ilike(pattern),
            User.bio.ilike(pattern),
            PhotographerProfile.location.ilike(pattern),
            cast(PhotographerProfile.styles, String).ilike(pattern),
        ))
    if city and city.strip():
        profile_query = profile_query.filter(PhotographerProfile.location.ilike(f"%{city.strip()}%"))
    if style and style.strip():
        profile_query = profile_query.filter(
            cast(PhotographerProfile.styles, String).ilike(f"%{style.strip()}%")
        )
    profiles = profile_query.offset(skip).limit(limit).all()
    result = []
    for p in profiles:
        result.append({
            "id": p.id,
            "user_id": p.user_id,
            "user_display_name": p.user.display_name if p.user else None,
            "username": p.user.username if p.user else None,
            "user_avatar_url": p.user.avatar_url if p.user else None,
            "user_bio": p.user.bio if p.user else None,
            "public_email": (
                p.user.email
                if p.user and p.user.show_email_on_profile and p.user.email_verified
                else None
            ),
            "cover_image_url": p.cover_image_url,
            "location": p.location,
            "service_city": p.service_city,
            "service_address": p.service_address,
            "service_latitude": float(p.service_latitude) if p.service_latitude is not None else None,
            "service_longitude": float(p.service_longitude) if p.service_longitude is not None else None,
            "service_radius_km": p.service_radius_km,
            "location_source": p.location_source,
            "styles": (p.styles or []),
            "equipment": p.equipment,
            "packages": p.packages,
            "available_hours": p.available_hours,
            "availability_exceptions": p.availability_exceptions,
            "advance_notice": p.advance_notice,
            "max_daily_bookings": p.max_daily_bookings,
            "max_booking_date": p.max_booking_date.isoformat() if p.max_booking_date else None,
            "portfolio": p.portfolio,
            "created_at": p.created_at,
            "updated_at": p.updated_at,
            "avg_rating": _get_avg_rating(db, p.user_id),
            "follower_count": get_follower_count(db, p.user_id),
            "following_count": get_following_count(db, p.user_id),
        })
    return result


def _fix_missing_ids(db: Session) -> None:
    """给数据库中所有已有 portfolio / packages 条目补上 id 字段（仅修复，不创建新记录）"""
    profiles = db.query(PhotographerProfile).all()
    dirty = False
    for p in profiles:
        portfolio = list(p.portfolio or [])
        packages = list(p.packages or [])

        pf_before = sum(1 for item in portfolio if isinstance(item, dict) and "id" not in item)
        pk_before = sum(
            1 for item in packages
            if isinstance(item, dict) and ("id" not in item or "is_active" not in item)
        )

        _assign_ids(portfolio)
        _normalize_package_defaults(_assign_ids(packages))
        pf_preview_changed = _ensure_portfolio_thumbnails(portfolio)
        pk_preview_changed = _ensure_package_thumbnails(packages)

        if pf_before > 0 or pf_preview_changed:
            p.portfolio = portfolio
            flag_modified(p, 'portfolio')
            dirty = True
        if pk_before > 0 or pk_preview_changed:
            p.packages = packages
            flag_modified(p, 'packages')
            dirty = True

    if dirty:
        db.commit()
        from backend.app.core.cache import cache_delete, cache_delete_pattern
        from backend.app.services.package_recommendation_service import invalidate_package_recommendation_cache
        cache_delete_pattern("photographer_packages*")
        cache_delete_pattern("photographer_list:*")
        cache_delete_pattern("photographer_works:*")
        for p in profiles:
            cache_delete(f"photographer:{p.user_id}")
        invalidate_package_recommendation_cache()


def get_all_works(
    db: Session,
    skip: int = 0,
    limit: int = 60,
    query_text: str | None = None,
    city: str | None = None,
    style: str | None = None,
) -> list[dict]:
    """分页查询全部作品，支持关键词、城市与风格过滤。"""
    _fix_missing_ids(db)
    profiles = (
        db.query(PhotographerProfile)
        .join(User, PhotographerProfile.user_id == User.id)
        .all()
    )
    works = []
    for p in profiles:
        if city and not _matches_search(city, p.location):
            continue
        for item in (p.portfolio or []):
            if style and not _matches_search(
                style,
                item.get("tag"),
                item.get("tags"),
                p.styles,
            ):
                continue
            if query_text and not _matches_search(
                query_text,
                item.get("title"),
                item.get("description"),
                item.get("tag"),
                item.get("tags"),
                p.user.display_name if p.user else None,
                p.user.username if p.user else None,
                p.location,
                p.styles,
            ):
                continue
            media_type = item.get("media_type") or "image"
            images = _work_images(item)
            thumbnail_urls = _work_thumbnail_urls(item, media_type)
            works.append({
                "id": _tag_id(item),
                "url": item.get("url", "") or (images[0] if images else ""),
                "images": images,
                "media_type": media_type,
                "thumbnail_url": item.get("thumbnail_url") or (thumbnail_urls[0] if thumbnail_urls else ""),
                "thumbnail_urls": thumbnail_urls,
                "compressed_url": item.get("compressed_url", ""),
                "duration": item.get("duration"),
                "compressed_duration": item.get("compressed_duration"),
                "tag": item.get("tag", ""),
                "tags": item.get("tags") or _split_tags(item.get("tag", "")),
                "title": item.get("title", ""),
                "description": item.get("description", ""),
                "user_id": p.user_id,
                "user_display_name": p.user.display_name if p.user else None,
                "user_avatar_url": p.user.avatar_url if p.user else None,
            })
    works.sort(key=lambda w: w["title"] or "", reverse=True)
    return works[skip:skip + limit]


def get_all_packages(
    db: Session,
    query_text: str | None = None,
    city: str | None = None,
    style: str | None = None,
    budget_min: int | None = None,
    budget_max: int | None = None,
    skip: int = 0,
    limit: int | None = None,
) -> list[dict]:
    """获取所有摄影师的方案（含摄影师信息）"""
    _fix_missing_ids(db)
    profiles = (
        db.query(PhotographerProfile)
        .join(User, PhotographerProfile.user_id == User.id)
        .filter(User.role == "photographer")
        .all()
    )
    packages = []
    for p in profiles:
        for pkg in (p.packages or []):
            # 跳过没有名称的方案
            if not pkg.get("name") or pkg.get("is_active", True) is False:
                continue
            package_styles = _package_styles(pkg)
            package_city = pkg.get("city") or p.location
            if city and package_city and not _matches_search(city, package_city):
                continue
            if style and not _matches_search(style, package_styles, p.styles):
                continue
            try:
                package_price = float(pkg.get("price") or 0)
            except (TypeError, ValueError):
                package_price = 0
            if budget_min is not None and package_price < budget_min:
                continue
            if budget_max is not None and package_price > budget_max:
                continue
            if query_text and not _matches_search(
                query_text,
                pkg.get("name"),
                pkg.get("description"),
                package_styles,
                package_city,
                p.user.display_name if p.user else None,
                p.user.username if p.user else None,
            ):
                continue
            packages.append({
                "id": _tag_id(pkg),
                "package_name": pkg.get("name", ""),
                "price": pkg.get("price", 0),
                "duration": pkg.get("duration", 0),
                "image_count": pkg.get("image_count", 0),
                "description": pkg.get("description", ""),
                "includes": pkg.get("includes", []),
                "styles": package_styles,
                "city": pkg.get("city", ""),
                "samples": pkg.get("samples", []),
                "sample_thumbnails": pkg.get("sample_thumbnails", []),
                "is_active": pkg.get("is_active", True),
                "service_location": pkg.get("service_location"),
                "original_image_count": pkg.get("original_image_count"),
                "retouched_image_count": pkg.get("retouched_image_count", pkg.get("image_count")),
                "delivery_formats": pkg.get("delivery_formats") or ["JPG"],
                "included_revision_count": pkg.get("included_revision_count", 0),
                "delivery_days": pkg.get("delivery_days", 7),
                "commercial_license": pkg.get("commercial_license", False),
                "terms_rules": pkg.get("terms_rules"),
                "copyright_terms": pkg.get("copyright_terms"),
                "cancellation_policy": pkg.get("cancellation_policy"),
                "reschedule_policy": pkg.get("reschedule_policy"),
                "payment_mode": pkg.get("payment_mode", "full"),
                "deposit_rate": pkg.get("deposit_rate", 0.30),
                "fulfillment_mode": pkg.get("fulfillment_mode", "single_delivery"),
                "photographer_id": p.user_id,
                "photographer_name": p.user.display_name if p.user else None,
                "photographer_avatar": p.user.avatar_url if p.user else None,
                "photographer_location": p.location,
            })
    if limit is None:
        return packages[skip:]
    return packages[skip:skip + limit]


def get_package_by_id(db: Session, package_id: str) -> dict | None:
    """根据套餐 ID 获取单个方案的详细信息（含摄影师信息）"""
    _fix_missing_ids(db)
    profiles = (
        db.query(PhotographerProfile)
        .join(User, PhotographerProfile.user_id == User.id)
        .filter(User.role == "photographer")
        .all()
    )
    for p in profiles:
        for pkg in (p.packages or []):
            pkid = _tag_id(pkg)
            if pkid == package_id and pkg.get("is_active", True) is not False:
                return {
                    "id": pkid,
                    "package_name": pkg.get("name", ""),
                    "price": pkg.get("price", 0),
                    "duration": pkg.get("duration", 0),
                    "image_count": pkg.get("image_count", 0),
                    "description": pkg.get("description", ""),
                    "includes": pkg.get("includes", []),
                    "styles": _package_styles(pkg),
                    "city": pkg.get("city", ""),
                    "samples": pkg.get("samples", []),
                    "sample_thumbnails": pkg.get("sample_thumbnails", []),
                    "is_active": pkg.get("is_active", True),
                    "service_location": pkg.get("service_location"),
                    "original_image_count": pkg.get("original_image_count"),
                    "retouched_image_count": pkg.get("retouched_image_count", pkg.get("image_count")),
                    "delivery_formats": pkg.get("delivery_formats") or ["JPG"],
                    "included_revision_count": pkg.get("included_revision_count", 0),
                    "delivery_days": pkg.get("delivery_days", 7),
                    "commercial_license": pkg.get("commercial_license", False),
                    "terms_rules": pkg.get("terms_rules"),
                    "copyright_terms": pkg.get("copyright_terms"),
                    "cancellation_policy": pkg.get("cancellation_policy"),
                    "reschedule_policy": pkg.get("reschedule_policy"),
                    "payment_mode": pkg.get("payment_mode", "full"),
                    "deposit_rate": pkg.get("deposit_rate", 0.30),
                    "fulfillment_mode": pkg.get("fulfillment_mode", "single_delivery"),
                    "photographer_id": p.user_id,
                    "photographer_name": p.user.display_name if p.user else None,
                    "photographer_avatar": p.user.avatar_url if p.user else None,
                    "photographer_location": p.location,
                    "photographer_bio": p.user.bio if p.user else None,
                }
    return None


def get_work_by_id(db: Session, work_id: str) -> dict | None:
    """根据作品 ID 获取单个作品的详细信息（含摄影师信息）"""
    _fix_missing_ids(db)
    profiles = (
        db.query(PhotographerProfile)
        .join(User, PhotographerProfile.user_id == User.id)
        .all()
    )
    for p in profiles:
        for item in (p.portfolio or []):
            wid = _tag_id(item)
            if wid == work_id:
                media_type = item.get("media_type") or "image"
                images = _work_images(item)
                thumbnail_urls = _work_thumbnail_urls(item, media_type)
                return {
                    "id": wid,
                    "url": item.get("url", "") or (images[0] if images else ""),
                    "images": images,
                    "media_type": media_type,
                    "thumbnail_url": item.get("thumbnail_url") or (thumbnail_urls[0] if thumbnail_urls else ""),
                    "thumbnail_urls": thumbnail_urls,
                    "compressed_url": item.get("compressed_url", ""),
                    "duration": item.get("duration"),
                    "compressed_duration": item.get("compressed_duration"),
                    "tag": item.get("tag", ""),
                    "tags": item.get("tags") or _split_tags(item.get("tag", "")),
                    "title": item.get("title", ""),
                    "description": item.get("description", ""),
                    "user_id": p.user_id,
                    "user_display_name": p.user.display_name if p.user else None,
                    "user_avatar_url": p.user.avatar_url if p.user else None,
                    "user_bio": p.user.bio if p.user else None,
                }
    return None
