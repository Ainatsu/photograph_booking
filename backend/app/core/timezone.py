"""
时区与 ISO 时间格式化工具
"""
import re
from datetime import datetime, timezone
from typing import Any

from fastapi.responses import JSONResponse


_ISO_DATETIME = re.compile(
    r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?$"
)


def isoformat_utc(value: datetime | None) -> str | None:
    """将 datetime 转为 UTC 的 ISO 格式字符串，无值时返回 None"""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat().replace("+00:00", "Z")


def _is_datetime_key(key: str) -> bool:
    """判断键名是否为时间字段"""
    return key.endswith(("_at", "_time", "_start", "_end"))


def _iso_string_to_utc(value: str) -> str | None:
    """将 ISO 时间字符串规范化为 UTC 格式，无法解析时返回 None"""
    if not _ISO_DATETIME.match(value):
        return None

    normalized = value.replace(" ", "T", 1)
    parse_value = normalized[:-1] + "+00:00" if normalized.endswith("Z") else normalized
    try:
        parsed = datetime.fromisoformat(parse_value)
    except ValueError:
        return None
    return isoformat_utc(parsed)


def _with_utc_timezone(value: Any, key: str | None = None) -> Any:
    """递归将数据中的 datetime 与时间字段统一转为 UTC 格式"""
    if isinstance(value, datetime):
        return isoformat_utc(value)

    if isinstance(value, dict):
        return {
            item_key: _with_utc_timezone(item_value, str(item_key))
            for item_key, item_value in value.items()
        }

    if isinstance(value, list):
        return [_with_utc_timezone(item) for item in value]

    if key and isinstance(value, str) and _is_datetime_key(key):
        return _iso_string_to_utc(value) or value

    return value


class UTCJSONResponse(JSONResponse):
    """将响应内容中的时间字段统一转为 UTC 格式的 JSON 响应"""

    def render(self, content: Any) -> bytes:
        """渲染响应体，自动转换其中的时间字段"""
        return super().render(_with_utc_timezone(content))
