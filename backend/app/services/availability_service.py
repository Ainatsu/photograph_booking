"""摄影师可预约档期的计算与时间工具服务。"""

import re
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


DAY_NAMES_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
DAY_NAMES_EN = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

DAY_ALIASES = {
    "monday": 0,
    "mon": 0,
    "周一": 0,
    "星期一": 0,
    "tuesday": 1,
    "tue": 1,
    "周二": 1,
    "星期二": 1,
    "wednesday": 2,
    "wed": 2,
    "周三": 2,
    "星期三": 2,
    "thursday": 3,
    "thu": 3,
    "周四": 3,
    "星期四": 3,
    "friday": 4,
    "fri": 4,
    "周五": 4,
    "星期五": 4,
    "saturday": 5,
    "sat": 5,
    "周六": 5,
    "星期六": 5,
    "sunday": 6,
    "sun": 6,
    "周日": 6,
    "周天": 6,
    "星期日": 6,
    "星期天": 6,
}

VALID_DAY_STATUSES = {"free", "busy"}
STATUS_ALIASES = {
    "free": "free",
    "available": "free",
    "空闲": "free",
    "busy": "busy",
    "closed": "busy",
    "unavailable": "busy",
    "忙碌": "busy",
    "unknown": "free",
    "未知": "free",
}

DEFAULT_DAY_START_MINUTES = 9 * 60
DEFAULT_DAY_END_MINUTES = 18 * 60
MAX_AVAILABILITY_DAYS = 365


def platform_timezone():
    """返回平台配置的时区对象，配置无效时回退到东八区。"""
    from backend.app.core.config import settings

    try:
        return ZoneInfo(settings.PLATFORM_TIMEZONE)
    except ZoneInfoNotFoundError:
        return timezone(timedelta(hours=8), name=settings.PLATFORM_TIMEZONE)


def platform_today() -> date:
    """返回平台时区下的今天日期。"""
    return datetime.now(platform_timezone()).date()


def weekday_name_cn(d: date) -> str:
    """返回日期对应的中文星期名称。"""
    return DAY_NAMES_CN[d.weekday()]


def day_name_en(d: date) -> str:
    """返回日期对应的英文星期名称。"""
    return DAY_NAMES_EN[d.weekday()]


def parse_time_range(range_str: str) -> tuple[int, int] | None:
    """解析 "HH:MM-HH:MM" 格式的时间段为起止分钟数。"""
    if not isinstance(range_str, str):
        return None
    match = re.match(r"^\s*(\d{1,2}):(\d{2})\s*[-–—]\s*(\d{1,2}):(\d{2})\s*$", range_str)
    if not match:
        return None

    start_hour = int(match.group(1))
    start_minute = int(match.group(2))
    end_hour = int(match.group(3))
    end_minute = int(match.group(4))

    if not (0 <= start_hour <= 23 and 0 <= start_minute <= 59):
        return None
    if end_hour == 24:
        if end_minute != 0:
            return None
    elif not (0 <= end_hour <= 23 and 0 <= end_minute <= 59):
        return None

    start_minutes = start_hour * 60 + start_minute
    end_minutes = end_hour * 60 + end_minute
    if start_minutes >= end_minutes:
        return None
    return start_minutes, end_minutes


def format_minutes(minutes: int) -> str:
    """将分钟数格式化为 HH:MM 字符串。"""
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def format_time_range(start_minutes: int, end_minutes: int) -> str:
    """将起止分钟数格式化为时间段字符串。"""
    return f"{format_minutes(start_minutes)}-{format_minutes(end_minutes)}"


