"""摄影师仪表盘聚合服务。"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from backend.app.models.analytics import AnalyticsEvent
from backend.app.models.favorite import Favorite
from backend.app.models.follow import Follow
from backend.app.models.like import Like
from backend.app.models.message import Message
from backend.app.models.order import Order, OrderStatus
from backend.app.models.order_reschedule import OrderRescheduleRequest, OrderRescheduleStatus
from backend.app.models.photographer import PhotographerProfile
from backend.app.models.project import ProjectApplication, ProjectApplicationStatus
from backend.app.services.order_service import get_photographer_stats


ACTIVE_SCHEDULE_STATUSES = [OrderStatus.AWAITING_PAYMENT, OrderStatus.CONFIRMED, OrderStatus.IN_PROGRESS]
UPCOMING_ORDER_STATUSES = [
    OrderStatus.PENDING,
    OrderStatus.AWAITING_PAYMENT,
    OrderStatus.CONFIRMED,
    OrderStatus.IN_PROGRESS,
]
COMPLETED_STATUSES = [OrderStatus.COMPLETED, OrderStatus.RECEIVED, OrderStatus.REVIEWED]
PUBLIC_COMPLETION_MIN_ORDERS = 5
RANGE_LABELS = {
    "7d": "近 7 天",
    "month": "本月",
    "90d": "近 90 天",
    "all": "全部",
}


def _utc_now_naive() -> datetime:
    """返回不带时区信息的当前 UTC 时间。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _status_value(status: OrderStatus | str) -> str:
    """返回枚举值或字符串形式的状态值。"""
    return status.value if isinstance(status, OrderStatus) else str(status)


def _previous_month_start(month_start: datetime) -> datetime:
    """返回给定月份起点对应的上个月起点。"""
    if month_start.month == 1:
        return month_start.replace(year=month_start.year - 1, month=12)
    return month_start.replace(month=month_start.month - 1)


def _next_month_start(month_start: datetime) -> datetime:
    """返回给定月份起点对应的下个月起点。"""
    if month_start.month == 12:
        return month_start.replace(year=month_start.year + 1, month=1)
    return month_start.replace(month=month_start.month + 1)


def _get_period(range_key: str, now: datetime) -> dict:
    """根据范围键计算当前与上一统计周期的时间区间。"""
    normalized_key = range_key if range_key in RANGE_LABELS else "month"
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if normalized_key == "7d":
        current_start = today_start - timedelta(days=6)
        current_end = now
        previous_start = current_start - timedelta(days=7)
        previous_end = current_start
    elif normalized_key == "90d":
        current_start = today_start - timedelta(days=89)
        current_end = now
        previous_start = current_start - timedelta(days=90)
        previous_end = current_start
    elif normalized_key == "all":
        current_start = None
        current_end = None
        previous_start = None
        previous_end = None
    else:
        current_start = today_start.replace(day=1)
        current_end = _next_month_start(current_start)
        previous_start = _previous_month_start(current_start)
        previous_end = current_start

    return {
        "range_key": normalized_key,
        "label": RANGE_LABELS[normalized_key],
        "current_start": current_start,
        "current_end": current_end,
        "previous_start": previous_start,
        "previous_end": previous_end,
    }


def _apply_range(query, column, start: datetime | None, end: datetime | None):
    """对查询按时间列追加起止区间过滤条件。"""
    if start is not None:
        query = query.filter(column >= start)
    if end is not None:
        query = query.filter(column < end)
    return query


