"""API 依赖注入：认证令牌解析与当前用户获取。"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/users/login")
oauth2_scheme_optional = OAuth2PasswordBearer(
    tokenUrl="/api/v1/users/login",
    auto_error=False,
)


def _decode_user_from_token(token: str, db: Session) -> User:
    """解码 JWT 令牌并查询返回对应用户，校验失败时抛出 401 异常。"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError as exc:
        raise credentials_exception from exc

    try:
        normalized_user_id = int(user_id)
    except (TypeError, ValueError) as exc:
        raise credentials_exception from exc

    user = db.query(User).filter(User.id == normalized_user_id).first()
    if user is None:
        raise credentials_exception
    if settings.TOKEN_VERSION_ENFORCEMENT_ENABLED:
        token_version = payload.get("ver", 0)
        if token_version != (user.token_version or 0):
            raise credentials_exception
    return user


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """获取当前登录用户。"""
    return _decode_user_from_token(token, db)


def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """获取当前活跃用户，账号被禁用时抛出异常。"""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="账号已被禁用")
    return current_user


def get_current_active_user_optional(
    token: str | None = Depends(oauth2_scheme_optional),
    db: Session = Depends(get_db),
) -> User | None:
    """可选地获取当前活跃用户，无令牌时返回 None。"""
    if not token:
        return None

    user = _decode_user_from_token(token, db)
    if not user.is_active:
        raise HTTPException(status_code=400, detail="账号已被禁用")
    return user
