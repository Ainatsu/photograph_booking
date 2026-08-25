"""
Booking Agent — 预约方案自动化

实现预约流程的状态机管理：
  SEARCHING_PACKAGE -> SELECTING_PACKAGE -> SELECTING_TIME -> CONFIRMING_BOOKING -> CREATING_BOOKING -> BOOKING_CREATED

职责：
  - 从上下文检索结果中确定摄影师和套餐
  - 查询可预约时间段
  - 生成确认文案
  - 用户确认后调用 create_booking 工具
"""

import re
from datetime import datetime, date, timedelta, timezone
from enum import Enum
from typing import Any

from sqlalchemy.orm import Session

from backend.app.models.ai_conversation import AIMessage
from backend.app.models.order import Order, OrderStatus
from backend.app.models.order_reschedule import OrderRescheduleRequest, OrderRescheduleStatus
from backend.app.models.photographer import PhotographerProfile
from backend.app.models.user import User
from backend.app.services.ai_planner_service import advance_booking_plan
from backend.app.services.availability_service import (
    DEFAULT_DAY_END_MINUTES,
    DEFAULT_DAY_START_MINUTES,
    day_name_en as _availability_day_name_en,
    format_minutes as _availability_format_minutes,
    get_day_availability,
    parse_date_string,
    parse_time_range as _availability_parse_time_range,
    weekday_name_cn as _availability_weekday_name_cn,
)
from backend.app.services.photographer_service import get_profile_by_user_id
from backend.app.services.agent_task_service import get_active_task


class BookingState(str, Enum):
    """预约流程的状态机状态。"""

    SEARCHING_PACKAGE = "searching_package"
    SELECTING_PACKAGE = "selecting_package"
    SELECTING_TIME = "selecting_time"
    CONFIRMING_BOOKING = "confirming_booking"
    CREATING_BOOKING = "creating_booking"
    BOOKING_CREATED = "booking_created"


DEFAULT_BOOKING_TIME = "12:00"

_UNICODE_CN_DIGITS = {
    "\u96f6": 0, "\u3007": 0, "\u4e00": 1, "\u4e8c": 2, "\u4e24": 2,
    "\u4e09": 3, "\u56db": 4, "\u4e94": 5, "\u516d": 6, "\u4e03": 7,
    "\u516b": 8, "\u4e5d": 9,
}


def _parse_unicode_chinese_number(value: str) -> int | None:
    if not value:
        return None
    if value.isdigit():
        return int(value)
    if value == "\u5341":
        return 10
    if value.startswith("\u5341"):
        return 10 + (_UNICODE_CN_DIGITS.get(value[1:]) or 0)
    if value.endswith("\u5341"):
        return (_UNICODE_CN_DIGITS.get(value[:-1]) or 0) * 10
    if "\u5341" in value:
        left, right = value.split("\u5341", 1)
        return (_UNICODE_CN_DIGITS.get(left) or 0) * 10 + (_UNICODE_CN_DIGITS.get(right) or 0)
    return _UNICODE_CN_DIGITS.get(value)


def _attach_booking_plan(
    result: dict[str, Any],
    task_state: dict[str, Any] | None,
    *,
    status: str,
    completed_step_ids: tuple[str, ...] = (),
    current_step_id: str | None = None,
    failed_step_id: str | None = None,
) -> dict[str, Any]:
    """把预约计划进度挂载到结果元数据上。"""
    plan = advance_booking_plan(
        task_state,
        status=status,
        completed_step_ids=completed_step_ids,
        current_step_id=current_step_id,
        failed_step_id=failed_step_id,
    )
    if not plan:
        return result

    metadata = result.setdefault("metadata", {})
    metadata["task_plan"] = plan
    next_task_state = metadata.get("task_state") or {}
    next_task_state["task_plan"] = plan
    metadata["task_state"] = next_task_state
    return result


def _now() -> datetime:
    """返回当前 UTC 时间。"""
    return datetime.now(timezone.utc)


def _today() -> date:
    """返回今天的日期。"""
    return _now().date()


def build_booking_appointment_datetime(
    appointment_date: str,
    appointment_time: str | None = None,
) -> datetime:
    """Convert booking date/time slots into the naive UTC datetime used by orders."""
    date_match = re.match(r"^(\d{2})-(\d{2})$", appointment_date or "")
    if not date_match:
        raise ValueError("日期格式无效")

    time_value = appointment_time or DEFAULT_BOOKING_TIME
    time_match = re.match(r"^(\d{1,2}):(\d{2})$", time_value)
    if not time_match:
        raise ValueError("时间格式无效")

    month, day = int(date_match.group(1)), int(date_match.group(2))
    hour, minute = int(time_match.group(1)), int(time_match.group(2))
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    appointment_dt = datetime(now.year, month, day, hour, minute, 0)
    if appointment_dt < now:
        appointment_dt = datetime(now.year + 1, month, day, hour, minute, 0)
    return appointment_dt


def _weekday_name_cn(d: date) -> str:
    """返回中文星期几，如 '周一', '周二'"""
    return _availability_weekday_name_cn(d)


def _day_name_en(d: date) -> str:
    """返回英文星期几"""
    return _availability_day_name_en(d)


def _parse_time_range(range_str: str) -> tuple[int, int] | None:
    """解析 '09:00-12:00' 为 (9*60, 12*60) 分钟数"""
    return _availability_parse_time_range(range_str)