def _period_metrics(
    db: Session,
    photographer_id: int,
    start: datetime | None,
    end: datetime | None,
) -> dict:
    """统计某时间区间内的订单量与完成率等核心指标。"""
    order_query = db.query(Order).filter(
        Order.photographer_id == photographer_id,
        Order.status != OrderStatus.CANCELLED,
    )
    order_query = _apply_range(order_query, Order.created_at, start, end)
    period_orders = order_query.count()
    completed_orders = order_query.filter(Order.status.in_(COMPLETED_STATUSES)).count()
    completion_rate = round(completed_orders / period_orders * 100, 1) if period_orders else 0.0
    avg_rating_result = order_query.filter(Order.rating.isnot(None)).with_entities(
        func.avg(Order.rating)
    ).scalar()
    avg_rating = round((avg_rating_result or 0) / 2, 1)
    rating_count = order_query.filter(Order.rating.isnot(None)).count()

    shoot_query = db.query(Order).filter(
        Order.photographer_id == photographer_id,
        Order.status.in_(ACTIVE_SCHEDULE_STATUSES),
    )
    shoot_query = _apply_range(shoot_query, Order.appointment_time, start, end)
    confirmed_shoots = shoot_query.count()

    return {
        "period_orders": period_orders,
        "confirmed_shoots": confirmed_shoots,
        "completion_rate": completion_rate,
        "avg_rating": avg_rating,
        "rating_count": rating_count,
    }


def _build_trends(current: dict, previous: dict | None, has_comparison: bool) -> dict:
    """对比当前与上一周期指标并生成趋势变化结果。"""
    if not previous or not has_comparison:
        return {
            "has_comparison": False,
            "period_orders_delta": None,
            "confirmed_shoots_delta": None,
            "completion_rate_delta": None,
            "avg_rating_delta": None,
        }

    return {
        "has_comparison": True,
        "period_orders_delta": current["period_orders"] - previous["period_orders"],
        "confirmed_shoots_delta": current["confirmed_shoots"] - previous["confirmed_shoots"],
        "completion_rate_delta": round(current["completion_rate"] - previous["completion_rate"], 1),
        "avg_rating_delta": round(current["avg_rating"] - previous["avg_rating"], 1),
    }


def _serialize_order_item(order: Order) -> dict:
    """序列化订单为仪表盘日程项字典。"""
    customer = order.customer
    active_reschedule = order.active_reschedule_request
    return {
        "id": order.id,
        "package_snapshot": order.package_snapshot,
        "appointment_time": order.appointment_time,
        "duration_minutes": order.duration_minutes,
        "status": _status_value(order.status),
        "customer_id": order.customer_id,
        "customer_name": customer.display_name if customer else None,
        "customer_avatar_url": customer.avatar_url if customer else None,
        "reschedule_requested_time": order.reschedule_requested_time,
        "active_reschedule_request": {
            "id": active_reschedule.id,
            "requested_by": active_reschedule.requested_by,
            "requested_appointment_time": active_reschedule.requested_appointment_time,
            "reason": active_reschedule.reason,
            "status": _status_value(active_reschedule.status),
            "expires_at": active_reschedule.expires_at,
        } if active_reschedule else None,
    }


def _parse_json_datetime(value) -> datetime | None:
    """解析 JSON 中的时间字段为无时区 datetime，失败返回 None。"""
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    if not value:
        return None
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _json_item_id(item: dict) -> str:
    """提取作品或套餐条目中的 ID 字符串。"""
    return str(item.get("id") or "").strip()


def _split_tags(value: str) -> list[str]:
    """按常见分隔符拆分标签字符串为列表。"""
    return [
        tag.strip()
        for tag in (value or "").replace("，", ",").replace("、", ",").replace("\n", ",").split(",")
        if tag.strip()
    ]


def _normalize_tags(value, fallback: str = "") -> list[str]:
    """将标签字段统一规范化为字符串列表。"""
    if isinstance(value, list):
        return [str(tag).strip() for tag in value if str(tag).strip()]
    if isinstance(value, str):
        return _split_tags(value)
    return _split_tags(fallback)


def _to_float_or_none(value) -> float | None:
    """安全地将值转为浮点数，无效时返回 None。"""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int_or_none(value) -> int | None:
    """安全地将值转为整数，无效时返回 None。"""
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _count_likes(db: Session, target_type: str, ids: list[str]) -> dict[str, int]:
    """批量统计各目标对象的点赞数。"""
    if not ids:
        return {}
    rows = (
        db.query(Like.target_id, func.count(Like.id).label("count"))
        .filter(Like.target_type == target_type, Like.target_id.in_(ids))
        .group_by(Like.target_id)
        .all()
    )
    counts = {target_id: int(count) for target_id, count in rows}
    return {target_id: counts.get(target_id, 0) for target_id in ids}


