"""
用户系统相关 Schema 定义

包含用户注册、登录、信息查看与更新的请求/响应模型。
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional


class UserRegisterRequest(BaseModel):
    """用户注册请求"""
    username: str = Field(..., min_length=4, max_length=24)
    phone_verification_token: Optional[str] = Field(None, min_length=20)
    email: Optional[EmailStr] = Field(None, description="可选邮箱，验证后才能用于登录")
    password: str = Field(
        ...,
        min_length=8,
        max_length=72,
        description="登录密码，至少 8 个字符且不超过 72 个 UTF-8 字节",
        example="Abc123456",
    )
    display_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="用户昵称 / 显示名称",
        example="摄影师小王",
    )


class UserLoginRequest(BaseModel):
    """用户登录请求"""
    email: EmailStr = Field(
        ...,
        description="登录邮箱",
        example="user@example.com",
    )
    password: str = Field(
        ...,
        description="登录密码",
        example="Abc123456",
    )


class UserResponse(BaseModel):
    """用户信息响应"""
    id: int = Field(..., description="用户唯一 ID", example=1)
    username: Optional[str] = None
    username_requires_update: bool = False
    email: Optional[str] = Field(None, description="已验证邮箱地址", example="user@example.com")
    pending_email: Optional[str] = None
    phone: Optional[str] = Field(None, description="手机号码", example="13800138000")
    email_verified: bool = False
    phone_verified: bool = False
    show_email_on_profile: bool = False
    display_name: str = Field(..., description="显示名称", example="摄影师小王")
    bio: Optional[str] = Field(None, description="个人简介", example="擅长人像摄影，5 年经验")
    avatar_url: Optional[str] = Field(
        None,
        description="头像图片 URL",
        example="/static/avatars/user_1.jpg",
    )
    background_url: Optional[str] = Field(
        None,
        description="个人主页背景图 URL",
        example="/static/backgrounds/user_1_bg.jpg",
    )
    role: str = Field(..., description="用户角色", example="photographer")
    is_active: bool = Field(..., description="账号是否激活", example=True)
    is_admin: bool = Field(False, description="是否为管理员", example=False)
    is_banned: bool = Field(False, description="是否被封禁", example=False)

    class Config:
        from_attributes = True


class UserUpdateRequest(BaseModel):
    """用户资料更新请求（所有字段可选，仅更新传入的字段）"""
    display_name: Optional[str] = Field(
        None,
        description="新的显示名称",
        example="摄影师小王（更新版）",
    )
    show_email_on_profile: Optional[bool] = Field(None, description="是否在摄影师公开主页展示已验证邮箱")
    bio: Optional[str] = Field(
        None,
        description="新的个人简介",
        example="专注婚礼摄影 10 年",
    )
    avatar_url: Optional[str] = Field(
        None,
        description="新的头像 URL",
        example="/static/avatars/user_1_new.jpg",
    )


class TokenResponse(BaseModel):
    """登录令牌响应"""
    access_token: str = Field(
        ...,
        description="JWT 访问令牌，后续请求需在 Authorization 头中携带",
        example="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    )
    token_type: str = Field(
        default="bearer",
        description="令牌类型，固定为 bearer",
        example="bearer",
    )


class UsernameAvailabilityResponse(BaseModel):
    """用户名可用性检查响应"""
    normalized_username: str
    available: bool
    reason: Optional[str] = None


class UsernameUpdateRequest(BaseModel):
    """用户名更新请求"""
    username: str = Field(..., min_length=4, max_length=24)


class ChangePasswordRequest(BaseModel):
    """修改密码请求"""
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=72)
