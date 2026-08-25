"""摄影师仪表盘 API。"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_active_user
from backend.app.core.database import get_db
from backend.app.models.user import User
from backend.app.schemas.photographer_dashboard import (
    PhotographerDashboardResponse,
    PhotographerPublicDashboardResponse,
)
from backend.app.services.photographer_dashboard_service import (
    get_photographer_dashboard,
    get_public_photographer_dashboard,
)

router = APIRouter(prefix="/orders", tags=["摄影师仪表盘"])


@router.get(
    "/dashboard",
    response_model=PhotographerDashboardResponse,
    summary="摄影师行动型仪表盘",
    description="聚合摄影师摘要、待处理事项和近期日程。仅当前摄影师本人可查看。",
    response_description="摄影师仪表盘数据",
)
def get_dashboard(
    range_key: str = Query("month", alias="range", description="统计时间范围：7d/month/90d/all"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """获取当前摄影师本人的行动型仪表盘数据。"""
    if current_user.role != "photographer":
        raise HTTPException(status_code=403, detail="仅摄影师可查看仪表盘")
    return get_photographer_dashboard(db, current_user.id, range_key)


@router.get(
    "/dashboard/public/{user_id}",
    response_model=PhotographerPublicDashboardResponse,
    summary="摄影师公开信任面板",
    description="公开查看已认证摄影师的服务可信度、内容活跃度和热门内容。",
    response_description="摄影师公开仪表盘数据",
)
def get_public_dashboard(
    user_id: int,
    db: Session = Depends(get_db),
):
    """公开获取指定认证摄影师的信任面板数据。"""
    user = db.query(User).filter(
        User.id == user_id,
        User.role == "photographer",
        User.is_active.is_(True),
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="摄影师不存在")
    return get_public_photographer_dashboard(db, user_id)