def _count_work_favorites(db: Session, photographer_id: int, ids: list[str]) -> dict[str, int]:
    """批量统计各作品的收藏数。"""
    if not ids:
        return {}
    rows = (
        db.query(Favorite.work_id, func.count(Favorite.id).label("count"))
        .filter(
            Favorite.favorite_type == "work",
            Favorite.photographer_id == photographer_id,
            Favorite.work_id.in_(ids),
        )
        .group_by(Favorite.work_id)
        .all()
    )
    counts = {work_id: int(count) for work_id, count in rows}
    return {work_id: counts.get(work_id, 0) for work_id in ids}


def _count_package_favorites(db: Session, photographer_id: int, ids: list[str]) -> dict[str, int]:
    """批量统计各套餐的收藏数。"""
    if not ids:
        return {}
    rows = (
        db.query(Favorite.package_id, func.count(Favorite.id).label("count"))
        .filter(
            Favorite.favorite_type == "package",
            Favorite.photographer_id == photographer_id,
            Favorite.package_id.in_(ids),
        )
        .group_by(Favorite.package_id)
        .all()
    )
    counts = {package_id: int(count) for package_id, count in rows}
    return {package_id: counts.get(package_id, 0) for package_id in ids}


def _has_package_samples(pkg: dict) -> bool:
    """判断套餐条目是否包含示例作品。"""
    samples = pkg.get("samples") or []
    if isinstance(samples, str):
        return bool(samples.strip())
    if not isinstance(samples, list):
        return False
    return any(bool(str(sample or "").strip()) for sample in samples)


def _first_package_sample(pkg: dict) -> str:
    """返回套餐的第一张示例图或示例作品链接。"""
    thumbnails = pkg.get("sample_thumbnails") or []
    if isinstance(thumbnails, list):
        for thumbnail in thumbnails:
            if thumbnail:
                return str(thumbnail)
    samples = pkg.get("samples") or []
    if isinstance(samples, list):
        for sample in samples:
            if sample:
                return str(sample)
    if isinstance(samples, str):
        return samples
    return ""


def _build_content_insights(db: Session, photographer_id: int, now: datetime) -> dict:
    """聚合摄影师的作品与套餐内容及其互动数据。"""
    profile = (
        db.query(PhotographerProfile)
        .filter(PhotographerProfile.user_id == photographer_id)
        .first()
    )
    portfolio = [item for item in (profile.portfolio or []) if isinstance(item, dict)] if profile else []
    packages = [item for item in (profile.packages or []) if isinstance(item, dict)] if profile else []

    recent_start = now - timedelta(days=30)
    recent_upload_count = 0
    for work in portfolio:
        uploaded_at = _parse_json_datetime(work.get("created_at") or work.get("uploaded_at"))
        if uploaded_at and uploaded_at >= recent_start:
            recent_upload_count += 1

    work_ids = [_json_item_id(work) for work in portfolio if _json_item_id(work)]
    package_ids = [_json_item_id(pkg) for pkg in packages if _json_item_id(pkg)]
    work_like_counts = _count_likes(db, "portfolio", work_ids)
    work_favorite_counts = _count_work_favorites(db, photographer_id, work_ids)
    package_favorite_counts = _count_package_favorites(db, photographer_id, package_ids)

    top_works = []
    for work in portfolio:
        work_id = _json_item_id(work)
        if not work_id:
            continue
        like_count = work_like_counts.get(work_id, 0)
        favorite_count = work_favorite_counts.get(work_id, 0)
        total_interactions = like_count + favorite_count
        if total_interactions <= 0:
            continue
        media_type = work.get("media_type") or "image"
        top_works.append({
            "id": work_id,
            "title": work.get("title") or work.get("tag") or "未命名作品",
            "url": work.get("url") or "",
            "thumbnail_url": work.get("thumbnail_url") or ("" if media_type == "video" else work.get("url") or ""),
            "media_type": media_type,
            "tags": _normalize_tags(work.get("tags"), work.get("tag", "")),
            "like_count": like_count,
            "favorite_count": favorite_count,
            "total_interactions": total_interactions,
        })
    top_works.sort(
        key=lambda item: (
            item["total_interactions"],
            item["like_count"],
            item["favorite_count"],
            item["title"],
        ),
        reverse=True,
    )

    top_packages = []
    for pkg in packages:
        package_id = _json_item_id(pkg)
        if not package_id:
            continue
        favorite_count = package_favorite_counts.get(package_id, 0)
        if favorite_count <= 0:
            continue
        top_packages.append({
            "id": package_id,
            "name": pkg.get("name") or "未命名套餐",
            "price": _to_float_or_none(pkg.get("price")),
            "duration": _to_int_or_none(pkg.get("duration")),
            "sample_url": _first_package_sample(pkg),
            "favorite_count": favorite_count,
            "booking_count": None,
            "booking_count_available": False,
        })
    top_packages.sort(key=lambda item: (item["favorite_count"], item["name"]), reverse=True)

    return {
        "content": {
            "portfolio_count": len(portfolio),
            "package_count": len(packages),
            "packages_with_samples": sum(1 for pkg in packages if _has_package_samples(pkg)),
            "recent_upload_count": recent_upload_count,
        },
        "top_works": top_works[:3],
        "top_packages": top_packages[:3],
        "work_ids": work_ids,
        "package_ids": package_ids,
    }


