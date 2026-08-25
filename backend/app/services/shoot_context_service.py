"""Compose normalized place, forecast, sunlight and deterministic advice."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from math import acos, cos, pi, radians, sin, tan
from typing import Any

from backend.app.core.config import settings
from backend.app.services.ai_agent_decision_contracts import GetShootContextInput
from backend.app.services.geocoding_service import GeocodingService, PlaceCandidate
from backend.app.services.weather_service import ForecastUnavailable, WeatherProviderError, WeatherService


class ShootContextService:
    """构建供 AI 客户端消费的稳定拍摄上下文协议。"""

    def __init__(self, geocoding: GeocodingService | None = None, weather: WeatherService | None = None):
        """初始化服务，默认使用地理编码与天气服务的默认实现。"""
        self.geocoding = geocoding or GeocodingService()
        self.weather = weather or WeatherService()

    async def get_context(self, query: GetShootContextInput | dict[str, Any]) -> dict[str, Any]:
        """根据地点、日期与时段生成拍摄上下文（地点/天气/光照/建议）。"""
        input_data = query if isinstance(query, GetShootContextInput) else GetShootContextInput.model_validate(query)
        place, candidates = await self._resolve_place(input_data)
        # 多个匹配项交给调用方澄清；不自动猜测，避免返回错误城市的天气信息。
        if place is None:
            return {
                "schema_version": "shoot_context_v1",
                "status": "ambiguous" if candidates else "failed",
                "place": None,
                "weather": None,
                "sunlight": None,
                "recommendations": [],
                "place_candidates": [item.as_dict() for item in candidates],
                "error_code": "ambiguous_location" if candidates else "location_not_found",
            }

        base = {
            "schema_version": "shoot_context_v1",
            "status": "success",
            "place": place.as_dict(),
            "weather": None,
            "sunlight": None,
            "recommendations": [],
            "place_candidates": [],
            "error_code": None,
        }
        try:
            weather = await self.weather.forecast(place.latitude, place.longitude, input_data.shoot_date)
        except ForecastUnavailable:
            base["status"] = "partial"
            base["error_code"] = "forecast_unavailable"
            base["sunlight"] = self._fallback_sunlight(place.latitude, place.longitude, input_data.shoot_date)
            return base
        except WeatherProviderError:
            base["status"] = "partial"
            base["error_code"] = "weather_unavailable"
            base["sunlight"] = self._fallback_sunlight(place.latitude, place.longitude, input_data.shoot_date)
            return base
        except Exception:
            # 供应商实现可被替换，未知适配器异常也不应中断整个助手响应。
            base["status"] = "partial"
            base["error_code"] = "weather_unavailable"
            base["sunlight"] = self._fallback_sunlight(place.latitude, place.longitude, input_data.shoot_date)
            return base

        base["weather"] = {
            "timezone": weather.get("timezone") or settings.PLATFORM_TIMEZONE,
            "forecast_date": input_data.shoot_date.isoformat(),
            "hourly": self._select_hours(weather.get("hourly") or [], input_data),
            "provider": weather.get("provider") or "open_meteo",
            "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        }
        base["sunlight"] = self._sunlight(weather.get("sunrise"), weather.get("sunset"))
        base["recommendations"] = self._recommendations(base["weather"]["hourly"], base["sunlight"])
        return base

    async def _resolve_place(self, input_data: GetShootContextInput) -> tuple[PlaceCandidate | None, list[PlaceCandidate]]:
        """解析地点：坐标直用，文本地点必须唯一命中。"""
        # 地图选择的坐标视为可信输入，可跳过地理编码；文本地点必须唯一命中。
        if input_data.latitude is not None and input_data.longitude is not None:
            return PlaceCandidate(
                name=input_data.location_text,
                address=input_data.location_address or input_data.location_text,
                latitude=input_data.latitude,
                longitude=input_data.longitude,
                provider="provided_coordinates",
            ), []
        candidates = await self.geocoding.resolve(input_data.location_text)
        preferred = self.geocoding.preferred_candidate(input_data.location_text, candidates)
        if preferred is None:
            return None, candidates
        return preferred, []

    @staticmethod
    def _select_hours(rows: list[dict[str, Any]], query: GetShootContextInput) -> list[dict[str, Any]]:
        """只保留与用户拍摄时段重叠的预报数据。"""

        if not query.start_time:
            return rows[:24]
        start = datetime.strptime(query.start_time, "%H:%M")
        end = start + timedelta(minutes=query.duration_minutes)
        selected = []
        for row in rows:
            current = datetime.strptime(str(row.get("time")), "%H:%M")
            # 第二个分支处理跨午夜拍摄，因为供应商行中只有时刻而没有完整日期。
            if start <= current <= end or (end.day != start.day and (current >= start or current <= end - timedelta(days=1))):
                selected.append(row)
        return selected or rows[:24]

    @staticmethod
    def _sunlight(sunrise: str | None, sunset: str | None) -> dict[str, str | None]:
        """根据日出日落时间推导适合人像拍摄的光线窗口。"""

        if not sunrise or not sunset:
            return {"sunrise": sunrise, "sunset": sunset, "golden_hour_start": None, "golden_hour_end": None, "blue_hour_end": None}
        sunrise_dt = datetime.strptime(sunrise, "%H:%M")
        sunset_dt = datetime.strptime(sunset, "%H:%M")
        golden_start = sunset_dt - timedelta(minutes=45)
        blue_end = sunset_dt + timedelta(minutes=27)
        return {
            "sunrise": sunrise,
            "sunset": sunset,
            "golden_hour_start": golden_start.strftime("%H:%M"),
            "golden_hour_end": sunset,
            "blue_hour_end": blue_end.strftime("%H:%M"),
        }

    @staticmethod
    def _fallback_sunlight(latitude: float, longitude: float, shoot_date: date) -> dict[str, str | None]:
        """Calculate a bounded daylight estimate when forecast data is unavailable.

        This is only a sunlight fallback; it never fills weather values. Hong Kong's
        configured UTC+8 meridian is used for the platform's current timezone.
        """
        day_of_year = shoot_date.timetuple().tm_yday
        angle = 2 * pi * (day_of_year - 81) / 364
        equation_of_time = 9.87 * sin(2 * angle) - 7.53 * cos(angle) - 1.5 * sin(angle)
        declination = radians(23.44) * sin(radians(360 * (day_of_year - 81) / 365))
        latitude_radians = radians(latitude)
        try:
            hour_angle = acos(
                (cos(radians(90.833)) / (cos(latitude_radians) * cos(declination)))
                - tan(latitude_radians) * tan(declination)
            )
        except ValueError:
            return {"sunrise": None, "sunset": None, "golden_hour_start": None, "golden_hour_end": None, "blue_hour_end": None}
        time_offset = equation_of_time + 4 * longitude - 60 * 8
        solar_noon = 720 - time_offset
        sunrise_minutes = solar_noon - 4 * hour_angle * 180 / pi
        sunset_minutes = solar_noon + 4 * hour_angle * 180 / pi

        def format_minutes(value: float) -> str:
            normalized = int(round(value)) % (24 * 60)
            return f"{normalized // 60:02d}:{normalized % 60:02d}"

        sunrise = format_minutes(sunrise_minutes)
        sunset = format_minutes(sunset_minutes)
        sunset_dt = datetime.strptime(sunset, "%H:%M")
        return {
            "sunrise": sunrise,
            "sunset": sunset,
            "golden_hour_start": (sunset_dt - timedelta(minutes=45)).strftime("%H:%M"),
            "golden_hour_end": sunset,
            "blue_hour_end": (sunset_dt + timedelta(minutes=27)).strftime("%H:%M"),
        }

    @staticmethod
    def _recommendations(rows: list[dict[str, Any]], sunlight: dict[str, str | None]) -> list[dict[str, str]]:
        """根据明确阈值生成可复现的天气与安全建议。"""

        recommendations: list[dict[str, str]] = []
        rain = [row for row in rows if (row.get("precipitation_probability") or 0) >= 60]
        wind = [row for row in rows if (row.get("wind_kph") or 0) >= 25]
        heat = [row for row in rows if (row.get("temperature_c") or 0) >= 32]
        if rain:
            recommendations.append({"code": "rain_backup", "severity": "warning", "title": "准备室内备选", "detail": "查询时段降雨概率较高，建议准备防雨方案"})
        if wind:
            recommendations.append({"code": "wind_safety", "severity": "warning", "title": "注意风力", "detail": "固定灯架并留意发型、反光板和无人机安全"})
        if heat:
            recommendations.append({"code": "heat_breaks", "severity": "warning", "title": "安排补水与休息", "detail": "气温偏高，建议缩短连续拍摄并安排补水补妆"})
        if sunlight.get("golden_hour_start"):
            recommendations.append({"code": "golden_hour", "severity": "info", "title": "适合户外人像", "detail": f"日落前 {sunlight['golden_hour_start']}-{sunlight['golden_hour_end']} 是柔和光线窗口"})
        return recommendations
