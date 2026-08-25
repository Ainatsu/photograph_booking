"""Weather provider boundary for shoot context."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import httpx

from backend.app.core.cache import cache_get, cache_set
from backend.app.core.config import settings


class WeatherProviderError(RuntimeError):
    """天气服务提供方错误。"""
    pass


class ForecastUnavailable(WeatherProviderError):
    """目标日期超出可预报范围或该地点无有效预报。"""
    pass


MAX_FORECAST_DAYS = 16


class OpenMeteoWeatherProvider:
    """仅封装 HTTP 调用，业务层的数据归一化由 WeatherService 负责。"""

    endpoint = "https://api.open-meteo.com/v1/forecast"

    async def forecast(self, latitude: float, longitude: float, shoot_date: date) -> dict[str, Any]:
        """调用 Open-Meteo 接口获取单日天气原始数据。"""
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": "temperature_2m,precipitation_probability,cloud_cover,wind_speed_10m,visibility",
            "daily": "sunrise,sunset",
            "timezone": "auto",
            "start_date": shoot_date.isoformat(),
            "end_date": shoot_date.isoformat(),
        }
        try:
            async with httpx.AsyncClient(timeout=settings.MAP_WEATHER_TIMEOUT_SECONDS) as client:
                response = await client.get(self.endpoint, params=params)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in {400, 404}:
                raise ForecastUnavailable from exc
            raise WeatherProviderError from exc
        except (httpx.TimeoutException, httpx.RequestError) as exc:
            raise WeatherProviderError from exc


class WeatherService:
    """校验、缓存并归一化单日天气预报。"""

    def __init__(self, provider: Any | None = None):
        """初始化服务并指定天气数据提供方。"""
        self.provider = provider or OpenMeteoWeatherProvider()

    async def forecast(self, latitude: float, longitude: float, shoot_date: date) -> dict[str, Any]:
        """校验日期范围，带缓存地获取并归一化天气预报。"""
        # Open-Meteo 在此时间窗外无法提供有效的逐小时预报，提前返回明确错误。
        if shoot_date < date.today() or shoot_date > date.today() + timedelta(days=MAX_FORECAST_DAYS):
            raise ForecastUnavailable
        key = f"shoot-weather:{latitude:.4f}:{longitude:.4f}:{shoot_date.isoformat()}"
        cached = cache_get(key)
        if cached is not None:
            return cached
        payload = await self.provider.forecast(latitude, longitude, shoot_date)
        result = self._normalize(payload)
        cache_set(key, result, settings.MAP_WEATHER_CACHE_TTL_SECONDS)
        return result

    @staticmethod
    def _normalize(payload: dict[str, Any]) -> dict[str, Any]:
        """将供应商原始响应归一化为逐小时天气数据。"""
        # 供应商返回多组并行数组；转换为逐小时对象，避免调用方错配不同时段的数据。
        hourly = payload.get("hourly") or {}
        times = hourly.get("time") or []
        fields = {
            "temperature_c": hourly.get("temperature_2m") or [],
            "precipitation_probability": hourly.get("precipitation_probability") or [],
            "cloud_cover": hourly.get("cloud_cover") or [],
            "wind_kph": hourly.get("wind_speed_10m") or [],
            "visibility_km": [float(value) / 1000 if value is not None else None for value in (hourly.get("visibility") or [])],
        }
        rows = []
        for index, raw_time in enumerate(times):
            time = str(raw_time).split("T")[-1][:5]
            # 单项指标可能缺失，而其他数组仍正常返回；缺失位置用 None 表示。
            rows.append({
                "time": time,
                **{name: values[index] if index < len(values) else None for name, values in fields.items()},
            })
        daily = payload.get("daily") or {}
        sunrise = (daily.get("sunrise") or [None])[0]
        sunset = (daily.get("sunset") or [None])[0]
        return {
            "timezone": payload.get("timezone") or settings.PLATFORM_TIMEZONE,
            "hourly": rows,
            "sunrise": str(sunrise).split("T")[-1][:5] if sunrise else None,
            "sunset": str(sunset).split("T")[-1][:5] if sunset else None,
            "provider": "open_meteo",
        }
