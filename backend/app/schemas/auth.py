"""账号验证与绑定相关 Schema 定义"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


VerificationChannel = Literal["phone", "email"]
VerificationPurpose = Literal[
    "register", "bind_phone", "bind_email", "change_phone", "change_email", "reset_password"
]


class VerificationRequest(BaseModel):
    """发送验证码请求"""

    channel: VerificationChannel
    target: str = Field(min_length=3, max_length=255)
    purpose: VerificationPurpose


class VerificationRequestResponse(BaseModel):
    """发送验证码响应"""

    challenge_id: str
    masked_target: str
    expires_in: int


class VerificationConfirmRequest(BaseModel):
    """校验验证码请求"""

    challenge_id: str
    code: str = Field(min_length=4, max_length=10)


class VerificationConfirmResponse(BaseModel):
    """校验验证码响应"""

    verification_token: str
    expires_in: int


class BindingRequest(BaseModel):
    """绑定新联系方式请求"""

    target: str = Field(min_length=3, max_length=255)


class BindingConfirmRequest(BaseModel):
    """确认绑定请求"""

    verification_token: str = Field(min_length=20)
