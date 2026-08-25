"""用户服务：用户的创建、资料更新、密码与登录态管理。"""

from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from backend.app.models.user import User
from backend.app.core.security import hash_password, validate_password, verify_password
from backend.app.services.identity_service import normalize_email, resolve_login_identifier, validate_username
from backend.app.services.verification_service import VerificationError, get_consumable_challenge

def create_user(db: Session, email: str, phone: str | None, password: str, display_name: str, role: str) -> User:
    """创建新用户并保存到数据库。"""
    # Keep this legacy service compatible with existing callers; the Phase A
    # migration normalizes persisted legacy addresses, while new registration
    # validation will normalize before calling this helper.
    normalized_email = email.strip() if email else None
    user = User(
        email=normalized_email,
        email_verified_at=datetime.now(timezone.utc) if normalized_email else None,
        phone=phone,
        hashed_password=hash_password(password),
        display_name=display_name,
        role=role
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def get_user_by_email(db: Session, email: str) -> User | None:
    """按邮箱查询用户。"""
    return db.query(User).filter(User.email == email).first()

def authenticate_user(db: Session, identifier: str, password: str) -> User | None:
    """Authenticate by verified email, verified phone, or public username.

    All lookup failures intentionally collapse to ``None`` so the API can
    return one indistinguishable invalid-credentials response.
    """
    user = resolve_login_identifier(db, identifier)
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user

def update_user(db: Session, user: User, display_name=None, phone=None, bio=None, avatar_url=None, background_url=None, show_email_on_profile=None) -> User:
    """更新用户资料，必要时刷新 AI 资源索引。"""
    should_refresh_ai_index = False
    if display_name is not None:
        user.display_name = display_name
        should_refresh_ai_index = True
    # Kept for legacy internal callers; the public API no longer forwards
    # direct phone edits and requires verification endpoints instead.
    if phone is not None:
        user.phone = phone
    if bio is not None:
        user.bio = bio
        should_refresh_ai_index = True
    if avatar_url is not None:
        user.avatar_url = avatar_url
        should_refresh_ai_index = True
    if background_url is not None:
        user.background_url = background_url
    if show_email_on_profile is not None:
        user.show_email_on_profile = bool(show_email_on_profile) and bool(user.email_verified)
    db.commit()
    db.refresh(user)
    if should_refresh_ai_index and user.role == "photographer":
        from backend.app.services.ai_resource_index_service import refresh_ai_resource_documents_for_user
        refresh_ai_resource_documents_for_user(db, user.id)
    return user


def update_username(db: Session, user: User, username: str) -> User:
    """修改用户 ID，校验唯一性与修改频率。"""
    normalized = validate_username(username)
    if normalized == user.username:
        return user
    if user.username_changed_at and not user.username_requires_update:
        elapsed = datetime.now(timezone.utc) - user.username_changed_at.replace(tzinfo=timezone.utc)
        if elapsed.total_seconds() < 30 * 24 * 3600:
            raise ValueError("用户 ID 每 30 天只能修改一次")
    if db.query(User.id).filter(User.username == normalized, User.id != user.id).first():
        raise ValueError("该用户 ID 已被占用")
    user.username = normalized
    user.username_requires_update = False
    user.username_changed_at = datetime.now(timezone.utc)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ValueError("该用户 ID 已被占用") from exc
    db.refresh(user)
    return user


def change_password(db: Session, user: User, current_password: str, new_password: str) -> User:
    """校验旧密码后更新密码并作废已有令牌。"""
    if not verify_password(current_password, user.hashed_password):
        raise ValueError("当前密码不正确")
    if verify_password(new_password, user.hashed_password):
        raise ValueError("新密码不能与当前密码相同")
    validate_password(new_password)
    user.hashed_password = hash_password(new_password)
    user.password_changed_at = datetime.now(timezone.utc)
    user.token_version = (user.token_version or 0) + 1
    db.commit()
    db.refresh(user)
    return user


def logout_all_devices(db: Session, user: User) -> User:
    """提升令牌版本，使已签发的令牌全部失效。"""
    user.token_version = (user.token_version or 0) + 1
    db.commit()
    db.refresh(user)
    return user


_IDENTITY_UNIQUE_HINTS = (
    "users.username",
    "uq_users_username",
    "users.phone",
    "uq_users_phone",
)


def _is_identity_unique_conflict(exc: IntegrityError) -> bool:
    """Tell a real username/phone collision apart from any other DB failure.

    Blanket-mapping IntegrityError to "identity taken" hides schema drift (for
    example a legacy ``NOT NULL`` on ``users.email``) behind a wrong 400, so
    anything we cannot attribute to those unique indexes must keep propagating.
    """
    message = str(getattr(exc, "orig", exc)).lower()
    if "unique" not in message and "duplicate" not in message:
        return False
    return any(hint in message for hint in _IDENTITY_UNIQUE_HINTS)


def register_verified_phone_user(
    db: Session,
    *,
    username: str,
    display_name: str,
    password: str,
    phone_verification_token: str | None = None,
    email: str | None = None,
) -> User:
    """通过手机号验证令牌注册并创建用户。"""
    normalized_username = validate_username(username)
    pending_email = normalize_email(email) if email else None
    challenge = None
    if phone_verification_token:
        challenge = get_consumable_challenge(
            db, phone_verification_token, channel="phone", purpose="register"
        )
    if db.query(User.id).filter(User.username == normalized_username).first():
        raise VerificationError("该用户 ID 已被占用", "username_conflict")
    if challenge and db.query(User.id).filter(User.phone == challenge.target).first():
        raise VerificationError("该手机号已被注册", "phone_conflict")
    now = datetime.now(timezone.utc)
    user = User(
        username=normalized_username,
        username_requires_update=False,
        phone=challenge.target if challenge else None,
        phone_verified_at=now if challenge else None,
        email=None,
        pending_email=pending_email,
        email_verified_at=None,
        hashed_password=hash_password(password),
        display_name=display_name,
        role="customer",
    )
    db.add(user)
    if challenge:
        challenge.consumed_at = now
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if _is_identity_unique_conflict(exc):
            raise VerificationError("用户名或手机号已被使用", "identity_conflict") from exc
        raise
    db.refresh(user)
    return user