def _count_analytics_events(
    db: Session,
    photographer_id: int,
    event_types: list[str],
    start: datetime | None,
    end: datetime | None,
    target_type: str | None = None,
) -> int:
    """统计指定类型埋点事件在区间内的数量。"""
    query = db.query(AnalyticsEvent).filter(
        AnalyticsEvent.user_id == photographer_id,
        AnalyticsEvent.event_type.in_(event_types),
    )
    if target_type:
        query = query.filter(AnalyticsEvent.target_type == target_type)
    query = _apply_range(query, AnalyticsEvent.created_at, start, end)
    return query.count()


def _count_likes_in_range(
    db: Session,
    target_type: str,
    target_ids: list[str],
    start: datetime | None,
    end: datetime | None,
) -> int:
    """统计区间内各目标对象的点赞总数。"""
    if not target_ids:
        return 0
    query = db.query(Like).filter(
        Like.target_type == target_type,
        Like.target_id.in_(target_ids),
    )
    query = _apply_range(query, Like.created_at, start, end)
    return query.count()


def _count_favorites_in_range(
    db: Session,
    photographer_id: int,
    favorite_type: str,
    ids: list[str],
    start: datetime | None,
    end: datetime | None,
) -> int:
    """统计区间内作品或套餐的收藏总数。"""
    if not ids:
        return 0
    id_column = Favorite.work_id if favorite_type == "work" else Favorite.package_id
    query = db.query(Favorite).filter(
        Favorite.photographer_id == photographer_id,
        Favorite.favorite_type == favorite_type,
        id_column.in_(ids),
    )
    query = _apply_range(query, Favorite.created_at, start, end)
    return query.count()


def _count_message_conversations(
    db: Session,
    photographer_id: int,
    start: datetime | None,
    end: datetime | None,
) -> int:
    """统计区间内与摄影师私信往来过的用户数。"""
    query = db.query(Message.sender_id, Message.receiver_id).filter(
        or_(
            Message.sender_id == photographer_id,
            Message.receiver_id == photographer_id,
        )
    )
    query = _apply_range(query, Message.created_at, start, end)
    counterpart_ids = set()
    for sender_id, receiver_id in query.all():
        if sender_id == photographer_id:
            counterpart_ids.add(receiver_id)
        else:
            counterpart_ids.add(sender_id)
    return len(counterpart_ids)


def _funnel_node(key: str, label: str, count: int, previous_count: int | None, source: str) -> dict:
    """构造转化漏斗中的一个节点数据。"""
    conversion_rate = None
    if previous_count and previous_count > 0:
        conversion_rate = round(count / previous_count * 100, 1)
    return {
        "key": key,
        "label": label,
        "count": count,
        "conversion_rate": conversion_rate,
        "source": source,
    }