def _normalize_intervals(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """对时间段列表排序并合并重叠区间。"""
    valid = sorted((start, end) for start, end in intervals if start < end)
    if not valid:
        return []

    merged: list[tuple[int, int]] = []
    for start, end in valid:
        if not merged or start > merged[-1][1]:
            merged.append((start, end))
        else:
            prev_start, prev_end = merged[-1]
            merged[-1] = (prev_start, max(prev_end, end))
    return merged


def slot_strings_to_intervals(slots: Any) -> list[tuple[int, int]]:
    """将时间段字符串列表解析为规范化区间列表。"""
    if not isinstance(slots, list):
        return []
    intervals = []
    for slot in slots:
        parsed = parse_time_range(slot)
        if parsed:
            intervals.append(parsed)
    return _normalize_intervals(intervals)


def normalize_day_status(value: Any) -> str:
    """将各种状态别名规范化为 free/busy。"""
    key = str(value or "free").strip().lower()
    return STATUS_ALIASES.get(key, "free")


def _parse_entry_date(value: Any) -> date | None:
    """解析例外条目中的日期字符串为 date，无效返回 None。"""
    raw_date = str(value or "").strip()
    if not raw_date:
        return None
    if "T" in raw_date:
        raw_date = raw_date.split("T", 1)[0]
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", raw_date):
        return None
    try:
        return date.fromisoformat(raw_date)
    except ValueError:
        return None


def is_date_in_availability_window(query_date: date, today: date | None = None, max_date: date | None = None) -> bool:
    """判断日期是否落在可预约的时间窗口内。"""
    base = today or date.today()
    return base <= query_date <= (max_date or base + timedelta(days=MAX_AVAILABILITY_DAYS))


def normalize_availability_entries(entries: list | None, today: date | None = None) -> list[dict]:
    """规范化例外日期条目并过滤窗口外的记录。"""
    normalized_by_date: dict[str, dict] = {}
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue

        entry_date = _parse_entry_date(entry.get("date"))
        if not entry_date or not is_date_in_availability_window(entry_date, today):
            continue

        raw_status = entry.get("status", entry.get("type", "free"))
        status = normalize_day_status(raw_status)
        location = str(entry.get("location") or "").strip()

        if status == "free" and not location:
            normalized_by_date.pop(entry_date.isoformat(), None)
            continue

        item = {"date": entry_date.isoformat(), "status": status}
        if location:
            item["location"] = location
        normalized_by_date[item["date"]] = item

    return [normalized_by_date[key] for key in sorted(normalized_by_date)]


def _entry_matches_date(entry: dict, query_date: date) -> bool:
    """判断例外条目是否命中指定日期。"""
    entry_date = _parse_entry_date(entry.get("date"))
    return entry_date == query_date


def _day_index(value: Any) -> int | None:
    """将星期名称/别名解析为星期索引，未知返回 None。"""
    if not isinstance(value, str):
        return None
    key = value.strip()
    lower_key = key.lower()
    if lower_key in DAY_ALIASES:
        return DAY_ALIASES[lower_key]
    return DAY_ALIASES.get(key)


def _entry_matches_weekday(entry: dict, query_date: date) -> bool:
    """判断周排期条目是否命中指定日期的星期。"""
    entry_day = entry.get("day")
    return _day_index(entry_day) == query_date.weekday()


def _weekly_available_intervals(profile: Any, query_date: date) -> list[tuple[int, int]]:
    """汇总摄影师周排期中当天的可预约时间段。"""
    intervals: list[tuple[int, int]] = []
    for entry in getattr(profile, "available_hours", None) or []:
        if isinstance(entry, dict) and _entry_matches_weekday(entry, query_date):
            intervals.extend(slot_strings_to_intervals(entry.get("slots") or []))
    return _normalize_intervals(intervals)


def get_day_availability(profile: Any, query_date: date) -> dict[str, str]:
    """获取指定日期的基础可约状态与地点信息。"""
    result = {
        "date": query_date.isoformat(),
        "status": "free",
        "location": "",
    }

    for entry in getattr(profile, "availability_exceptions", None) or []:
        if not isinstance(entry, dict) or not _entry_matches_date(entry, query_date):
            continue
        result["status"] = normalize_day_status(entry.get("status", entry.get("type", "free")))
        result["location"] = str(entry.get("location") or "").strip()

    return result


def get_configured_intervals(profile: Any, query_date: date) -> tuple[list[tuple[int, int]], list[tuple[int, int]], bool]:
    """返回当天可预约区间及是否全天忙碌。"""
    day = get_day_availability(profile, query_date)
    if day["status"] == "busy":
        return [], [(0, 24 * 60)], True
    return [(DEFAULT_DAY_START_MINUTES, DEFAULT_DAY_END_MINUTES)], [], False


def profile_has_positive_availability(profile: Any) -> bool:
    """判断摄影师档案是否存在可用预约能力。"""
    return profile is not None


def interval_overlaps(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    """判断两个分钟级时间段是否重叠。"""
    return a_start < b_end and a_end > b_start


def interval_contains(container: tuple[int, int], target: tuple[int, int]) -> bool:
    """判断目标时间段是否被容器时间段完整包含。"""
    return container[0] <= target[0] and target[1] <= container[1]


def is_interval_bookable_by_profile(profile: Any, appointment: datetime, duration_minutes: int) -> bool:
    """判断指定预约时间与时长在摄影师档案下是否可预约。"""
    query_date = appointment.date()
    start_minutes = appointment.hour * 60 + appointment.minute
    end_minutes = start_minutes + duration_minutes

    if end_minutes > 24 * 60:
        return False
    max_booking_date = getattr(profile, "max_booking_date", None)
    if max_booking_date and query_date > max_booking_date:
        return False

    day = get_day_availability(profile, query_date)
    if day["status"] == "busy":
        return False
    return True


def parse_date_string(date_str: str | None, today: date) -> date | None:
    """解析日期字符串为窗口内的 date，空值回退到今天。"""
    if not date_str:
        return today if is_date_in_availability_window(today, today) else None

    raw_date = date_str.strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}$", raw_date):
        try:
            query_date = date.fromisoformat(raw_date)
        except ValueError:
            return None
        return query_date if is_date_in_availability_window(query_date, today) else None

    match = re.match(r"^(\d{1,2})-(\d{1,2})$", raw_date)
    if not match:
        return None

    month, day = int(match.group(1)), int(match.group(2))
    try:
        query_date = date(today.year, month, day)
    except ValueError:
        return None
    if query_date < today:
        try:
            query_date = date(today.year + 1, month, day)
        except ValueError:
            return None
    return query_date if is_date_in_availability_window(query_date, today) else None


def list_bookable_slots(
    db,
    profile,
    start_date: date,
    days: int,
    duration_minutes: int,
    buffer_minutes: int = 30,
) -> dict:
    """按摄影师周排期、例外日期、已有订单、提前预约量和每日上限生成真实可选档期。"""
    from backend.app.models.order import Order, OrderStatus
    tz = platform_timezone()
    active_statuses = [
        OrderStatus.PENDING,
        OrderStatus.AWAITING_PAYMENT,
        OrderStatus.CONFIRMED,
        OrderStatus.IN_PROGRESS,
        OrderStatus.DELIVERED,
    ]
    range_start_local = datetime.combine(start_date, datetime.min.time(), tzinfo=tz)
    configured_max_date = getattr(profile, "max_booking_date", None)
    effective_max_date = configured_max_date or (platform_today() + timedelta(days=MAX_AVAILABILITY_DAYS))
    requested_days = max(1, min(days, MAX_AVAILABILITY_DAYS + 1))
    range_end_local = range_start_local + timedelta(days=requested_days)
    range_start_utc = range_start_local.astimezone(timezone.utc).replace(tzinfo=None)
    range_end_utc = range_end_local.astimezone(timezone.utc).replace(tzinfo=None)
    orders = db.query(Order).filter(
        Order.photographer_id == profile.user_id,
        Order.status.in_(active_statuses),
        Order.appointment_time >= range_start_utc,
        Order.appointment_time < range_end_utc,
    ).all()

    return compute_bookable_slots(profile, start_date, days, duration_minutes, orders, buffer_minutes)


def compute_bookable_slots(
    profile,
    start_date: date,
    days: int,
    duration_minutes: int,
    orders: list,
    buffer_minutes: int = 30,
    now_local: datetime | None = None,
) -> dict:
    """Pure slot calculation over an already loaded profile and order collection."""
    from backend.app.core.config import settings

    timezone_name = settings.PLATFORM_TIMEZONE
    tz = platform_timezone()
    now_local = now_local or datetime.now(tz)
    advance_notice_hours = max(0, int(getattr(profile, "advance_notice", 24) or 0))
    earliest_local = now_local + timedelta(hours=advance_notice_hours)
    max_daily = max(1, int(getattr(profile, "max_daily_bookings", 5) or 5))
    duration = max(30, int(duration_minutes))
    buffer_value = max(0, int(buffer_minutes or 0))
    result_days = []
    configured_max_date = getattr(profile, "max_booking_date", None)
    effective_max_date = configured_max_date or (platform_today() + timedelta(days=MAX_AVAILABILITY_DAYS))
    requested_days = max(1, min(days, MAX_AVAILABILITY_DAYS + 1))

    orders_by_date: dict[date, list[tuple[datetime, datetime]]] = {}
    for order in orders:
        start_utc = order.appointment_time.replace(tzinfo=timezone.utc)
        start_local = start_utc.astimezone(tz)
        end_local = start_local + timedelta(minutes=int(order.duration_minutes or 0) + buffer_value)
        orders_by_date.setdefault(start_local.date(), []).append((start_local, end_local))

    for offset in range(requested_days):
        query_date = start_date + timedelta(days=offset)
        if query_date > effective_max_date:
            break
        day = get_day_availability(profile, query_date)
        weekly_intervals = _weekly_available_intervals(profile, query_date)
        intervals = weekly_intervals or [(DEFAULT_DAY_START_MINUTES, DEFAULT_DAY_END_MINUTES)]
        occupied = orders_by_date.get(query_date, [])
        slots = []
        unavailable_reason = None
        if day["status"] == "busy":
            intervals = []
            unavailable_reason = "摄影师已标记全天不可预约"
        elif len(occupied) >= max_daily:
            intervals = []
            unavailable_reason = "当日预约数量已满"

        for interval_start, interval_end in intervals:
            cursor = interval_start
            while cursor + duration <= interval_end:
                slot_start = datetime.combine(query_date, datetime.min.time(), tzinfo=tz) + timedelta(minutes=cursor)
                slot_end = slot_start + timedelta(minutes=duration)
                blocked_end = slot_end + timedelta(minutes=buffer_value)
                # Historical dates are useful for audit/backfill queries and must
                # still expose their computed schedule; advance notice only
                # applies to today and future dates.
                notice_ok = query_date < now_local.date() or slot_start >= earliest_local
                if notice_ok and not any(
                    slot_start < occupied_end and blocked_end > occupied_start
                    for occupied_start, occupied_end in occupied
                ):
                    slots.append({
                        "start_at": slot_start.isoformat(),
                        "end_at": slot_end.isoformat(),
                        "label": f"{slot_start.strftime('%H:%M')}–{slot_end.strftime('%H:%M')}",
                    })
                cursor += 30

        result_days.append({
            "date": query_date.isoformat(),
            "weekday": weekday_name_cn(query_date),
            "location": day.get("location") or getattr(profile, "location", None),
            "slots": slots,
            "unavailable_reason": unavailable_reason if not slots else None,
        })

    return {
        "photographer_id": profile.user_id,
        "timezone": timezone_name,
        "advance_notice_hours": advance_notice_hours,
        "duration_minutes": duration,
        "buffer_minutes": buffer_value,
        "max_booking_date": effective_max_date.isoformat(),
        "days": result_days,
    }


def batch_list_bookable_slots(db, requests: list[dict], buffer_minutes: int = 30) -> dict[str, dict]:
    """Load active orders once, then compute slots for all package candidates."""
    from backend.app.models.order import Order, OrderStatus

    if not requests:
        return {}
    tz = platform_timezone()
    start_date = min(item["start_date"] for item in requests)
    end_date = max(item["start_date"] + timedelta(days=max(1, item.get("days", 1))) for item in requests)
    photographer_ids = {item["profile"].user_id for item in requests}
    range_start = datetime.combine(start_date, datetime.min.time(), tzinfo=tz).astimezone(timezone.utc).replace(tzinfo=None)
    range_end = datetime.combine(end_date, datetime.min.time(), tzinfo=tz).astimezone(timezone.utc).replace(tzinfo=None)
    active_statuses = [OrderStatus.PENDING, OrderStatus.AWAITING_PAYMENT, OrderStatus.CONFIRMED, OrderStatus.IN_PROGRESS, OrderStatus.DELIVERED]
    orders = db.query(Order).filter(
        Order.photographer_id.in_(photographer_ids),
        Order.status.in_(active_statuses),
        Order.appointment_time >= range_start,
        Order.appointment_time < range_end,
    ).all()
    orders_by_photographer: dict[int, list] = {}
    for order in orders:
        orders_by_photographer.setdefault(order.photographer_id, []).append(order)
    return {
        item["key"]: compute_bookable_slots(
            item["profile"], item["start_date"], item.get("days", 1), item["duration_minutes"],
            orders_by_photographer.get(item["profile"].user_id, []), buffer_minutes,
        )
        for item in requests
    }
