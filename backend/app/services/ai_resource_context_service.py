"""构建摄影师、作品与套餐资源文档，供 AI 检索与上下文使用。"""

from typing import Any

from backend.app.models.photographer import PhotographerProfile


CONTEXT_SCHEMA_VERSION = "ai_context_v1"


def build_price_label(price: Any) -> str | None:
    """将价格数值格式化为人民币价格标签。"""
    numeric = _to_float(price)
    if numeric is None:
        return None
    return f"¥{numeric:g}"


def build_price_tags(price: Any, duration: Any = None, image_count: Any = None) -> list[str]:
    """根据价格区间、时长与精修张数生成价格标签列表。"""
    numeric = _to_float(price)
    tags: list[str] = []
    if numeric is None:
        return tags

    if numeric <= 500:
        tags.append("500元内")
    elif numeric <= 1000:
        tags.append("千元内")
    elif numeric <= 2000:
        tags.append("1000-2000元")
    else:
        tags.append("2000元以上")

    duration_value = _to_int(duration)
    if duration_value:
        tags.append(f"{duration_value}分钟")

    image_count_value = _to_int(image_count)
    if image_count_value:
        tags.append(f"精修{image_count_value}张")

    return tags


def build_search_text(*values: Any) -> str:
    """把多个字段展开并去重后拼接为搜索文本。"""
    parts: list[str] = []
    for value in values:
        parts.extend(_flatten_text(value))
    return " ".join(_dedupe(parts))


def build_resource_documents(profiles: list[PhotographerProfile]) -> dict[str, list[dict[str, Any]]]:
    """批量将摄影师资料转换为摄影师/作品/套餐三类资源文档。"""
    documents = {
        "photographers": [],
        "portfolio_items": [],
        "packages": [],
    }
    for profile in profiles:
        package_summaries = _package_summaries(profile)
        portfolio_summaries = _portfolio_summaries(profile)

        documents["photographers"].append(
            _build_photographer_document(profile, package_summaries, portfolio_summaries)
        )

        for item in profile.portfolio or []:
            if isinstance(item, dict):
                documents["portfolio_items"].append(
                    _build_portfolio_document(profile, item, package_summaries)
                )

        for pkg in profile.packages or []:
            if isinstance(pkg, dict):
                documents["packages"].append(_build_package_document(profile, pkg))

    return documents


def _build_photographer_document(
    profile: PhotographerProfile,
    package_summaries: list[dict[str, Any]],
    portfolio_summaries: list[dict[str, Any]],
) -> dict[str, Any]:
    """构建单个摄影师的资源检索文档。"""
    user = profile.user
    display_name = user.display_name if user else None
    user_bio = user.bio if user else None
    price_range = _price_range(profile.packages or [])
    payload = {
        "id": profile.id,
        "user_id": profile.user_id,
        "user_display_name": display_name,
        "user_avatar_url": user.avatar_url if user else None,
        "user_bio": user_bio,
        "cover_image_url": profile.cover_image_url,
        "location": profile.location,
        "styles": profile.styles or [],
        "equipment": profile.equipment,
        "price_range": price_range,
        "package_summaries": package_summaries[:3],
        "portfolio_summaries": portfolio_summaries[:3],
    }
    price_tags = _dedupe(tag for pkg in package_summaries for tag in pkg.get("price_tags", []))
    search_text = build_search_text(
        display_name,
        user_bio,
        profile.location,
        profile.styles,
        profile.equipment,
        price_range.get("label") if price_range else None,
        price_tags,
        package_summaries[:3],
        portfolio_summaries[:3],
    )
    return _resource_document(
        resource_type="photographer",
        resource_id=profile.id,
        owner_user_id=profile.user_id,
        title=display_name or f"摄影师 {profile.user_id}",
        summary=user_bio or " ".join(profile.styles or []),
        tags=profile.styles or [],
        city=profile.location,
        price=price_range["min"] if price_range else None,
        price_label=price_range["label"] if price_range else None,
        price_tags=price_tags,
        search_text=search_text,
        payload=payload,
    )


