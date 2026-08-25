"""订单合同快照（套餐/企划/历史）的构建与回填字段服务。"""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any


CURRENCY_CNY = "CNY"
DEFAULT_DELIVERY_DAYS = 7
DEFAULT_COPYRIGHT_TERMS = "著作权归摄影师所有，客户获得订单约定范围内的使用权。"
DEFAULT_CANCELLATION_POLICY = {
    "version": 1,
    "currency": CURRENCY_CNY,
    "rules": [
        {"stage": "before_provider_confirmation", "refund_rate": 1.0, "description": "摄影师确认前取消，全额退款。"},
        {"stage": "customer_more_than_72h", "refund_rate": 0.9, "description": "客户在拍摄前 72 小时以上取消，退款 90%。"},
        {"stage": "customer_24_to_72h", "refund_rate": 0.5, "description": "客户在拍摄前 24-72 小时取消，退款 50%。"},
        {"stage": "customer_less_than_24h", "refund_rate": 0.0, "description": "客户在拍摄前 24 小时内取消，定金不退。"},
        {"stage": "provider_cancelled", "refund_rate": 1.0, "description": "摄影师主动取消，客户全额退款。"},
    ],
}
DEFAULT_RESCHEDULE_POLICY = {
    "version": 1,
    "response_hours": 24,
    "original_slot_retained": True,
    "candidate_slot_locked": True,
}


def _normalize_datetime(value: datetime) -> datetime:
    """将带时区时间转为 UTC 无时区时间。"""
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _iso(value: datetime | None) -> str | None:
    """将时间转为 ISO 字符串，空值返回 None。"""
    return _normalize_datetime(value).isoformat() if value else None


def _money(value: Any) -> Decimal | None:
    """将任意值转为两位小数的 Decimal 金额，非法返回 None。"""
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        return None


def _money_json(value: Any) -> float | None:
    """将金额转为 JSON 兼容的 float，非法返回 None。"""
    normalized = _money(value)
    return float(normalized) if normalized is not None else None


def _as_list(value: Any) -> list:
    """将值转为深拷贝的列表，None 转为空列表。"""
    if value is None:
        return []
    if isinstance(value, list):
        return deepcopy(value)
    return [deepcopy(value)]


def _policy(value: Any, default: dict) -> Any:
    """深拷贝策略，空值回退到默认策略。"""
    return deepcopy(value) if value not in (None, "", []) else deepcopy(default)


def _nonnegative_int(value: Any, default: int = 0) -> int:
    """将值转为非负整数，非法回退到默认值。"""
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return default


def _delivery_due_at(appointment_time: datetime, source: dict) -> datetime:
    """按交付日期字段或默认天数计算交付截止时间。"""
    explicit = source.get("delivery_due_at")
    if isinstance(explicit, datetime):
        return _normalize_datetime(explicit)
    delivery_days = source.get("delivery_days") or DEFAULT_DELIVERY_DAYS
    try:
        delivery_days = max(0, int(delivery_days))
    except (TypeError, ValueError):
        delivery_days = DEFAULT_DELIVERY_DAYS
    return _normalize_datetime(appointment_time) + timedelta(days=delivery_days)