def _build_interactions_and_funnel(
    db: Session,
    photographer_id: int,
    start: datetime | None,
    end: datetime | None,
    work_ids: list[str],
    package_ids: list[str],
) -> dict:
    """汇总互动指标并构建从访问到成交的转化漏斗。"""
    profile_views = _count_analytics_events(
        db,
        photographer_id,
        ["profile_view", "profile_exposure"],
        start,
        end,
        "photographer",
    )
    portfolio_views = _count_analytics_events(
        db,
        photographer_id,
        ["portfolio_view", "portfolio_exposure"],
        start,
        end,
        "portfolio",
    )
    package_views = _count_analytics_events(
        db,
        photographer_id,
        ["package_view", "package_detail_click", "package_exposure"],
        start,
        end,
        "package",
    )
    tracked_event_count = _count_analytics_events(
        db,
        photographer_id,
        [
            "profile_view",
            "profile_exposure",
            "portfolio_view",
            "portfolio_exposure",
            "package_view",
            "package_detail_click",
            "package_exposure",
            "booking_started",
        ],
        start,
        end,
    )

    follower_query = db.query(Follow).filter(Follow.following_id == photographer_id)
    follower_query = _apply_range(follower_query, Follow.created_at, start, end)
    new_followers = follower_query.count()

    work_likes = _count_likes_in_range(db, "portfolio", work_ids, start, end)
    work_favorites = _count_favorites_in_range(db, photographer_id, "work", work_ids, start, end)
    package_favorites = _count_favorites_in_range(
        db,
        photographer_id,
        "package",
        package_ids,
        start,
        end,
    )
    message_conversations = _count_message_conversations(db, photographer_id, start, end)

    order_query = db.query(Order).filter(
        Order.photographer_id == photographer_id,
        Order.status != OrderStatus.CANCELLED,
    )
    order_query = _apply_range(order_query, Order.created_at, start, end)
    created_orders = order_query.count()
    completed_orders = order_query.filter(Order.status.in_(COMPLETED_STATUSES)).count()
    work_interactions = work_likes + work_favorites

    nodes = [
        _funnel_node("profile_views", "主页访问", profile_views, None, "analytics_events.profile_view"),
        _funnel_node("work_interactions", "作品互动", work_interactions, profile_views, "likes + work favorites"),
        _funnel_node("package_favorites", "套餐收藏", package_favorites, work_interactions, "package favorites"),
        _funnel_node("message_conversations", "私信咨询", message_conversations, package_favorites, "messages"),
        _funnel_node("created_orders", "创建预约", created_orders, message_conversations, "orders.created_at"),
        _funnel_node("completed_orders", "完成订单", completed_orders, created_orders, "orders.status"),
    ]

    return {
        "interactions": {
            "new_followers": new_followers,
            "message_conversations": message_conversations,
            "work_likes": work_likes,
            "work_favorites": work_favorites,
            "package_favorites": package_favorites,
            "profile_views": profile_views,
            "portfolio_views": portfolio_views,
            "package_views": package_views,
        },
        "funnel": {
            "nodes": nodes,
            "tracked_event_count": tracked_event_count,
        },
    }


def _application_status_value(status: ProjectApplicationStatus | str) -> str:
    """返回应邀状态枚举或字符串形式的状态值。"""
    return status.value if isinstance(status, ProjectApplicationStatus) else str(status)


def _quote_matches_budget(quote: int | None, budget_min: int | None, budget_max: int | None) -> bool | None:
    """判断报价是否落在企划预算区间内，无法判断时返回 None。"""
    if quote is None or (budget_min is None and budget_max is None):
        return None
    if budget_min is not None and quote < budget_min:
        return False
    if budget_max is not None and quote > budget_max:
        return False
    return True