def _build_portfolio_document(
    profile: PhotographerProfile,
    item: dict[str, Any],
    package_summaries: list[dict[str, Any]],
) -> dict[str, Any]:
    """构建单个作品（图/视频）的资源检索文档。"""
    user = profile.user
    media_type = item.get("media_type") or "image"
    tags = item.get("tags") or _split_tags(item.get("tag", ""))
    related_package_prices = [
        {
            "id": pkg.get("id"),
            "name": pkg.get("name"),
            "price": pkg.get("price"),
            "price_label": pkg.get("price_label"),
            "price_tags": pkg.get("price_tags", []),
        }
        for pkg in package_summaries[:3]
    ]
    price_tags = _dedupe(tag for pkg in related_package_prices for tag in pkg.get("price_tags", []))
    payload = {
        "id": item.get("id", ""),
        "url": item.get("url", ""),
        "thumbnail_url": item.get("thumbnail_url") or ("" if media_type == "video" else item.get("url", "")),
        "compressed_url": item.get("compressed_url", ""),
        "media_type": media_type,
        "duration": item.get("duration"),
        "compressed_duration": item.get("compressed_duration"),
        "tag": item.get("tag", ""),
        "tags": tags,
        "title": item.get("title", ""),
        "description": item.get("description", ""),
        "user_id": profile.user_id,
        "user_display_name": user.display_name if user else None,
        "user_avatar_url": user.avatar_url if user else None,
        "photographer_bio": user.bio if user else None,
        "photographer_styles": profile.styles or [],
        "photographer_location": profile.location,
        "related_package_prices": related_package_prices,
        "price_tags": price_tags,
    }
    search_text = build_search_text(
        item.get("title", ""),
        item.get("description", ""),
        item.get("tag", ""),
        tags,
        profile.location,
        profile.styles,
        user.display_name if user else None,
        user.bio if user else None,
        related_package_prices,
    )
    return _resource_document(
        resource_type="portfolio_item",
        resource_id=item.get("id", ""),
        owner_user_id=profile.user_id,
        title=item.get("title", ""),
        summary=item.get("description", ""),
        tags=tags,
        city=profile.location,
        price=None,
        price_label=None,
        price_tags=price_tags,
        search_text=search_text,
        payload=payload,
    )


def _build_package_document(profile: PhotographerProfile, pkg: dict[str, Any]) -> dict[str, Any]:
    """构建单个套餐的资源检索文档。"""
    user = profile.user
    price = _to_float(pkg.get("price"))
    price_label = build_price_label(price)
    price_tags = build_price_tags(price, pkg.get("duration"), pkg.get("image_count"))
    styles = _as_list(pkg.get("styles") or pkg.get("includes"))
    includes = _as_list(pkg.get("includes"))
    service_tags = _dedupe([*includes, *styles])
    makeup_included = _has_makeup(service_tags, pkg.get("name", ""), pkg.get("description", ""))
    city = pkg.get("city") or profile.location
    payload = {
        "id": pkg.get("id", ""),
        "package_name": pkg.get("name", ""),
        "price": pkg.get("price", 0),
        "price_label": price_label,
        "price_tags": price_tags,
        "duration": pkg.get("duration", 0),
        "image_count": pkg.get("image_count", 0),
        "description": pkg.get("description", ""),
        "includes": includes,
        "styles": styles,
        "service_tags": service_tags,
        "makeup_included": makeup_included,
        "city": city,
        "samples": _as_list(pkg.get("samples")),
        "sample_thumbnails": _as_list(pkg.get("sample_thumbnails")),
        "photographer_id": profile.user_id,
        "photographer_name": user.display_name if user else None,
        "photographer_avatar": user.avatar_url if user else None,
        "photographer_location": profile.location,
        "photographer_bio": user.bio if user else None,
        "photographer_styles": profile.styles or [],
    }
    search_text = build_search_text(
        pkg.get("name", ""),
        pkg.get("description", ""),
        includes,
        styles,
        service_tags,
        "含妆" if makeup_included else None,
        city,
        price_label,
        price_tags,
        user.display_name if user else None,
        user.bio if user else None,
        profile.styles,
    )
    return _resource_document(
        resource_type="package",
        resource_id=pkg.get("id", ""),
        owner_user_id=profile.user_id,
        title=pkg.get("name", ""),
        summary=pkg.get("description", ""),
        tags=service_tags,
        city=city,
        price=price,
        price_label=price_label,
        price_tags=price_tags,
        search_text=search_text,
        payload=payload,
    )