def _format_minutes(minutes: int) -> str:
    """将分钟数转为 '14:00' 格式"""
    return _availability_format_minutes(minutes)


# --- 可预约时间段查询 ---

def get_available_slots(
    db: Session,
    *,
    photographer_id: int,
    package_duration: int = 120,
    date_str: str | None = None,
) -> dict[str, Any]:
    """
    查询摄影师在某日（或最近可预约日）的可用时间段。

    返回:
    {
        "photographer_id": int,
        "photographer_name": str | None,
        "date": str,          # "MM-DD"
        "date_label": str,    # "6月30日 (周二)"
        "slots": [            # 每个可用时间段
            {"start": "09:00", "end": "12:00", "duration_minutes": 180},
            ...
        ],
        "package_duration": int,
        "total_available": int,
    }
    """
    # 1. 获取摄影师信息
    photographer = db.query(User).filter(
        User.id == photographer_id,
        User.role == "photographer",
    ).first()
    if not photographer:
        return {
            "photographer_id": photographer_id,
            "error": "photographer_not_found",
            "slots": [],
            "total_available": 0,
        }

    profile = db.query(PhotographerProfile).filter(
        PhotographerProfile.user_id == photographer_id
    ).first()
    if not profile:
        return {
            "photographer_id": photographer_id,
            "photographer_name": photographer.display_name,
            "error": "profile_not_found",
            "slots": [],
            "total_available": 0,
        }

    # 2. 确定查询日期
    query_date = parse_date_string(date_str, _today())
    if query_date is None:
        return {
            "photographer_id": photographer_id,
            "photographer_name": photographer.display_name,
            "error": "invalid_date_format",
            "slots": [],
            "total_available": 0,
        }

    # 3. 按天读取档期状态。未标记的日期默认为空闲。
    day_availability = get_day_availability(profile, query_date)
    day_status = day_availability["status"]
    location = day_availability.get("location") or ""

    if day_status == "busy":
        return {
            "photographer_id": photographer_id,
            "photographer_name": photographer.display_name,
            "date": query_date.strftime("%m-%d"),
            "date_label": f"{query_date.month}月{query_date.day}日 ({_weekday_name_cn(query_date)})",
            "location": location,
            "slots": [],
            "total_available": 0,
            "info": "该日档期忙碌",
        }

    # 4. 计算可用分钟段。每日状态不再精确到小时，因此使用平台默认展示时段。
    raw_slots: list[dict[str, Any]] = [
        {
            "start_minutes": DEFAULT_DAY_START_MINUTES,
            "end_minutes": DEFAULT_DAY_END_MINUTES,
        }
    ]

    if not raw_slots:
        return {
            "photographer_id": photographer_id,
            "photographer_name": photographer.display_name,
            "date": query_date.strftime("%m-%d"),
            "date_label": f"{query_date.month}月{query_date.day}日 ({_weekday_name_cn(query_date)})",
            "slots": [],
            "total_available": 0,
            "info": "可用时段格式无法解析",
        }

    # 5. 获取当天已有订单（已确认/进行中），排除冲突
    query_start = datetime.combine(query_date, datetime.min.time())
    query_end = query_start + timedelta(days=1)

    existing_orders = (
        db.query(Order)
        .filter(
            Order.photographer_id == photographer_id,
            Order.appointment_time >= query_start,
            Order.appointment_time < query_end,
            Order.status.in_([
                OrderStatus.PENDING,
                OrderStatus.CONFIRMED,
                OrderStatus.IN_PROGRESS,
            ])
        )
        .all()
    )

    # 将已有订单转为占用分钟段
    busy_intervals: list[tuple[int, int]] = []
    for order in existing_orders:
        order_start = order.appointment_time
        start_min = order_start.hour * 60 + order_start.minute
        end_min = start_min + order.duration_minutes
        busy_intervals.append((start_min, end_min))

    pending_reschedules = (
        db.query(OrderRescheduleRequest)
        .join(Order, Order.id == OrderRescheduleRequest.order_id)
        .filter(
            Order.photographer_id == photographer_id,
            OrderRescheduleRequest.requested_appointment_time >= query_start,
            OrderRescheduleRequest.requested_appointment_time < query_end,
            OrderRescheduleRequest.status == OrderRescheduleStatus.PENDING,
            OrderRescheduleRequest.expires_at > datetime.now(timezone.utc).replace(tzinfo=None),
        )
        .all()
    )
    for request in pending_reschedules:
        request_start = request.requested_appointment_time
        start_min = request_start.hour * 60 + request_start.minute
        busy_intervals.append((start_min, start_min + request.order.duration_minutes))

    # 6. 从每个 raw_slot 中切割出未被占用的子段
    available_slots_result: list[dict[str, Any]] = []
    for raw in raw_slots:
        rs, re_ = raw["start_minutes"], raw["end_minutes"]
        # 按 package_duration 切片
        cursor = rs
        while cursor + package_duration <= re_:
            # 检查 [cursor, cursor + package_duration) 是否被占用
            conflict = False
            for b_start, b_end in busy_intervals:
                if cursor < b_end and cursor + package_duration > b_start:
                    conflict = True
                    # 跳过到占用结束位置
                    cursor = b_end
                    break
            if conflict:
                continue

            available_slots_result.append({
                "start": _format_minutes(cursor),
                "end": _format_minutes(cursor + package_duration),
                "duration_minutes": package_duration,
            })
            cursor += 30  # 每 30 分钟一个间隔

    return {
        "photographer_id": photographer_id,
        "photographer_name": photographer.display_name,
        "date": query_date.strftime("%m-%d"),
        "date_label": f"{query_date.month}月{query_date.day}日 ({_weekday_name_cn(query_date)})",
        "location": location,
        "slots": available_slots_result,
        "package_duration": package_duration,
        "total_available": len(available_slots_result),
    }


