"""
安全相关工具：密码校验、哈希与 JWT 令牌
"""
import bcrypt
import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from .config import settings


MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_BYTES = 72


def validate_password(password: str) -> None:
    """校验密码长度与字节数，不合法时抛出 ValueError"""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError("密码至少需要 8 个字符")
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError("密码过长，请控制在 72 个 UTF-8 字节以内")

def hash_password(password: str) -> str:
    """将明文密码加密为哈希值"""
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError("密码过长，请控制在 72 个 UTF-8 字节以内")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码是否匹配"""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8")
        )
    except (ValueError, TypeError):
        return False

def create_access_token(data: dict) -> str:
    """生成 JWT 访问令牌"""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"iat": int(now.timestamp()), "exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def verify_access_token(token: str) -> dict | None:
    """验证 JWT 并返回 payload，失败返回 None"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None


def hash_verification_code(challenge_id: str, code: str) -> str:
    """用 HMAC-SHA256 生成验证码的哈希值"""
    message = f"{challenge_id}:{code}".encode("utf-8")
    return hmac.new(settings.SECRET_KEY.encode("utf-8"), message, hashlib.sha256).hexdigest()


def verify_verification_code(challenge_id: str, code: str, code_hash: str) -> bool:
    """校验验证码哈希是否与期望值匹配"""
    expected = hash_verification_code(challenge_id, code)
    return hmac.compare_digest(expected, code_hash)


def create_verification_token(*, challenge_id: str, channel: str, target: str, purpose: str) -> str:
    """生成身份验证用的 JWT 令牌"""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(seconds=settings.VERIFICATION_TOKEN_TTL_SECONDS)
    payload = {
        "sub": challenge_id,
        "typ": "identity_verification",
        "channel": channel,
        "target": target,
        "purpose": purpose,
        "iat": int(now.timestamp()),
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def verify_verification_token(token: str) -> dict | None:
    """验证身份验证令牌并返回 payload，无效时返回 None"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None
    if payload.get("typ") != "identity_verification" or not payload.get("sub"):
        return None
    return payload