def _build_project_performance(
    db: Session,
    photographer_id: int,
    start: datetime | None,
    end: datetime | None,
) -> dict:
    """统计摄影师在区间内的企划应邀表现。"""
    query = (
        db.query(ProjectApplication)
        .options(joinedload(ProjectApplication.project))
        .filter(
            ProjectApplication.photographer_id == photographer_id,
            ProjectApplication.status != ProjectApplicationStatus.WITHDRAWN,
        )
    )
    query = _apply_range(query, ProjectApplication.created_at, start, end)
    applications = query.all()
    submitted_applications = len(applications)
    selected_applications = sum(
        1
        for application in applications
        if _application_status_value(application.status) == ProjectApplicationStatus.SELECTED.value
    )
    converted_orders = sum(
        1
        for application in applications
        if application.project
        and application.project.selected_application_id == application.id
        and application.project.converted_order_id is not None
    )
    average_quote = None
    if submitted_applications:
        average_quote = round(
            sum(application.price_quote for application in applications) / submitted_applications,
            1,
        )

    budget_match_sample_count = 0
    budget_match_count = 0
    for application in applications:
        project = application.project
        match = _quote_matches_budget(
            application.price_quote,
            project.budget_min if project else None,
            project.budget_max if project else None,
        )
        if match is None:
            continue
        budget_match_sample_count += 1
        if match:
            budget_match_count += 1

    application_conversion_rate = (
        round(selected_applications / submitted_applications * 100, 1)
        if submitted_applications
        else None
    )
    budget_match_rate = (
        round(budget_match_count / budget_match_sample_count * 100, 1)
        if budget_match_sample_count
        else None
    )

    return {
        "submitted_applications": submitted_applications,
        "selected_applications": selected_applications,
        "converted_orders": converted_orders,
        "application_conversion_rate": application_conversion_rate,
        "average_quote": average_quote,
        "budget_match_rate": budget_match_rate,
        "budget_match_sample_count": budget_match_sample_count,
    }


def _build_public_trust(db: Session, photographer_id: int, now: datetime) -> dict:
    """构建可公开展示的摄影师信任指标。"""
    base_query = db.query(Order).filter(
        Order.photographer_id == photographer_id,
        Order.status != OrderStatus.CANCELLED,
    )
    total_orders = base_query.count()
    completed_orders = base_query.filter(Order.status.in_(COMPLETED_STATUSES)).count()

    rating_query = base_query.filter(Order.rating.isnot(None))
    rating_count = rating_query.count()
    avg_rating_result = rating_query.with_entities(func.avg(Order.rating)).scalar()
    avg_rating = round(avg_rating_result / 2, 1) if avg_rating_result is not None else None

    completion_rate_visible = total_orders >= PUBLIC_COMPLETION_MIN_ORDERS
    completion_rate = (
        round(completed_orders / total_orders * 100, 1)
        if completion_rate_visible and total_orders
        else None
    )

    recent_start = now - timedelta(days=90)
    recent_order_activity = base_query.filter(Order.created_at >= recent_start).count() > 0

    return {
        "completed_orders": completed_orders,
        "avg_rating": avg_rating,
        "rating_count": rating_count,
        "rating_visible": rating_count > 0,
        "completion_rate": completion_rate,
        "completion_rate_visible": completion_rate_visible,
        "completion_sample_count": total_orders if completion_rate_visible else 0,
        "recent_order_activity": recent_order_activity,
    }


def get_public_photographer_dashboard(db: Session, photographer_id: int) -> dict:
    """获取可公开展示的摄影师信任与内容指标。"""

    now = _utc_now_naive()
    content_insights = _build_content_insights(db, photographer_id, now)
    return {
        "trust": _build_public_trust(db, photographer_id, now),
        "content": content_insights["content"],
        "top_works": content_insights["top_works"],
        "top_packages": content_insights["top_packages"],
    }