def build_package_contract_snapshot(
    *,
    package: dict,
    appointment_time: datetime,
    customer_notes: str | None = None,
) -> dict:
    """构建套餐类订单的合同快照。"""
    package_id = str(package.get("id") or "").strip()
    package_name = str(package.get("package_name") or package.get("name") or "").strip()
    package_description = package.get("description") or ""
    price = _money_json(package.get("price"))
    duration_minutes = _nonnegative_int(
        package.get("duration") or package.get("duration_minutes")
    )
    if not package_id or not package_name:
        raise ValueError("套餐缺少稳定 ID 或名称")
    if price is None or price < 0:
        raise ValueError("套餐价格无效")
    if duration_minutes <= 0:
        raise ValueError("套餐服务时长无效")
    service_location = (
        package.get("service_location")
        or package.get("city")
        or package.get("photographer_location")
        or None
    )
    delivery_due_at = _delivery_due_at(appointment_time, package)
    retouched_count = package.get("retouched_image_count")
    if retouched_count is None:
        retouched_count = package.get("image_count")
    original_count = package.get("original_image_count")
    delivery_formats = _as_list(package.get("delivery_formats") or ["JPG"])
    revision_count = _nonnegative_int(package.get("included_revision_count"))
    included_items = _as_list(package.get("includes"))
    cancellation_policy = _policy(package.get("cancellation_policy"), DEFAULT_CANCELLATION_POLICY)
    reschedule_policy = _policy(package.get("reschedule_policy"), DEFAULT_RESCHEDULE_POLICY)
    copyright_terms = package.get("copyright_terms") or DEFAULT_COPYRIGHT_TERMS

    return {
        "version": 1,
        "source": {"type": "package", "id": package_id, "application_id": None},
        "currency": CURRENCY_CNY,
        "title": package_name,
        "package": {
            "id": package_id,
            "name": package_name,
            "description": package_description,
            "styles": _as_list(package.get("styles")),
            "included_items": included_items,
        },
        "pricing": {"package_price": price, "final_price": price, "currency": CURRENCY_CNY},
        "schedule": {
            "appointment_time": _iso(appointment_time),
            "duration_minutes": duration_minutes,
            "service_location": service_location,
            "delivery_due_at": _iso(delivery_due_at),
        },
        "deliverables": {
            "items": included_items,
            "original_image_count": original_count,
            "retouched_image_count": retouched_count,
            "formats": delivery_formats,
            "included_revision_count": revision_count,
        },
        "license": {
            "commercial_license": bool(package.get("commercial_license", False)),
            "copyright_terms": copyright_terms,
        },
        "policies": {
            "cancellation": cancellation_policy,
            "reschedule": reschedule_policy,
        },
        "payment_mode": package.get("payment_mode") or "full",
        "deposit_rate": float(package.get("deposit_rate") or 0.30),
        "fulfillment_mode": package.get("fulfillment_mode") or "single_delivery",
        "customer_notes": customer_notes,
    }


def build_project_contract_snapshot(
    *,
    project,
    application,
    appointment_time: datetime,
    duration_minutes: int,
) -> dict:
    """构建企划类订单的合同快照。"""
    delivery_due_at = _delivery_due_at(appointment_time, {})
    final_price = _money_json(application.price_quote)
    included_items = _as_list(application.included_items)
    proposal_text = application.proposal_text or ""
    if included_items:
        included_text = "、".join(str(item) for item in included_items if item)
        if included_text and included_text not in proposal_text:
            proposal_text = f"{proposal_text}\n\n包含内容：{included_text}"
    project_deliverables = deepcopy(project.deliverables) if project.deliverables is not None else []
    cancellation_policy = deepcopy(DEFAULT_CANCELLATION_POLICY)
    reschedule_policy = deepcopy(DEFAULT_RESCHEDULE_POLICY)

    return {
        "version": 1,
        "source": {
            "type": "project",
            "id": str(project.id),
            "application_id": application.id,
        },
        "currency": CURRENCY_CNY,
        "title": project.title,
        "project": {
            "id": project.id,
            "title": project.title,
            "category": project.category,
            "style_tags": _as_list(project.style_tags),
            "customer_requirements": {
                "description": project.description,
                "budget_min": project.budget_min,
                "budget_max": project.budget_max,
                "deliverables": project_deliverables,
                "reference_images": _as_list(project.reference_images),
            },
        },
        "application": {
            "id": application.id,
            "photographer_id": application.photographer_id,
            "proposal_text": proposal_text,
            "package_summary": application.package_snapshot,
            "included_items": included_items,
            "revision_note": application.revision_note,
            "portfolio_refs": application.portfolio_refs,
        },
        "pricing": {
            "package_price": final_price,
            "final_price": final_price,
            "currency": CURRENCY_CNY,
        },
        "schedule": {
            "appointment_time": _iso(appointment_time),
            "duration_minutes": duration_minutes,
            "service_location": project.location_text or project.city,
            "delivery_due_at": _iso(delivery_due_at),
        },
        "deliverables": {
            "items": project_deliverables,
            "included_items": included_items,
            "original_image_count": None,
            "retouched_image_count": None,
            "formats": ["JPG"],
            "included_revision_count": 0,
            "revision_terms": application.revision_note,
        },
        "license": {
            "commercial_license": False,
            "copyright_terms": DEFAULT_COPYRIGHT_TERMS,
        },
        "policies": {
            "cancellation": cancellation_policy,
            "reschedule": reschedule_policy,
        },
        "payment_mode": "full",
        "deposit_rate": 0.30,
        "fulfillment_mode": "single_delivery",
        "customer_notes": project.description,
    }


