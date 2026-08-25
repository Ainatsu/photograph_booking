"""身份验证相关 API 路由。"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.schemas.auth import (
    VerificationConfirmRequest,
    VerificationConfirmResponse,
    VerificationRequest,
    VerificationRequestResponse,
)
from backend.app.services.verification_service import VerificationError, confirm_challenge, request_challenge

router = APIRouter(prefix="/auth", tags=["身份验证"])


@router.post("/verifications/request", response_model=VerificationRequestResponse)
def request_verification(data: VerificationRequest, db: Session = Depends(get_db)):
    """请求发送验证码，返回验证挑战信息。"""
    try:
        challenge, masked = request_challenge(db, channel=data.channel, target=data.target, purpose=data.purpose)
    except VerificationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.detail) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return VerificationRequestResponse(
        challenge_id=challenge.id,
        masked_target=masked,
        expires_in=settings.VERIFICATION_CODE_TTL_SECONDS,
    )


@router.post("/verifications/confirm", response_model=VerificationConfirmResponse)
def confirm_verification(data: VerificationConfirmRequest, db: Session = Depends(get_db)):
    """校验验证码，返回验证令牌。"""
    try:
        token = confirm_challenge(db, challenge_id=data.challenge_id, code=data.code)
    except VerificationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.detail) from exc
    return VerificationConfirmResponse(
        verification_token=token,
        expires_in=settings.VERIFICATION_TOKEN_TTL_SECONDS,
    )