def _resource_document(
    resource_type: str,
    resource_id: Any,
    owner_user_id: int,
    title: str | None,
    summary: str | None,
    tags: list[str],
    city: str | None,
    price: float | None,
    price_label: str | None,
    price_tags: list[str],
    search_text: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """按统一结构组装一条资源文档记录。"""
    return {
        "schema_version": CONTEXT_SCHEMA_VERSION,
        "resource_type": resource_type,
        "id": resource_id,
        "owner_user_id": owner_user_id,
        "title": title or "",
        "summary": summary or "",
        "search_text": search_text,
        "tags": tags,
        "city": city,
        "price": price,
        "price_label": price_label,
        "price_tags": price_tags,
        "payload": payload,
    }


def _package_summaries(profile: PhotographerProfile) -> list[dict[str, Any]]:
    """提取摄影师套餐的简要摘要列表。"""
    summaries = []
    for pkg in profile.packages or []:
        if not isinstance(pkg, dict):
            continue
        price = _to_float(pkg.get("price"))
        summaries.append({
            "id": pkg.get("id", ""),
            "name": pkg.get("name", ""),
            "price": pkg.get("price", 0),
            "price_label": build_price_label(price),
            "price_tags": build_price_tags(price, pkg.get("duration"), pkg.get("image_count")),
            "description": pkg.get("description", ""),
            "includes": _as_list(pkg.get("includes")),
            "styles": _as_list(pkg.get("styles") or pkg.get("includes")),
            "service_tags": _dedupe([*_as_list(pkg.get("includes")), *_as_list(pkg.get("styles") or pkg.get("includes"))]),
        })
    return summaries


def _portfolio_summaries(profile: PhotographerProfile) -> list[dict[str, Any]]:
    """提取摄影师作品的简要摘要列表。"""
    summaries = []
    for item in profile.portfolio or []:
        if not isinstance(item, dict):
            continue
        media_type = item.get("media_type") or "image"
        summaries.append({
            "id": item.get("id", ""),
            "title": item.get("title", ""),
            "description": item.get("description", ""),
            "tags": item.get("tags") or _split_tags(item.get("tag", "")),
            "thumbnail_url": item.get("thumbnail_url") or ("" if media_type == "video" else item.get("url", "")),
            "media_type": media_type,
        })
    return summaries


def _price_range(packages: list[dict[str, Any]]) -> dict[str, Any] | None:
    """计算套餐价格区间并生成价格标签，无有效价格返回 None。"""
    prices = [
        price
        for price in (_to_float(pkg.get("price")) for pkg in packages if isinstance(pkg, dict))
        if price is not None
    ]
    if not prices:
        return None
    min_price = min(prices)
    max_price = max(prices)
    label = build_price_label(min_price)
    if min_price != max_price:
        label = f"{build_price_label(min_price)}-{build_price_label(max_price)}"
    return {
        "min": min_price,
        "max": max_price,
        "label": label,
    }


def _flatten_text(value: Any) -> list[str]:
    """递归展开嵌套结构为文本片段列表。"""
    if value is None:
        return []
    if isinstance(value, dict):
        return [part for item in value.values() for part in _flatten_text(item)]
    if isinstance(value, (list, tuple, set)):
        return [part for item in value for part in _flatten_text(item)]
    text = str(value).strip()
    return [text] if text else []


def _as_list(value: Any) -> list[Any]:
    """将任意值规范化为列表。"""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _split_tags(value: str) -> list[str]:
    """按常见分隔符拆分标签字符串并去除空白。"""
    return [
        tag.strip()
        for tag in (value or "").replace("，", ",").replace("、", ",").replace("\n", ",").split(",")
        if tag.strip()
    ]


def _dedupe(values: Any) -> list[str]:
    """按字符串顺序去重并保留非空文本。"""
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _has_makeup(values: Any, *texts: Any) -> bool:
    """判断文本中是否包含化妆/妆造服务，排除不含妆表述。"""
    haystack = " ".join(_flatten_text([values, *texts]))
    if any(term in haystack for term in ("不含化妆", "不含妆", "不带妆", "无妆")):
        return False
    return any(term in haystack for term in ("化妆", "妆造", "含妆", "带妆", "造型"))


def _to_float(value: Any) -> float | None:
    """安全转换数值为浮点数，失败返回 None。"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    """安全转换数值为整数，失败返回 None。"""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