def find_nearby_available_dates(
    db: Session,
    *,
    photographer_id: int,
    package_duration: int = 120,
    max_days: int = 14,
) -> list[dict[str, Any]]:
    """
    查找摄影师未来 N 天内有可用时段的所有日期。
    档期默认为空闲，只有忙碌日期和已有订单会排除可用时段。
    """
    results = []
    for i in range(max_days):
        d = _today() + timedelta(days=i)
        date_str = d.strftime("%m-%d")
        slot_result = get_available_slots(
            db,
            photographer_id=photographer_id,
            package_duration=package_duration,
            date_str=date_str,
        )
        if slot_result.get("total_available", 0) > 0:
            results.append(slot_result)
    return results


# --- Booking Agent 上下文函数 ---

def _latest_referenced_package(db: Session, conversation_id: int, content: str | None = None) -> dict | None:
    """
    从最近 assistant 消息的 references 中查找 packages，
    支持按索引（如"第一个"）或名称匹配
    """
    requested_index = _requested_reference_index(content)

    messages = (
        db.query(AIMessage)
        .filter(AIMessage.conversation_id == conversation_id, AIMessage.role == "assistant")
        .order_by(AIMessage.created_at.desc(), AIMessage.id.desc())
        .limit(20)
        .all()
    )

    for message in messages:
        references = (message.message_metadata or {}).get("references") or {}
        packages = references.get("packages") or []
        if not packages:
            continue

        # 按名称匹配
        named_match = _match_package_by_name(content, packages)
        if named_match:
            return named_match

        # 按索引匹配
        if requested_index is not None:
            if 0 <= requested_index < len(packages):
                return packages[requested_index]
            continue

        text = (content or "").strip()
        if any(term in text for term in ("最近", "离得近", "距离近")):
            known = [pkg for pkg in packages if pkg.get("distance_km") is not None]
            if known:
                return min(known, key=lambda pkg: float(pkg["distance_km"]))
        if any(term in text for term in ("便宜", "价格低", "最低价")):
            return min(packages, key=lambda pkg: float(pkg.get("price") or 0))
        if "最早" in text:
            def earliest(pkg: dict) -> str:
                slots = ((pkg.get("availability") or {}).get("matching_slots") or [])
                return str(slots[0].get("start_at")) if slots else "9999"
            return min(packages, key=earliest)

        # 默认返回第一个
        return packages[0]

    return None


def _latest_referenced_photographer_for_booking(
    db: Session,
    conversation_id: int,
    content: str | None = None,
) -> dict | None:
    """
    从最近的 references 中查找摄影师信息。
    首先尝试在 packages 的元数据里找 photographer_id，
    其次在 photographers 列表中找。
    """
    # 先尝试从 package 引用中获取摄影师
    pkg = _latest_referenced_package(db, conversation_id, content)
    if pkg and pkg.get("photographer_id"):
        return {
            "user_id": pkg["photographer_id"],
            "user_display_name": pkg.get("photographer_name") or f"摄影师 {pkg['photographer_id']}",
        }

    requested_index = _requested_reference_index(content)

    messages = (
        db.query(AIMessage)
        .filter(AIMessage.conversation_id == conversation_id, AIMessage.role == "assistant")
        .order_by(AIMessage.created_at.desc(), AIMessage.id.desc())
        .limit(20)
        .all()
    )

    for message in messages:
        references = (message.message_metadata or {}).get("references") or {}
        photographers = references.get("photographers") or []
        if not photographers:
            continue

        named_match = _match_photographer_by_name(content, photographers)
        if named_match:
            return named_match

        if requested_index is not None:
            if 0 <= requested_index < len(photographers):
                return photographers[requested_index]
            continue

        return photographers[0]

    return None


def _requested_reference_index(content: str | None) -> int | None:
    """从用户文本中解析引用索引（如“第二个”）。"""
    text = (content or "").strip()
    chinese_numbers = {
        "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
        "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
    }
    match = re.search(r"第\s*([一二两三四五六七八九十\d]+)\s*(?:个|位|名)?", text)
    if not match:
        match = re.search(r"([1-9]\d*)\s*(?:个|位|名|号)", text)
    if not match:
        return None
    raw_value = match.group(1)
    number = int(raw_value) if raw_value.isdigit() else chinese_numbers.get(raw_value)
    if not number:
        return None
    return number - 1


def _match_package_by_name(content: str | None, packages: list[dict]) -> dict | None:
    """在套餐列表中按名称匹配用户提到的套餐。"""
    text = (content or "").strip()
    if not text:
        return None
    candidates = []
    for pkg in packages:
        name = (pkg.get("package_name") or "").strip()
        if name and name in text:
            candidates.append((len(name), pkg))
    if not candidates:
        return None
    return sorted(candidates, key=lambda x: x[0], reverse=True)[0][1]


