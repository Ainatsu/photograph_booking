"""Deterministic, bounded extraction for incremental Agent task patches."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any


TASK_FIELDS: dict[str, set[str]] = {
    "create_project": {
        "title", "description", "category", "style_tags", "city", "location_text",
        "shoot_date_start", "shoot_date_end", "duration_minutes", "budget_min", "budget_max",
        "deliverables", "visibility", "expires_at", "reference_images",
    },
    "publish_package": {
        "name", "price", "duration", "description", "includes", "styles", "city",
        "service_location", "original_image_count", "retouched_image_count", "delivery_days",
        "included_revision_count", "payment_mode", "deposit_rate", "commercial_license",
        "delivery_formats", "terms_rules", "samples",
    },
    "publish_work": {"title", "tags", "description"},
    "project_application": {"proposal_text", "price_quote", "package_snapshot", "portfolio_refs", "revision_note"},
    "create_booking": {"appointment_date", "duration_minutes", "notes"},
    "create_inspiration": {
        "inspiration_id", "reference_text", "title", "summary", "tags", "cover_url",
        "location_name", "location_address", "latitude", "longitude", "place_id",
        "provider", "coordinate_system", "location_precision", "generation_metadata",
    },
    "generate_image": {"prompt", "mode", "aspect_ratio", "count", "quality", "strength", "source"},
}

_MONEY = r"(?P<value>\d+(?:\.\d+)?)"


def _number(value: str) -> int | float:
    number = float(value.replace(",", ""))
    return int(number) if number.is_integer() else number


def _clean_list(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"[、,，/和及\s]+", value) if item.strip()]


def _first_match(patterns: list[str], text: str) -> re.Match[str] | None:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match
    return None


def _parse_datetime(text: str, fallback_date: str | None = None) -> tuple[str | None, str | None, str | None]:
    """Return (date, time, iso_datetime) for explicit absolute dates in one reply."""
    iso_match = re.search(r"(20\d{2})[-/](\d{1,2})[-/](\d{1,2})(?:\s*[T ]?\s*(\d{1,2})(?::|：)(\d{2}))?", text)
    cn_match = re.search(r"(20\d{2})年(\d{1,2})月(\d{1,2})日?(?:\s*(上午|下午|晚上)?\s*(\d{1,2})(?:点|时)(?:(\d{1,2})分?)?)?", text)
    match = iso_match or cn_match
    date_value = None
    has_explicit_time = False
    if match:
        year, month, day = (int(match.group(index)) for index in (1, 2, 3))
        date_value = f"{year:04d}-{month:02d}-{day:02d}"
        if iso_match:
            has_explicit_time = match.group(4) is not None
            hour = int(match.group(4) or 0)
            minute = int(match.group(5) or 0)
        else:
            has_explicit_time = match.group(5) is not None
            period = match.group(4) or ""
            hour = int(match.group(5) or 0)
            minute = int(match.group(6) or 0)
            if period in {"下午", "晚上"} and hour < 12:
                hour += 12
    else:
        time_match = re.search(r"(?:(上午|下午|晚上)\s*)?(\d{1,2})(?::|：|点|时)(\d{1,2})?分?", text)
        if not time_match or not fallback_date:
            return None, None, None
        date_value = fallback_date[:10]
        period = time_match.group(1) or ""
        hour = int(time_match.group(2))
        minute = int(time_match.group(3) or 0)
        if period in {"下午", "晚上"} and hour < 12:
            hour += 12
        has_explicit_time = True

    try:
        date_only = datetime.fromisoformat(date_value)
        value = date_only.replace(hour=hour, minute=minute)
    except ValueError:
        return None, None, None
    return value.date().isoformat(), value.strftime("%H:%M") if has_explicit_time else None, value.isoformat() if has_explicit_time else None


def _set(field: str, value: Any, evidence: str, confidence: float = 0.95) -> dict[str, Any]:
    return {"field": field, "op": "set", "value": value, "confidence": confidence, "evidence": evidence}


def _clear(field: str, evidence: str) -> dict[str, Any]:
    return {"field": field, "op": "clear", "value": None, "confidence": 0.95, "evidence": evidence}


def extract_task_patch(
    task_type: str,
    content: str | None,
    *,
    page_context: dict[str, Any] | None = None,
    existing_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Extract only explicit, allow-listed facts from one user message.

    This intentionally stays conservative. Domain intent classification can provide a
    richer merged snapshot, while this function handles corrections and clear semantics.
    """
    allowed = TASK_FIELDS.get(task_type, set())
    text = (content or "").strip()
    operations: list[dict[str, Any]] = []
    if not text or not allowed:
        return {"task_type": task_type, "operations": []}

    def add(field: str, value: Any, evidence: str, confidence: float = 0.95) -> None:
        if field in allowed:
            operations.append(_set(field, value, evidence, confidence))

    if "title" in allowed:
        match = _first_match([
            r"(?:标题|企划名|作品名)\s*(?:改成|改为|叫|是|：|:)\s*([^，。；;\n]{1,120})",
        ], text)
        if match:
            add("title", match.group(1).strip(), match.group(0))
    if "name" in allowed:
        match = _first_match([
            r"(?:方案名|套餐名|名称)\s*(?:改成|改为|叫|是|：|:)\s*([^，。；;\n]{1,120})",
        ], text)
        if match:
            add("name", match.group(1).strip(), match.group(0))

    if "city" in allowed:
        match = re.search(r"(?:城市|地点|在|去)\s*[：:]?\s*([^，。,；;。\s]{2,20})", text)
        if match and match.group(1) not in {"拍照", "拍摄", "预约", "发布"} and "不定" not in match.group(1):
            add("city", match.group(1), match.group(0))
    if "style_tags" in allowed:
        match = re.search(r"(?:风格|想要|偏好)\s*[：:]?\s*([^，,。；;\n]+)", text)
        if match:
            add("style_tags", _clean_list(match.group(1)), match.group(0))
    if "styles" in allowed:
        match = re.search(r"(?:风格|类型|擅长)\s*[：:]?\s*([^，,。；;\n]+)", text)
        if match:
            add("styles", _clean_list(match.group(1)), match.group(0))
    if "tags" in allowed:
        match = re.search(r"(?:标签|风格)\s*[：:]?\s*([^。；;\n]+)", text)
        if match:
            add("tags", _clean_list(match.group(1)), match.group(0))
    if "budget_min" in allowed:
        match = re.search(rf"(?:预算最低|预算下限|至少)\s*(?:改成|改为|调整为|设置为)?\s*[：:]?\s*{_MONEY}", text)
        if match:
            add("budget_min", _number(match.group("value")), match.group(0))
    if "budget_max" in allowed:
        match = re.search(rf"(?:预算最高|预算上限|最多|预算)\s*(?:改成|改为|调整为|设置为)?\s*[：:]?\s*{_MONEY}", text)
        if match:
            add("budget_max", _number(match.group("value")), match.group(0))
    if "price" in allowed:
        match = re.search(rf"(?:价格|收费|售价)\s*[：:]?\s*{_MONEY}", text)
        if match:
            add("price", _number(match.group("value")), match.group(0))
    if "price_quote" in allowed:
        match = re.search(rf"(?:报价|应邀价格|我的价格)\s*[：:]?\s*{_MONEY}", text)
        if match:
            add("price_quote", _number(match.group("value")), match.group(0))
    if "duration_minutes" in allowed or "duration" in allowed:
        match = re.search(r"(?:时长|拍摄时长)\s*[：:]?\s*(\d+(?:\.\d+)?)\s*(小时|小時|分钟|分鐘|分)", text)
        if match:
            minutes = _number(match.group(1)) * (60 if match.group(2) in {"小时", "小時"} else 1)
            add("duration_minutes" if "duration_minutes" in allowed else "duration", minutes, match.group(0))
    if "description" in allowed:
        match = re.search(r"(?:描述|说明|需求|介绍)\s*(?:改成|改为|是|：|:)\s*(.+)", text)
        if match:
            add("description", match.group(1).strip(), match.group(0))
    if "proposal_text" in allowed:
        match = re.search(r"(?:应邀说明|申请说明|拍摄方案|提案)\s*(?:改成|改为|是|：|:)\s*(.+)", text)
        if match:
            add("proposal_text", match.group(1).strip(), match.group(0))
    if "package_snapshot" in allowed:
        match = re.search(r"(?:关联方案|方案摘要)\s*(?:改成|改为|是|：|:)\s*([^。；;\n]+)", text)
        if match:
            add("package_snapshot", match.group(1).strip(), match.group(0))
    if "deliverables" in allowed:
        match = re.search(r"(?:交付要求|交付内容)\s*(?:改成|改为|是|：|:)\s*(.+)", text)
        if match:
            add("deliverables", match.group(1).strip(), match.group(0))
    if "includes" in allowed:
        match = re.search(r"(?:包含|服务内容)\s*[：:]?\s*([^。；;\n]+)", text)
        if match:
            add("includes", _clean_list(match.group(1)), match.group(0))
    if "delivery_formats" in allowed:
        match = re.search(r"(?:交付格式|格式)\s*[：:]?\s*([^。；;\n]+)", text)
        if match:
            add("delivery_formats", _clean_list(match.group(1)), match.group(0))
    number_fields = {
        "original_image_count": ("原片", "底片"),
        "retouched_image_count": ("精修", "精修数量"),
        "delivery_days": ("交付周期", "交付天数"),
        "included_revision_count": ("修改次数", "免费修改"),
    }
    for field, aliases in number_fields.items():
        if field not in allowed:
            continue
        alias_pattern = "|".join(re.escape(alias) for alias in aliases)
        match = re.search(rf"(?:{alias_pattern})\s*[：:]?\s*(\d+)", text)
        if match:
            add(field, int(match.group(1)), match.group(0))
    if "payment_mode" in allowed:
        if re.search(r"定金\s*(?:加|\+)?\s*尾款", text):
            add("payment_mode", "deposit_balance", "定金加尾款")
        elif re.search(r"全款(?:支付)?", text):
            add("payment_mode", "full", "全款支付")
    if "deposit_rate" in allowed:
        match = re.search(r"定金(?:比例)?\s*[：:]?\s*(\d{1,2})(?:%|％|成)", text)
        if match:
            raw = int(match.group(1))
            rate = raw / (10 if "成" in match.group(0) else 100)
            add("deposit_rate", rate, match.group(0))
    if "commercial_license" in allowed:
        if re.search(r"(?:包含|允许)商业(?:使用|授权)", text):
            add("commercial_license", True, "包含商业授权")
        elif re.search(r"(?:不包含|不允许)商业(?:使用|授权)", text):
            add("commercial_license", False, "不包含商业授权")
    if "notes" in allowed:
        match = re.search(r"(?:备注|需求|说明)\s*(?:改成|改为|是|：|:)\s*(.+)", text)
        if match:
            add("notes", match.group(1).strip()[:500], match.group(0))
    existing_fields = existing_fields or {}
    fallback_date = existing_fields.get("appointment_date") or existing_fields.get("shoot_date_start")
    date_value, _time_value, datetime_value = _parse_datetime(text, str(fallback_date) if fallback_date else None)
    if date_value and "appointment_date" in allowed:
        add("appointment_date", date_value, date_value)
    if datetime_value:
        if "shoot_date_start" in allowed:
            add("shoot_date_start", datetime_value, datetime_value)

    clear_aliases = {
        "location_text": r"(?:地点|位置)(?:先)?(?:不定|取消|清空|不要)",
        "description": r"(?:描述|说明|需求)(?:先)?(?:不填|清空|取消|不要)",
        "notes": r"(?:备注|需求)(?:先)?(?:不填|清空|取消|不要)",
    }
    for field, pattern in clear_aliases.items():
        if field in allowed and re.search(pattern, text):
            operations.append(_clear(field, text))

    # A single answer may contain many fields. Keep every distinct field, with the
    # last explicit mention winning when the same field appears more than once.
    deduped: dict[str, dict[str, Any]] = {}
    for operation in operations:
        deduped[operation["field"]] = operation
    return {"task_type": task_type, "operations": list(deduped.values())}


def apply_operations(fields: dict[str, Any], operations: list[dict[str, Any]], allowed: set[str]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Apply validated operations and return a new snapshot plus accepted operations."""
    next_fields = dict(fields or {})
    accepted: list[dict[str, Any]] = []
    for operation in operations:
        field = operation.get("field")
        if field not in allowed or operation.get("op") not in {"set", "clear"}:
            continue
        confidence = float(operation.get("confidence", 0))
        if confidence < 0.75:
            continue
        if operation["op"] == "clear":
            next_fields.pop(field, None)
        else:
            next_fields[field] = operation.get("value")
        accepted.append(operation)
    return next_fields, accepted
