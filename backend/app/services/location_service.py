"""Deterministic location helpers used by recommendations.

Coordinates are intentionally optional: when they are unavailable we keep the
candidate for city-level matching but never manufacture a precise distance.
"""

from __future__ import annotations

import math
from typing import Any


def validate_coordinates(latitude: float | None, longitude: float | None) -> tuple[float, float] | None:
    """校验经纬度范围，缺失时返回 None。"""
    if latitude is None or longitude is None:
        return None
    try:
        lat, lon = float(latitude), float(longitude)
    except (TypeError, ValueError):
        raise ValueError("无效的经纬度")
    if not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise ValueError("纬度必须在 -90..90，经度必须在 -180..180")
    return lat, lon


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """计算两点间的大圆距离（公里）。"""
    a = validate_coordinates(lat1, lon1)
    b = validate_coordinates(lat2, lon2)
    if a is None or b is None:
        raise ValueError("需要完整的经纬度")
    lat1_r, lon1_r, lat2_r, lon2_r = tuple(math.radians(v) for v in (*a, *b))
    dlat, dlon = lat2_r - lat1_r, lon2_r - lon1_r
    hav = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    return 6371.0088 * 2 * math.asin(math.sqrt(min(1.0, hav)))


def distance_label(distance_km: float | None) -> str:
    """将距离格式化为可读文案。"""
    if distance_km is None:
        return "同城，距离未知"
    return f"约 {distance_km:.1f} km"


def package_coordinates(package: dict[str, Any], profile: Any) -> tuple[float, float] | None:
    """从套餐或档案中提取首个有效的服务坐标。"""
    for source in (package, profile):
        coords = validate_coordinates(
            source.get("service_latitude") if isinstance(source, dict) else getattr(source, "service_latitude", None),
            source.get("service_longitude") if isinstance(source, dict) else getattr(source, "service_longitude", None),
        )
        if coords:
            return coords
    return None