def _match_photographer_by_name(content: str | None, photographers: list[dict]) -> dict | None:
    """在摄影师列表中按名称匹配用户提到的摄影师。"""
    text = (content or "").strip()
    if not text:
        return None
    candidates = []
    for ph in photographers:
        name = (ph.get("user_display_name") or "").strip()
        if name and name in text:
            candidates.append((len(name), ph))
    if not candidates:
        return None
    return sorted(candidates, key=lambda x: x[0], reverse=True)[0][1]


def _find_package_in_profile(db: Session, photographer_id: int, package_hint: str | None = None) -> dict | None:
    """在摄影师的 packages 列表中查找匹配的套餐。"""
    profile_data = get_profile_by_user_id(db, photographer_id)
    if not profile_data:
        return None
    packages = profile_data.get("packages") or []
    if not packages:
        return None

    if package_hint:
        for pkg in packages:
            name = (pkg.get("name") or "").strip()
            if name and name in package_hint:
                return pkg
        for pkg in packages:
            styles = pkg.get("styles") or []
            for style in styles:
                if style and style in package_hint:
                    return pkg

    return packages[0] if packages else None


def _format_package_for_display(pkg: dict, photographer_name: str | None = None) -> str:
    """格式化套餐信息用于展示"""
    name = pkg.get("name") or ""
    price = pkg.get("price") or 0
    duration = pkg.get("duration") or 120
    image_count = pkg.get("image_count") or ""
    includes = pkg.get("includes") or []

    parts = [f"「{name}」"]
    parts.append(f"价格 {int(price)} 元")
    parts.append(f"时长 {int(duration)} 分钟")
    if image_count:
        parts.append(f"精修 {int(image_count)} 张")
    if includes:
        parts.append(f"包含：{'、'.join(includes[:3])}")

    if photographer_name:
        return f"{photographer_name} 的{' '.join(parts)}"
    return " ".join(parts)


def _format_slot_summary(slots_data: dict[str, Any]) -> str:
    """格式化可用时间段列表"""
    date_label = slots_data.get("date_label", "")
    slots = slots_data.get("slots") or []
    if not slots:
        return f"{date_label} 暂无可用时段"

    slot_texts = [f"{s['start']}-{s['end']}" for s in slots[:6]]
    summary = f"{date_label} 可用时段：{'、'.join(slot_texts)}"
    if len(slots) > 6:
        summary += f" 等共 {len(slots)} 个时段"
    return summary


def _booking_summary_text(
    photographer_name: str | None,
    package_display: str,
    appointment_date: str | None,
    appointment_time: str | None,
) -> str:
    """生成预约确认摘要"""
    lines = [f"摄影师：{photographer_name or '待确认'}"]
    lines.append(f"套餐：{package_display}")
    if appointment_date:
        lines.append(f"日期：{appointment_date}")
    if appointment_time:
        lines.append(f"时间：{appointment_time}")
    return "\n".join(lines)


# --- Booking Agent 主入口 ---

