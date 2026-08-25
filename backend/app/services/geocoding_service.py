"""Geocoding provider boundary for shoot context.

Only the normalized place fields leave this module. Provider payloads never enter
the AI prompt or message metadata.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from backend.app.core.cache import cache_get, cache_set
from backend.app.core.config import settings


@dataclass(frozen=True)
class PlaceCandidate:
    """标准化的地点候选结构。"""

    name: str
    address: str
    latitude: float
    longitude: float
    coordinate_system: str = "WGS84"
    provider: str = "open_meteo_geocoding"
    feature_code: str | None = None
    country_code: str | None = None
    admin1: str | None = None
    admin2: str | None = None
    population: int | None = None

    def as_dict(self) -> dict[str, Any]:
        """将地点候选序列化为字典。"""
        return {
            "name": self.name,
            "address": self.address,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "coordinate_system": self.coordinate_system,
            "provider": self.provider,
            "feature_code": self.feature_code,
            "country_code": self.country_code,
            "admin1": self.admin1,
            "admin2": self.admin2,
            "population": self.population,
        }


class OpenMeteoGeocodingProvider:
    """将供应商特有的搜索结果转换为稳定的地点候选结构。"""

    endpoint = "https://geocoding-api.open-meteo.com/v1/search"

    async def search(self, query: str) -> list[PlaceCandidate]:
        """调用地理编码接口查询地点并返回候选列表。"""
        params = {"name": query, "count": 5, "language": "zh", "format": "json"}
        async with httpx.AsyncClient(timeout=settings.MAP_WEATHER_TIMEOUT_SECONDS) as client:
            response = await client.get(self.endpoint, params=params)
            response.raise_for_status()
            payload = response.json()
        return [self._normalize(item) for item in payload.get("results", []) if self._valid(item)]

    @staticmethod
    def _valid(item: dict[str, Any]) -> bool:
        """判断搜索结果是否包含有效坐标。"""
        return isinstance(item, dict) and item.get("latitude") is not None and item.get("longitude") is not None

    @staticmethod
    def _normalize(item: dict[str, Any]) -> PlaceCandidate:
        """将供应商结果归一化为地点候选。"""
        # 保留供应商返回的行政区层级，同时去掉城市名与行政区名相同等重复项。
        name = str(item.get("name") or item.get("admin1") or "未知地点")
        admin1 = str(item.get("admin1")) if item.get("admin1") else None
        admin2 = str(item.get("admin2")) if item.get("admin2") else None
        parts = [name, admin2, admin1, item.get("country")]
        address = ", ".join(dict.fromkeys(str(part) for part in parts if part))
        population = item.get("population")
        return PlaceCandidate(
            name=name,
            address=address,
            latitude=float(item["latitude"]),
            longitude=float(item["longitude"]),
            feature_code=str(item.get("feature_code")) if item.get("feature_code") else None,
            country_code=str(item.get("country_code")) if item.get("country_code") else None,
            admin1=admin1,
            admin2=admin2,
            population=int(population) if isinstance(population, (int, float)) else None,
        )


class GeocodingService:
    """解析用户输入的地点文本，并缓存规范化后的短期结果。"""

    def __init__(self, provider: Any | None = None):
        """初始化地理编码服务，默认使用 Open-Meteo Provider。"""
        self.provider = provider or OpenMeteoGeocodingProvider()

    async def resolve(self, location_text: str) -> list[PlaceCandidate]:
        """解析地点文本并返回候选，优先命中缓存。"""
        # 合并空白并统一大小写，避免语义相同的查询占用多个缓存条目。
        normalized = " ".join(location_text.strip().split()).lower()
        # v2 retains administrative type and population for deterministic ranking.
        key = f"shoot-geocode:v2:{normalized}"
        cached = cache_get(key)
        if cached is not None:
            return [PlaceCandidate(**item) for item in cached]
        candidates = await self.provider.search(normalized)
        cache_set(key, [item.as_dict() for item in candidates], settings.MAP_WEATHER_CACHE_TTL_SECONDS)
        return candidates

    @staticmethod
    def preferred_candidate(
        location_text: str,
        candidates: list[PlaceCandidate],
    ) -> PlaceCandidate | None:
        """Select a clearly dominant administrative city while preserving real ambiguity."""
        if len(candidates) == 1:
            return candidates[0]
        query = " ".join(location_text.strip().lower().split())
        if not query:
            return None

        exact = [item for item in candidates if item.name.strip().lower() == query]
        if not exact:
            return None

        administrative_codes = {"PPLC", "PPLA", "PPLA2", "PPLA3"}
        administrative = [
            item for item in exact if (item.feature_code or "").upper() in administrative_codes
        ]
        if len(administrative) == 1:
            return administrative[0]

        ranked = sorted(exact, key=lambda item: item.population or 0, reverse=True)
        if not ranked or not ranked[0].population or ranked[0].population < 100_000:
            return None
        runner_up_population = ranked[1].population or 0 if len(ranked) > 1 else 0
        if ranked[0].population >= max(100_000, runner_up_population * 3):
            return ranked[0]
        return None
