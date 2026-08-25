"""摄影师申请相关 API 路由。"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_active_user
from backend.app.core.database import get_db
from backend.app.models.user import User
from backend.app.schemas.photographer_application import (
    PhotographerApplicationResponse,
    PhotographerApplicationSubmit,
)
from backend.app.services.photographer_application_service import (
    get_application_by_user_id,
    serialize_application,
    submit_application,
)

router = APIRouter(prefix="/photographer-applications", tags=["摄影师申请"])


@router.get(
    "/me",
    response_model=PhotographerApplicationResponse | None,
    summary="查看我的摄影师申请",
)
def my_photographer_application(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """查看当前用户的摄影师申请。"""
    application = get_application_by_user_id(db, current_user.id)
    return serialize_application(application) if application else None


@router.post(
    "/me",
    response_model=PhotographerApplicationResponse,
    summary="提交摄影师申请",
)
def submit_my_photographer_application(
    data: PhotographerApplicationSubmit,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """提交当前用户的摄影师申请。"""
    application = submit_application(db, current_user, data)
    return serialize_application(application)