def booking_agent_result(
    db: Session,
    *,
    user_id: int,
    conversation_id: int,
    message_id: int,
    content: str | None,
    confirm_requested: bool,
    package_reference: dict | None = None,
) -> dict[str, Any]:
    """
    Booking Agent 主入口。

    流程:
    1. 确定要预约的摄影师和套餐（从上下文 references 或用户输入）
    2. 缺少日期 -> 询问日期并展示可用日期
    3. 缺少时间 -> 默认 12:00
    4. 信息齐全 -> 生成确认文案
    5. 用户确认 -> 创建预约
    """
    # 检查是否有进行中的 task_state
    task_state = _latest_booking_task_state(db, conversation_id, user_id)
    slots = _merge_booking_slots(task_state, content)
    if package_reference:
        snapshot = package_reference.get("snapshot") or {}
        package = _normalize_package(snapshot)
        slots.update({
            "package_id": package.get("id"),
            "package_name": package.get("name"),
            "selected_package": package,
        })
        if package.get("photographer_id"):
            slots["photographer_id"] = package["photographer_id"]
            slots["photographer_name"] = snapshot.get("photographer_name")

    # 确定摄影师和套餐
    photographer = _resolve_photographer(db, conversation_id, content, slots)
    package_info = _resolve_package(db, conversation_id, content, slots, photographer)

    if not photographer or not package_info:
        return _missing_photographer_or_package_result()

    photographer_name = photographer.get("user_display_name") or f"摄影师 {photographer['user_id']}"
    pkg = package_info["package"]
    pkg_display = _format_package_for_display(pkg, photographer_name)
    photographer_id = photographer["user_id"]
    duration_minutes = pkg.get("duration") or 120
    slots.update({
        "photographer_id": photographer_id,
        "photographer_name": photographer_name,
        "package_id": pkg.get("id"),
        "package_name": pkg.get("name"),
        "package_display": pkg_display,
        "selected_package": pkg,
        "duration_minutes": duration_minutes,
    })

    # 确定日期
    appointment_date = slots.get("date")
    appointment_time = slots.get("time")

    # 阶段 1: 缺少日期 -> 询问日期 + 展示可用日期
    if not appointment_date:
        result = _ask_for_date_result(
            db=db,
            photographer_id=photographer_id,
            package_duration=duration_minutes,
            pkg_display=pkg_display,
            slots_data=slots,
        )
        return _attach_booking_plan(
            result,
            task_state,
            status="awaiting_date",
            completed_step_ids=("vision_analysis", "search_packages", "select_package"),
            current_step_id="select_time",
        )

    # 阶段 2: 缺少时间 -> 默认 12:00，用户明确指定时间时使用用户时间
    if not appointment_time:
        matching_slots = ((pkg.get("availability") or {}).get("matching_slots") or [])
        if matching_slots:
            appointment_time = datetime.fromisoformat(matching_slots[0]["start_at"]).strftime("%H:%M")
        else:
            appointment_time = slots.get("time_start") or DEFAULT_BOOKING_TIME
        slots["time"] = appointment_time

    # 阶段 3: 信息齐全 -> 确认
    if confirm_requested:
        result = _execute_booking_result(
            db=db,
            user_id=user_id,
            conversation_id=conversation_id,
            message_id=message_id,
            photographer_id=photographer_id,
            package_display=pkg_display,
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            duration_minutes=duration_minutes,
            photographer_name=photographer_name,
            slots_data=slots,
        )
        task_status = ((result.get("metadata") or {}).get("task_state") or {}).get("status")
        return _attach_booking_plan(
            result,
            task_state,
            status=task_status or "completed",
            completed_step_ids=(
                "vision_analysis",
                "search_packages",
                "select_package",
                "select_time",
                "confirm_booking",
                "create_booking",
            ) if task_status == "completed" else (
                "vision_analysis",
                "search_packages",
                "select_package",
                "select_time",
                "confirm_booking",
            ),
            failed_step_id="create_booking" if task_status == "failed" else None,
        )

    # 生成确认文案
    result = _confirmation_result(
        photographer_name=photographer_name,
        pkg_display=pkg_display,
        appointment_date=appointment_date,
        appointment_time=appointment_time,
        slots_data=slots,
    )
    return _attach_booking_plan(
        result,
        task_state,
        status="awaiting_confirmation",
        completed_step_ids=(
            "vision_analysis",
            "search_packages",
            "select_package",
            "select_time",
            "confirm_booking",
        ),
    )


def _latest_booking_task_state(
    db: Session,
    conversation_id: int,
    user_id: int | None = None,
) -> dict[str, Any] | None:
    """从最近 assistant 消息中获取 booking 类型的 task_state"""
    if user_id is not None:
        task = get_active_task(db, user_id, conversation_id)
        if task and task.task_type == "create_booking":
            fields = task.fields or {}
            target = task.target or {}
            slots = {**target, **fields}
            if fields.get("appointment_date"):
                slots["date"] = fields["appointment_date"]
            appointment_time = fields.get("appointment_time")
            if appointment_time:
                try:
                    parsed = datetime.fromisoformat(str(appointment_time))
                    slots.setdefault("date", parsed.strftime("%m-%d"))
                    slots["time"] = parsed.strftime("%H:%M")
                except ValueError:
                    pass
            state = {
                "task_type": "create_booking",
                "status": "awaiting_confirmation" if slots.get("date") else "awaiting_date",
                "slots": slots,
                "pending_action": None,
            }
            latest_message = (
                db.query(AIMessage)
                .filter(
                    AIMessage.conversation_id == conversation_id,
                    AIMessage.role == "assistant",
                )
                .order_by(AIMessage.created_at.desc(), AIMessage.id.desc())
                .first()
            )
            legacy_state = (latest_message.message_metadata or {}).get("task_state") if latest_message else None
            if isinstance(legacy_state, dict) and legacy_state.get("task_plan"):
                state["task_plan"] = legacy_state["task_plan"]
            return state

    message = (
        db.query(AIMessage)
        .filter(
            AIMessage.conversation_id == conversation_id,
            AIMessage.role == "assistant",
        )
        .order_by(AIMessage.created_at.desc(), AIMessage.id.desc())
        .first()
    )
    if not message:
        return None
    task_state = (message.message_metadata or {}).get("task_state") or {}
    if task_state.get("task_type") != "create_booking":
        return None
    return task_state


def _merge_booking_slots(task_state: dict | None, content: str | None) -> dict[str, Any]:
    """合并历史 task_state 中的 slots 和用户新输入的信息"""
    slots: dict[str, Any] = {}

    if task_state:
        prev_slots = task_state.get("slots") or {}
        # 只保留有值的字段
        for key in (
            "photographer_id", "photographer_name", "package_id", "package_name",
            "package_display", "selected_package", "date", "time", "appointment_date",
            "appointment_time", "notes", "duration_minutes", "time_start", "time_end",
        ):
            val = prev_slots.get(key)
            if val not in (None, "", []):
                slots[key] = val

    # 从用户输入中提取新的信息
    if content:
        extracted = _extract_booking_slots(content)
        for key, val in extracted.items():
            if val not in (None, "", []):
                slots[key] = val

    return slots


