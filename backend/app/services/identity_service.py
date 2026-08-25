"""用户身份标识（邮箱、用户名、手机号）的规范化与校验服务。"""

from __future__ import annotations

import re
from dataclasses import dataclass

from email_validator import EmailNotValidError, validate_email
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.models.user import User

try:
    import phonenumbers
except ImportError:  # 允许迁移或最小测试环境先运行；生产依赖已写入 requirements.txt
    phonenumbers = None


USERNAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{3,23}$")
PHONE_INPUT_PATTERN = re.compile(r"^[0-9+()\-\s]{6,}$")
RESERVED_USERNAMES = {
    "admin",
    "administrator",
    "root",
    "system",
    "support",
    "official",
    "api",
    "auth",
    "login",
    "logout",
    "register",
    "me",
    "users",
    "photographers",
    "null",
    "undefined",
}


class IdentityValidationError(ValueError):
    """身份校验失败异常，携带错误码。"""

    def __init__(self, detail: str, code: str = "invalid") -> None:
        """初始化异常详情与错误码。"""
        super().__init__(detail)
        self.detail = detail
        self.code = code


@dataclass(frozen=True)
class ResolvedIdentifier:
    """登录标识的分类结果（类型 + 规范化值）。"""

    kind: str
    normalized: str


def normalize_email(value: str) -> str:
    """规范化邮箱：去空白、转小写并校验格式。"""
    raw = (value or "").strip().lower()
    if not raw:
        raise IdentityValidationError("邮箱不能为空", "empty")
    try:
        result = validate_email(raw, check_deliverability=False)
    except EmailNotValidError as exc:
        raise IdentityValidationError("邮箱格式不正确", "invalid_format") from exc
    return result.normalized.strip().lower()


def normalize_username(value: str) -> str:
    """规范化用户名：去空白并去掉开头的 @。"""
    return (value or "").strip().removeprefix("@").lower()


def validate_username(value: str) -> str:
    """校验用户名格式与保留名单，返回规范化结果。"""
    normalized = normalize_username(value)
    if not USERNAME_PATTERN.fullmatch(normalized):
        raise IdentityValidationError(
            "用户 ID 需为 4-24 位，以英文字母开头，仅包含小写字母、数字和下划线",
            "invalid_format",
        )
    compact = normalized.replace("_", "")
    if normalized in RESERVED_USERNAMES or compact in RESERVED_USERNAMES:
        raise IdentityValidationError("该用户 ID 为系统保留名称", "reserved")
    return normalized


def _fallback_normalize_phone(value: str, region: str) -> str:
    """无 phonenumbers 库时的手机号规范化回退实现。"""
    compact = re.sub(r"[()\-\s]", "", value)
    if compact.startswith("+") and compact[1:].isdigit() and 8 <= len(compact[1:]) <= 15:
        return compact
    digits = re.sub(r"\D", "", compact)
    if region.upper() == "CN" and len(digits) == 11 and digits.startswith("1"):
        return f"+86{digits}"
    if region.upper() == "HK" and len(digits) == 8:
        return f"+852{digits}"
    raise IdentityValidationError("手机号格式不正确", "invalid_format")


def normalize_phone(value: str, default_region: str | None = None) -> str:
    """规范化手机号为 E.164 格式（可指定默认区号）。"""
    raw = (value or "").strip()
    if not raw:
        raise IdentityValidationError("手机号不能为空", "empty")
    region = (default_region or settings.DEFAULT_PHONE_REGION or "CN").upper()
    if phonenumbers is None:
        return _fallback_normalize_phone(raw, region)
    try:
        parsed = phonenumbers.parse(raw, None if raw.startswith("+") else region)
    except phonenumbers.NumberParseException as exc:
        raise IdentityValidationError("手机号格式不正确", "invalid_format") from exc
    if not phonenumbers.is_valid_number(parsed):
        raise IdentityValidationError("手机号格式不正确", "invalid_format")
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


def looks_like_phone(value: str) -> bool:
    """粗略判断输入是否像手机号。"""
    raw = (value or "").strip()
    return raw.startswith("+") or bool(PHONE_INPUT_PATTERN.fullmatch(raw))


def classify_login_identifier(identifier: str) -> ResolvedIdentifier:
    """将登录输入分类为邮箱、手机号或用户名并规范化。"""
    raw = (identifier or "").strip()
    # A leading @ is the public-username presentation form; only other @
    # positions indicate an email address.
    if "@" in raw and not raw.startswith("@"):
        return ResolvedIdentifier("email", normalize_email(raw))
    if looks_like_phone(raw):
        return ResolvedIdentifier("phone", normalize_phone(raw))
    return ResolvedIdentifier("username", normalize_username(raw))


def resolve_login_identifier(db: Session, identifier: str) -> User | None:
    """按分类结果查找对应已校验的用户。"""
    try:
        resolved = classify_login_identifier(identifier)
    except IdentityValidationError:
        return None

    if resolved.kind == "email":
        return (
            db.query(User)
            .filter(User.email == resolved.normalized, User.email_verified_at.is_not(None))
            .first()
        )
    if resolved.kind == "phone":
        return (
            db.query(User)
            .filter(User.phone == resolved.normalized, User.phone_verified_at.is_not(None))
            .first()
        )
    return db.query(User).filter(User.username == resolved.normalized).first()


def username_availability(db: Session, value: str) -> tuple[str, bool, str | None]:
    """检查用户名可用性，返回 (规范化名, 是否可用, 原因)。"""
    normalized = normalize_username(value)
    try:
        normalized = validate_username(normalized)
    except IdentityValidationError as exc:
        return normalized, False, exc.code
    exists = db.query(User.id).filter(User.username == normalized).first() is not None
    return normalized, not exists, "taken" if exists else None
