"""验证码服务：发送、校验与消费邮箱/短信验证码及验证令牌。"""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.security import (
    create_verification_token,
    hash_verification_code,
    verify_verification_code,
    verify_verification_token,
)
from backend.app.models.identity_verification import IdentityVerificationChallenge
from backend.app.services.email_provider import get_email_provider
from backend.app.services.identity_service import normalize_email, normalize_phone
from backend.app.services.sms_provider import get_sms_provider


class VerificationError(ValueError):
    """验证相关异常，携带错误码。"""

    def __init__(self, detail: str, code: str = "invalid_verification") -> None:
        """初始化异常详情与错误码。"""
        super().__init__(detail)
        self.detail = detail
        self.code = code


def _utcnow() -> datetime:
    """返回当前 UTC 时间。"""
    return datetime.now(timezone.utc)


def _normalize(channel: str, target: str) -> str:
    """按渠道归一化手机号或邮箱。"""
    if channel == "phone":
        return normalize_phone(target)
    if channel == "email":
        return normalize_email(target)
    raise VerificationError("不支持的验证渠道", "invalid_channel")


def _mask(channel: str, target: str) -> str:
    """对手机号或邮箱做脱敏处理。"""
    if channel == "phone":
        return f"{target[:6]}****{target[-4:]}" if len(target) > 10 else f"{target[:3]}****{target[-2:]}"
    local, domain = target.split("@", 1)
    visible = local[:2] if len(local) > 2 else local[:1]
    return f"{visible}***@{domain}"


def request_challenge(db: Session, *, channel: str, target: str, purpose: str, user_id: int | None = None) -> tuple[IdentityVerificationChallenge, str]:
    """发起验证码挑战：生成验证码并发送，返回挑战与脱敏目标。"""
    normalized = _normalize(channel, target)
    now = _utcnow()
    resend_after = now - timedelta(seconds=settings.VERIFICATION_RESEND_INTERVAL_SECONDS)
    recent = (
        db.query(IdentityVerificationChallenge.id)
        .filter(
            IdentityVerificationChallenge.channel == channel,
            IdentityVerificationChallenge.target == normalized,
            IdentityVerificationChallenge.purpose == purpose,
            IdentityVerificationChallenge.created_at >= resend_after,
        )
        .first()
    )
    if recent:
        raise VerificationError("验证码发送过于频繁，请稍后再试", "rate_limited")

    code = f"{secrets.randbelow(1_000_000):06d}"
    challenge_id = str(uuid.uuid4())
    challenge = IdentityVerificationChallenge(
        id=challenge_id,
        channel=channel,
        target=normalized,
        purpose=purpose,
        code_hash=hash_verification_code(challenge_id, code),
        expires_at=now + timedelta(seconds=settings.VERIFICATION_CODE_TTL_SECONDS),
        max_attempts=settings.VERIFICATION_MAX_ATTEMPTS,
        user_id=user_id,
    )
    db.add(challenge)
    try:
        if channel == "phone":
            get_sms_provider().send_verification_code(normalized, code)
        else:
            get_email_provider().send_verification_code(normalized, code)
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(challenge)
    return challenge, _mask(channel, normalized)


def confirm_challenge(db: Session, *, challenge_id: str, code: str) -> str:
    """校验验证码，通过后返回验证令牌。"""
    challenge = db.query(IdentityVerificationChallenge).filter(IdentityVerificationChallenge.id == challenge_id).first()
    now = _utcnow()
    if not challenge or challenge.consumed_at or challenge.confirmed_at:
        raise VerificationError("验证码无效或已使用")
    expires_at = challenge.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= now:
        raise VerificationError("验证码已过期", "expired")
    if challenge.attempt_count >= challenge.max_attempts:
        raise VerificationError("验证码尝试次数过多", "attempts_exceeded")

    challenge.attempt_count += 1
    if not verify_verification_code(challenge.id, code, challenge.code_hash):
        db.commit()
        raise VerificationError("验证码错误", "invalid_code")

    challenge.confirmed_at = now
    db.commit()
    return create_verification_token(
        challenge_id=challenge.id,
        channel=challenge.channel,
        target=challenge.target,
        purpose=challenge.purpose,
    )


def get_consumable_challenge(db: Session, token: str, *, channel: str, purpose: str) -> IdentityVerificationChallenge:
    """校验令牌并返回可消费的验证挑战。"""
    payload = verify_verification_token(token)
    if not payload or payload.get("channel") != channel or payload.get("purpose") != purpose:
        raise VerificationError("验证令牌无效或已过期", "invalid_token")
    challenge = db.query(IdentityVerificationChallenge).filter(IdentityVerificationChallenge.id == payload["sub"]).first()
    if (
        not challenge
        or not challenge.confirmed_at
        or challenge.consumed_at
        or challenge.channel != channel
        or challenge.purpose != purpose
        or challenge.target != payload.get("target")
    ):
        raise VerificationError("验证令牌无效或已使用", "invalid_token")
    return challenge