def _extract_booking_slots(text: str) -> dict[str, Any]:
    """从用户输入中提取预约相关参数"""
    text = text or ""
    slots: dict[str, Any] = {}

    unicode_date = re.search(r"(\d{1,2})\s*[\u6708]\s*(\d{1,2})\s*[\u65e5\u53f7]?", text)
    if not unicode_date:
        unicode_date = re.search(r"(\d{1,2})\s*[/\-]\s*(\d{1,2})", text)
    if unicode_date:
        slots["date"] = f"{int(unicode_date.group(1)):02d}-{int(unicode_date.group(2)):02d}"
    else:
        chinese_date = re.search(
            r"([\u96f6\u3007\u4e00\u4e8c\u4e24\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d\u5341]+)\s*\u6708\s*"
            r"([\u96f6\u3007\u4e00\u4e8c\u4e24\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d\u5341]+)\s*[\u65e5\u53f7]?",
            text,
        )
        if chinese_date:
            month = _parse_unicode_chinese_number(chinese_date.group(1))
            day = _parse_unicode_chinese_number(chinese_date.group(2))
            if month and day and 1 <= month <= 12 and 1 <= day <= 31:
                slots["date"] = f"{month:02d}-{day:02d}"

    # 日期
    match = re.search(r"(\d{1,2})\s*月\s*(\d{1,2})\s*(?:[日号])?", text)
    if match:
        slots["date"] = f"{int(match.group(1)):02d}-{int(match.group(2)):02d}"

    # 时间
    time_match = re.search(r"(\d{1,2})(?::|：)(\d{2})", text)
    if time_match:
        slots["time"] = f"{int(time_match.group(1)):02d}:{time_match.group(2)}"
    else:
        # "3点" "下午2点" 等
        hour_match = re.search(r"(上午|下午|晚上)?\s*(\d{1,2})\s*点", text)
        if hour_match:
            hour = int(hour_match.group(2))
            if hour_match.group(1) in {"下午", "晚上"} and hour < 12:
                hour += 12
            slots["time"] = f"{hour:02d}:00"

    if "time" not in slots:
        time_match = re.search(r"(\d{1,2})(?::|[\uff1a])(\d{2})", text)
        if time_match:
            slots["time"] = f"{int(time_match.group(1)):02d}:{time_match.group(2)}"
        else:
            hour_match = re.search(
                r"([\u4e0a\u5348\u4e0b\u5348\u665a\u4e0a])?\s*(\d{1,2})\s*[\u70b9\u65f6]",
                text,
            )
            if hour_match:
                hour = int(hour_match.group(2))
                if hour_match.group(1) in {"\u4e0b\u5348", "\u665a\u4e0a"} and hour < 12:
                    hour += 12
                slots["time"] = f"{hour:02d}:00"

    # 摄影师名称
    name_match = re.search(r"([\u4e00-\u9fffA-Za-z0-9_ -]{2,24}摄影师\d*)", text)
    if name_match:
        slots["photographer_name"] = name_match.group(1).strip()

    notes_match = re.search(
        r"(?:\u5907\u6ce8|\u9700\u6c42|\u8bf4\u660e)\s*(?:[:\uff1a,\uff0c]\s*)?(.+)$",
        text,
    )
    if notes_match:
        slots["notes"] = notes_match.group(1).strip()[:500]

    return slots


def _resolve_photographer(
    db: Session,
    conversation_id: int,
    content: str | None,
    slots: dict[str, Any],
) -> dict | None:
    """从各种来源解析摄影师信息"""
    # 1. 从 slots 中直接获取
    if slots.get("photographer_id"):
        photographer_id = slots["photographer_id"]
        user = db.query(User).filter(User.id == photographer_id).first()
        if user:
            return {"user_id": user.id, "user_display_name": user.display_name}

    # 2. 从上下文 references 中查找
    return _latest_referenced_photographer_for_booking(db, conversation_id, content)


def _resolve_package(
    db: Session,
    conversation_id: int,
    content: str | None,
    slots: dict[str, Any],
    photographer: dict | None,
) -> dict | None:
    """从各种来源解析套餐信息"""
    # 1. 规划阶段已经选中过套餐时，优先沿用，避免后续只补日期导致检索为空。
    selected_package = slots.get("selected_package")
    if isinstance(selected_package, dict):
        return {"package": _normalize_package(selected_package)}

    if photographer and slots.get("package_id"):
        profile_data = get_profile_by_user_id(db, photographer["user_id"])
        for package in (profile_data or {}).get("packages") or []:
            if str(package.get("id") or package.get("package_id")) == str(slots["package_id"]):
                return {"package": _normalize_package(package)}

    # 1. 从上下文 references 中查找
    pkg = _latest_referenced_package(db, conversation_id, content)
    if pkg:
        return {"package": _normalize_package(pkg)}

    # 2. 有摄影师时，从摄影师资料中查找
    if photographer:
        photographer_id = photographer["user_id"]
        package_hint = slots.get("package_name") or content
        found = _find_package_in_profile(db, photographer_id, package_hint)
        if found:
            return {"package": found}

    return None


def _normalize_package(pkg: dict) -> dict:
    """将 references 中的 package 格式转为标准格式"""
    return {
        "id": pkg.get("id") or pkg.get("package_id"),
        "name": pkg.get("package_name") or pkg.get("name") or "",
        "price": pkg.get("price") or 0,
        "duration": pkg.get("duration") or pkg.get("duration_minutes") or 120,
        "image_count": pkg.get("image_count") or 0,
        "includes": pkg.get("includes") or [],
        "styles": pkg.get("styles") or [],
        "availability": pkg.get("availability"),
        "distance_km": pkg.get("distance_km"),
        "photographer_id": pkg.get("photographer_id"),
        "photographer_name": pkg.get("photographer_name"),
    }


