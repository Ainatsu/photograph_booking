"""
用户系统 API 路由

提供用户注册、登录、个人信息查看与更新功能。
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from backend.app.schemas.user import ChangePasswordRequest, UserUpdateRequest, UsernameUpdateRequest
from backend.app.schemas.auth import BindingConfirmRequest, BindingRequest
from backend.app.core.database import get_db
from backend.app.core.security import create_access_token
from backend.app.models.user import User
from backend.app.schemas.user import (
    UserRegisterRequest,
    UserResponse,
    TokenResponse,
    UsernameAvailabilityResponse,
)
from backend.app.services.user_service import (
    create_user,
    get_user_by_email,
    authenticate_user, change_password, logout_all_devices, register_verified_phone_user, update_user
)
from backend.app.api.deps import get_current_active_user
from backend.app.services.user_service import create_user as create_user_svc
from backend.app.utils.file_upload import save_upload_file
from backend.app.services.identity_service import username_availability, IdentityValidationError
from backend.app.services.verification_service import VerificationError, confirm_challenge, get_consumable_challenge, request_challenge

router = APIRouter(prefix="/users", tags=["用户系统"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="用户注册",
    description="创建新用户账号。新用户默认都是客户；成为摄影师需要提交申请并通过管理员审核。",
    response_description="注册成功，返回新创建的用户信息",
)
def register(request: UserRegisterRequest, db: Session = Depends(get_db)):
    """创建新用户账号"""
    try:
        return register_verified_phone_user(
        db,
        username=request.username,
        password=request.password,
        display_name=request.display_name,
        phone_verification_token=request.phone_verification_token,
        email=str(request.email) if request.email else None,
        )
    except (VerificationError, IdentityValidationError) as exc:
        raise HTTPException(status_code=400, detail=exc.detail) from exc


@router.get("/username-availability", response_model=UsernameAvailabilityResponse)
def check_username_availability(username: str, db: Session = Depends(get_db)):
    """检查用户名是否可用"""
    normalized, available, reason = username_availability(db, username)
    return UsernameAvailabilityResponse(
        normalized_username=normalized,
        available=available,
        reason=reason,
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="用户登录",
    description="使用邮箱和密码登录，成功返回 JWT 访问令牌。令牌需在后续请求的 Authorization 头中以 Bearer 方式携带。",
    response_description="登录成功，返回 JWT 访问令牌",
)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """用户登录，校验密码并签发 JWT 令牌"""
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="邮箱或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={
        "sub": str(user.id), "role": user.role, "is_admin": user.is_admin,
        "ver": user.token_version or 0,
    })
    return TokenResponse(access_token=access_token)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="获取当前用户信息",
    description="返回当前登录用户的详细资料，包括昵称、头像、角色等信息。",
    response_description="当前登录用户的完整信息",
)
def get_me(current_user: User = Depends(get_current_active_user)):
    """返回当前登录用户的详细信息"""
    return current_user


@router.patch(
    "/me",
    response_model=UserResponse,
    summary="更新个人资料",
    description="更新当前登录用户的个人资料。所有字段均为可选，仅更新传入的字段。",
    response_description="更新后的用户信息",
)
def update_me(
    data: UserUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """更新当前登录用户的个人资料"""
    user = update_user(
        db, current_user,
        display_name=data.display_name,
        bio=data.bio,
        avatar_url=data.avatar_url,
        show_email_on_profile=data.show_email_on_profile,
    )
    return user


@router.patch("/me/username", response_model=UserResponse)
def update_my_username(
    data: UsernameUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """修改用户名（当前策略为注册后不可修改）"""
    raise HTTPException(status_code=403, detail="用户名在注册后不可修改")


@router.post("/me/change-password")
def change_my_password(
    data: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """修改当前用户的登录密码"""
    try:
        change_password(db, current_user, data.current_password, data.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"message": "密码已修改，请重新登录"}


@router.post("/me/logout-all")
def logout_all(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """使当前用户在所有设备上退出登录"""
    logout_all_devices(db, current_user)
    return {"message": "已退出全部设备"}


@router.post("/me/phone/request")
def request_phone_binding(
    data: BindingRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """发起绑定手机号的验证请求"""
    try:
        challenge, masked = request_challenge(db, channel="phone", target=data.target, purpose="bind_phone", user_id=current_user.id)
    except (VerificationError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"challenge_id": challenge.id, "masked_target": masked, "expires_in": 300}


@router.post("/me/phone/confirm", response_model=UserResponse)
def confirm_phone_binding(
    data: BindingConfirmRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """确认验证码并完成手机号绑定"""
    try:
        challenge = get_consumable_challenge(db, data.verification_token, channel="phone", purpose="bind_phone")
        if challenge.user_id != current_user.id:
            raise VerificationError("验证令牌无效", "invalid_token")
        current_user.phone = challenge.target
        current_user.phone_verified_at = datetime.now(timezone.utc)
        challenge.consumed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(current_user)
        return current_user
    except VerificationError as exc:
        raise HTTPException(status_code=400, detail=exc.detail) from exc


@router.post("/me/email/request")
def request_email_binding(
    data: BindingRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """发起绑定邮箱的验证请求"""
    try:
        challenge, masked = request_challenge(db, channel="email", target=data.target, purpose="bind_email", user_id=current_user.id)
    except (VerificationError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"challenge_id": challenge.id, "masked_target": masked, "expires_in": 300}


@router.post("/me/email/confirm", response_model=UserResponse)
def confirm_email_binding(
    data: BindingConfirmRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """确认验证码并完成邮箱绑定"""
    try:
        challenge = get_consumable_challenge(db, data.verification_token, channel="email", purpose="bind_email")
        if challenge.user_id != current_user.id:
            raise VerificationError("验证令牌无效", "invalid_token")
        current_user.email = challenge.target
        current_user.email_verified_at = datetime.now(timezone.utc)
        current_user.pending_email = None
        challenge.consumed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(current_user)
        return current_user
    except VerificationError as exc:
        raise HTTPException(status_code=400, detail=exc.detail) from exc


@router.post(
    "/me/avatar",
    response_model=UserResponse,
    summary="上传头像",
    description="上传用户头像图片，支持常见图片格式。上传成功后自动更新用户头像 URL。",
    response_description="更新头像后的用户信息",
)
async def upload_avatar(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """上传用户头像并更新头像 URL"""
    url = await save_upload_file(file, sub_dir="avatars")
    user = update_user(db, current_user, avatar_url=url)
    return user


@router.post(
    "/me/background",
    response_model=UserResponse,
    summary="上传个人主页背景图",
    description="上传用户个人主页的背景图片，支持常见图片格式。上传成功后自动更新背景图 URL。",
    response_description="更新背景图后的用户信息",
)
async def upload_background(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """上传个人主页背景图并更新背景图 URL"""
    url = await save_upload_file(file, sub_dir="backgrounds")
    user = update_user(db, current_user, background_url=url)
    return user