def build_legacy_contract_snapshot(
    *,
    package_snapshot: str,
    appointment_time: datetime,
    duration_minutes: int,
    customer_notes: str | None = None,
) -> dict:
    """构建历史订单的兼容合同快照。"""
    return {
        "version": 1,
        "source": {"type": "legacy", "id": None, "application_id": None},
        "currency": CURRENCY_CNY,
        "title": package_snapshot,
        "pricing": {"package_price": None, "final_price": None, "currency": CURRENCY_CNY},
        "schedule": {
            "appointment_time": _iso(appointment_time),
            "duration_minutes": duration_minutes,
            "service_location": None,
            "delivery_due_at": None,
        },
        "deliverables": {},
        "license": {"commercial_license": False, "copyright_terms": None},
        "policies": {"cancellation": None, "reschedule": None},
        "payment_mode": "full",
        "deposit_rate": 0.30,
        "fulfillment_mode": "single_delivery",
        "customer_notes": customer_notes,
        "legacy": True,
    }


def contract_to_order_fields(snapshot: dict) -> dict:
    """将合同快照映射回订单字段字典。"""
    source = snapshot.get("source") or {}
    package = snapshot.get("package") or {}
    pricing = snapshot.get("pricing") or {}
    schedule = snapshot.get("schedule") or {}
    deliverables = snapshot.get("deliverables") or {}
    license_terms = snapshot.get("license") or {}
    policies = snapshot.get("policies") or {}
    return {
        "source_type": source.get("type") or "legacy",
        "source_id": source.get("id"),
        "source_application_id": source.get("application_id"),
        "package_id": package.get("id"),
        "package_name": package.get("name") or snapshot.get("title"),
        "package_description": package.get("description"),
        "package_price": _money(pricing.get("package_price")),
        "final_price": _money(pricing.get("final_price")),
        "currency": CURRENCY_CNY,
        "service_location": schedule.get("service_location"),
        "delivery_due_at": datetime.fromisoformat(schedule["delivery_due_at"]) if schedule.get("delivery_due_at") else None,
        "original_image_count": deliverables.get("original_image_count"),
        "retouched_image_count": deliverables.get("retouched_image_count"),
        "delivery_formats": deliverables.get("formats") or [],
        "included_revision_count": deliverables.get("included_revision_count"),
        "commercial_license": bool(license_terms.get("commercial_license", False)),
        "copyright_terms": license_terms.get("copyright_terms"),
        "cancellation_policy_snapshot": policies.get("cancellation"),
        "reschedule_policy_snapshot": policies.get("reschedule"),
        "deliverables": deliverables,
        "payment_mode": snapshot.get("payment_mode") or "full",
        "deposit_rate": _money(snapshot.get("deposit_rate") or 0.30),
        "fulfillment_mode": snapshot.get("fulfillment_mode") or "single_delivery",
        "contract_snapshot": snapshot,
    }