def _missing_photographer_or_package_result() -> dict[str, Any]:
    """无法确定摄影师或套餐时的回复"""
    return {
        "content": (
            "你想预约哪个套餐？可以先让我帮你查找摄影师和套餐，"
            "找到后告诉我「预约这个套餐」或「就这个」，我来帮你安排预约。"
        ),
        "metadata": {
            "model": {"provider": "platform_orchestrator", "model": "booking-agent"},
            "suggested_actions": [],
            "task_state": {
                "task_type": "create_booking",
                "status": "awaiting_package",
                "slots": {},
                "pending_action": None,
            },
        },
    }


def _ask_for_date_result(
    db: Session,
    *,
    photographer_id: int,
    package_duration: int,
    pkg_display: str,
    slots_data: dict[str, Any],
) -> dict[str, Any]:
    """缺少日期时，查询可用日期并询问用户"""
    nearby = find_nearby_available_dates(
        db,
        photographer_id=photographer_id,
        package_duration=package_duration,
        max_days=14,
    )

    if not nearby:
        return {
            "content": (
                f"你选择的 {pkg_display} 未来两周暂时没有可预约的时间段。"
                "你可以换个摄影师或稍后再查看。"
            ),
            "metadata": {
                "model": {"provider": "platform_orchestrator", "model": "booking-agent-no-slots"},
                "suggested_actions": [],
                "task_state": {
                    "task_type": "create_booking",
                    "status": "awaiting_date",
                    "slots": {
                        "photographer_id": photographer_id,
                        "package_display": pkg_display,
                        "duration_minutes": package_duration,
                    },
                    "pending_action": None,
                },
            },
        }

    content_parts = [
        f"你选择了 {pkg_display}。",
        f"请告诉我你想约哪一天？以下是近期可选日期。没有指定具体几点时，我会默认约 {DEFAULT_BOOKING_TIME}：",
    ]
    content_parts.extend(f"  • {day_slots['date_label']}" for day_slots in nearby[:5])
    if len(nearby) > 5:
        content_parts.append(f"  ……以及之后 {len(nearby) - 5} 天也可预约。")

    # 保存可用日期信息到 slots，方便后续快速查询
    available_dates = [
        {"date": d["date"], "date_label": d["date_label"]}
        for d in nearby[:14]
    ]

    return {
        "content": "\n".join(content_parts),
        "metadata": {
            "model": {"provider": "platform_orchestrator", "model": "booking-agent-ask-date"},
            "available_dates": available_dates,
            "suggested_actions": [],
            "task_state": {
                "task_type": "create_booking",
                "status": "awaiting_date",
                "slots": {
                    "photographer_id": photographer_id,
                    "package_display": pkg_display,
                    "duration_minutes": package_duration,
                },
                "pending_action": None,
            },
        },
    }


def _ask_for_time_result(
    db: Session,
    *,
    photographer_id: int,
    package_duration: int,
    date_str: str,
    pkg_display: str,
    slots_data: dict[str, Any],
) -> dict[str, Any]:
    """缺少时间时，查询并展示可用时段"""
    slot_result = get_available_slots(
        db,
        photographer_id=photographer_id,
        package_duration=package_duration,
        date_str=date_str,
    )

    if not slot_result.get("slots"):
        return {
            "content": (
                f"{slot_result.get('date_label', date_str)} {pkg_display} 没有可用时段。"
                "你可以选另一个日期，我帮你再查。"
            ),
            "metadata": {
                "model": {"provider": "platform_orchestrator", "model": "booking-agent-no-time"},
                "suggested_actions": [],
                "task_state": {
                    "task_type": "create_booking",
                    "status": "awaiting_time",
                    "slots": {
                        "photographer_id": photographer_id,
                        "package_display": pkg_display,
                        "date": date_str,
                        "duration_minutes": package_duration,
                    },
                    "pending_action": None,
                },
            },
        }

    slot_summary = _format_slot_summary(slot_result)
    content = f"{slot_result.get('date_label', date_str)} {pkg_display}。\n{slot_summary}\n\n你希望约哪个时间段？"

    return {
        "content": content,
        "metadata": {
            "model": {"provider": "platform_orchestrator", "model": "booking-agent-ask-time"},
            "available_slots_result": slot_result,
            "suggested_actions": [],
            "task_state": {
                "task_type": "create_booking",
                "status": "awaiting_time",
                "slots": {
                    "photographer_id": photographer_id,
                    "package_display": pkg_display,
                    "date": date_str,
                    "duration_minutes": package_duration,
                },
                "pending_action": None,
            },
        },
    }