def get_photographer_dashboard(db: Session, photographer_id: int, range_key: str = "month") -> dict:
    """获取摄影师工作台数据。"""

    now = _utc_now_naive()
    period = _get_period(range_key, now)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_start = today_start + timedelta(days=1)
    week_start = today_start - timedelta(days=today_start.weekday())
    week_end = week_start + timedelta(days=7)
    current_metrics = _period_metrics(
        db,
        photographer_id,
        period["current_start"],
        period["current_end"],
    )
    previous_metrics = None
    if period["previous_start"] is not None and period["previous_end"] is not None:
        previous_metrics = _period_metrics(
            db,
            photographer_id,
            period["previous_start"],
            period["previous_end"],
        )
    has_comparison = bool(
        previous_metrics and (
            previous_metrics["period_orders"] > 0 or previous_metrics["confirmed_shoots"] > 0
        )
    )
    legacy_stats = get_photographer_stats(db, photographer_id)
    content_insights = _build_content_insights(db, photographer_id, now)
    conversion_insights = _build_interactions_and_funnel(
        db,
        photographer_id,
        period["current_start"],
        period["current_end"],
        content_insights["work_ids"],
        content_insights["package_ids"],
    )
    project_performance = _build_project_performance(
        db,
        photographer_id,
        period["current_start"],
        period["current_end"],
    )

    base_query = db.query(Order).filter(Order.photographer_id == photographer_id)

    pending_orders = base_query.filter(Order.status == OrderStatus.PENDING).count()
    reschedule_requests = (
        db.query(func.count(OrderRescheduleRequest.id))
        .join(Order, Order.id == OrderRescheduleRequest.order_id)
        .filter(
            Order.photographer_id == photographer_id,
            OrderRescheduleRequest.requested_by != photographer_id,
            OrderRescheduleRequest.status == OrderRescheduleStatus.PENDING,
            OrderRescheduleRequest.expires_at > now,
        )
        .scalar()
        or 0
    )
    reschedule_requests += base_query.filter(
        Order.status == OrderStatus.RESCHEDULE_REQUESTED
    ).count()
    orders_to_deliver = base_query.filter(
        Order.status.in_([OrderStatus.CONFIRMED, OrderStatus.IN_PROGRESS])
    ).count()
    orders_waiting_review = base_query.filter(
        Order.status.in_([OrderStatus.COMPLETED, OrderStatus.RECEIVED]),
        Order.rating.is_(None),
    ).count()

    today_orders = base_query.filter(
        Order.status.in_(ACTIVE_SCHEDULE_STATUSES),
        Order.appointment_time >= today_start,
        Order.appointment_time < tomorrow_start,
    ).count()
    week_confirmed_orders = base_query.filter(
        Order.status.in_(ACTIVE_SCHEDULE_STATUSES),
        Order.appointment_time >= week_start,
        Order.appointment_time < week_end,
    ).count()

    next_order = (
        base_query.options(joinedload(Order.customer))
        .filter(
            Order.status.in_(ACTIVE_SCHEDULE_STATUSES),
            Order.appointment_time >= now,
        )
        .order_by(Order.appointment_time.asc(), Order.id.asc())
        .first()
    )
    upcoming_orders = (
        base_query.options(joinedload(Order.customer))
        .filter(
            Order.status.in_(UPCOMING_ORDER_STATUSES),
            Order.appointment_time >= now,
        )
        .order_by(Order.appointment_time.asc(), Order.id.asc())
        .limit(3)
        .all()
    )

    return {
        "period": {
            **period,
            "has_comparison": has_comparison,
        },
        "summary": {
            "monthly_orders": legacy_stats["monthly_orders"],
            "weekly_orders": legacy_stats["weekly_orders"],
            "period_orders": current_metrics["period_orders"],
            "confirmed_shoots": current_metrics["confirmed_shoots"],
            "completion_rate": current_metrics["completion_rate"],
            "avg_rating": current_metrics["avg_rating"],
        },
        "trends": _build_trends(current_metrics, previous_metrics, has_comparison),
        "revenue": {
            "available": False,
            "reason": "订单尚未记录结构化金额字段，暂不展示收入统计。",
            "month_estimated": None,
            "completed": None,
            "pending": None,
            "average_order_value": None,
        },
        "content": content_insights["content"],
        "top_works": content_insights["top_works"],
        "top_packages": content_insights["top_packages"],
        "todo": {
            "pending_orders": pending_orders,
            "reschedule_requests": reschedule_requests,
            "orders_to_deliver": orders_to_deliver,
            "orders_waiting_review": orders_waiting_review,
        },
        "schedule": {
            "today_orders": today_orders,
            "week_confirmed_orders": week_confirmed_orders,
            "next_order": _serialize_order_item(next_order) if next_order else None,
            "upcoming_orders": [_serialize_order_item(order) for order in upcoming_orders],
        },
        "interactions": conversion_insights["interactions"],
        "funnel": conversion_insights["funnel"],
        "project_performance": project_performance,
    }