def _confirmation_result(
    *,
    photographer_name: str,
    pkg_display: str,
    appointment_date: str,
    appointment_time: str,
    slots_data: dict[str, Any],
) -> dict[str, Any]:
    """信息齐全，生成确认文案"""
    # 尝试把 MM-DD 转成更友好的格式
    date_label = appointment_date
    match = re.match(r"^(\d{2})-(\d{2})$", appointment_date)
    if match:
        date_label = f"{int(match.group(1))}月{int(match.group(2))}日"

    summary = _booking_summary_text(
        photographer_name=photographer_name,
        package_display=pkg_display,
        appointment_date=date_label,
        appointment_time=appointment_time,
    )

    content = f"我帮你整理了预约信息，请确认：\n{summary}\n\n确认后我会为你创建预约。"
    appointment_dt = build_booking_appointment_datetime(appointment_date, appointment_time)
    booking_payload = {
        "package_id": slots_data.get("package_id") or (slots_data.get("selected_package") or {}).get("id"),
        "photographer_id": slots_data.get("photographer_id"),
        "package_description": pkg_display,
        "appointment_time": appointment_dt.isoformat(),
        "duration_minutes": slots_data.get("duration_minutes", 120),
        "notes": slots_data.get("notes"),
    }

    return {
        "content": content,
        "metadata": {
            "model": {"provider": "platform_orchestrator", "model": "booking-agent-confirmation"},
            "suggested_actions": [
                {
                    "type": "confirm_create_booking",
                    "label": "确认预约",
                    "payload": {
                        "photographer_id": slots_data.get("photographer_id"),
                        "package_id": slots_data.get("package_id") or (slots_data.get("selected_package") or {}).get("id"),
                        "photographer_name": photographer_name,
                        "package_display": pkg_display,
                        "appointment_date": appointment_date,
                        "appointment_time": appointment_time,
                        "duration_minutes": slots_data.get("duration_minutes", 120),
                        "notes": slots_data.get("notes"),
                    },
                    "requires_confirmation": True,
                }
            ],
            "task_state": {
                "task_type": "create_booking",
                "status": "awaiting_confirmation",
                "slots": {
                    "photographer_id": slots_data.get("photographer_id"),
                    "photographer_name": photographer_name,
                    "package_name": slots_data.get("package_name"),
                    "package_display": pkg_display,
                    "selected_package": slots_data.get("selected_package"),
                    "notes": slots_data.get("notes"),
                    "date": appointment_date,
                    "time": appointment_time,
                    "duration_minutes": slots_data.get("duration_minutes", 120),
                },
                "pending_action": {
                    "tool": "create_booking",
                    "input": booking_payload,
                },
            },
        },
    }


def _execute_booking_result(
    db: Session,
    *,
    user_id: int,
    conversation_id: int,
    message_id: int,
    photographer_id: int,
    package_display: str,
    appointment_date: str,
    appointment_time: str,
    duration_minutes: int,
    photographer_name: str,
    slots_data: dict[str, Any],
) -> dict[str, Any]:
    """用户确认后创建预约"""
    try:
        appointment_dt = build_booking_appointment_datetime(appointment_date, appointment_time)
    except (ValueError, IndexError) as e:
        return _booking_error_result(f"日期时间解析失败：{e}", slots_data)

    # 调用 create_booking 工具
    from backend.app.services.ai_agent_tool_service import create_booking as create_booking_tool

    tool_call = create_booking_tool(
        db,
        user_id=user_id,
        conversation_id=conversation_id,
        message_id=message_id,
        booking_payload={
            "photographer_id": photographer_id,
            "package_id": slots_data.get("package_id") or (slots_data.get("selected_package") or {}).get("id"),
            "package_description": package_display,
            "appointment_time": appointment_dt.isoformat(),
            "duration_minutes": duration_minutes,
            "notes": slots_data.get("notes"),
        },
    )
    result = tool_call.get("result") or {}
    if tool_call["status"] == "success":
        date_label = f"{appointment_dt.month}月{appointment_dt.day}日"
        content = (
            f"预约已创建！\n"
            f"摄影师：{photographer_name}\n"
            f"套餐：{package_display}\n"
            f"时间：{date_label} {appointment_time}\n\n"
            f"订单编号：{result.get('order_id')}\n"
            f"状态：待摄影师确认。摄影师确认后你会收到通知。"
        )
        status_value = "completed"
    else:
        content = f"预约创建失败：{result.get('error') or '工具执行失败'}。"
        status_value = "failed"

    return {
        "content": content,
        "metadata": {
            "model": {"provider": "platform_tool", "model": "create-booking"},
            "tool_calls": [tool_call],
            "suggested_actions": [],
            "task_state": {
                "task_type": "create_booking",
                "status": status_value,
                "slots": {
                    "photographer_id": photographer_id,
                    "photographer_name": photographer_name,
                    "package_name": slots_data.get("package_name"),
                    "package_display": package_display,
                    "selected_package": slots_data.get("selected_package"),
                    "date": appointment_date,
                    "time": appointment_time,
                    "duration_minutes": duration_minutes,
                },
                "pending_action": None,
            },
        },
    }


def _booking_error_result(error_msg: str, slots_data: dict[str, Any]) -> dict[str, Any]:
    """预约失败时的错误返回"""
    return {
        "content": f"预约失败：{error_msg}",
        "metadata": {
            "model": {"provider": "platform_tool", "model": "create-booking-error"},
            "suggested_actions": [],
            "task_state": {
                "task_type": "create_booking",
                "status": "failed",
                "slots": {
                    k: v for k, v in slots_data.items()
                    if k in ("photographer_id", "photographer_name", "package_display",
                             "date", "time", "duration_minutes")
                },
                "pending_action": None,
            },
        },
    }
