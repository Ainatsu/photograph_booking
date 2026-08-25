"""
推荐系统 API 路由

提供作品、套餐和企划的个性化推荐以及推荐事件上报等功能。
"""

from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from backend.app.api.deps import get_current_active_user, get_current_active_user_optional
from backend.app.core.database import get_db
from backend.app.models.user import User
from backend.app.schemas.recommendation import PackageRecommendationQuery, RecommendationEventBatchCreate, RecommendationEventBatchResponse, RecommendationPackagesResponse, RecommendationProjectsResponse, RecommendationWorksResponse
from backend.app.services.package_recommendation_service import recommend_packages
from backend.app.services.project_recommendation_service import recommend_projects
from backend.app.services.recommendation_event_service import record_batch
from backend.app.services.recommendation_service import recommend_works
from backend.app.services.recommendation_metrics_service import algorithm_funnel_metrics

router = APIRouter(prefix="/recommendations", tags=["recommendations"])

@router.get("/works", response_model=RecommendationWorksResponse)
def get_recommended_works(scene: str = Query("gallery_for_you", pattern="^(gallery_for_you|home_feed|similar_works)$"), cursor: str | None = None, limit: int = Query(20, ge=1, le=50), city: str | None = Query(None, max_length=100), seed_work_id: str | None = Query(None, max_length=80), session_id: str | None = Query(None, max_length=100), db: Session = Depends(get_db), current_user: User | None = Depends(get_current_active_user_optional)):
    """获取推荐的作品列表"""
    return recommend_works(db, current_user.id if current_user else None, scene, cursor, limit, city, seed_work_id, session_id)

@router.get("/packages", response_model=RecommendationPackagesResponse)
def get_recommended_packages(cursor: str | None = None, limit: int = Query(20, ge=1, le=50), city: str | None = Query(None, max_length=100), budget_min: float | None = Query(None, ge=0), budget_max: float | None = Query(None, ge=0), budget_strict: bool = False, date_strict: bool = False, styles: str | None = Query(None, max_length=300), shoot_date: date | None = None, time_start: str | None = Query(None, pattern=r"^\d{2}:\d{2}$"), time_end: str | None = Query(None, pattern=r"^\d{2}:\d{2}$"), duration_minutes: int | None = Query(None, gt=0), location_text: str | None = Query(None, max_length=255), latitude: float | None = Query(None, ge=-90, le=90), longitude: float | None = Query(None, ge=-180, le=180), max_distance_km: float | None = Query(None, ge=0), require_exact_availability: bool = False, sort_mode: str = Query("best_match", pattern="^(best_match|nearest|lowest_price|earliest_available)$"), session_id: str | None = Query(None, max_length=100), db: Session = Depends(get_db), current_user: User | None = Depends(get_current_active_user_optional)):
    """获取推荐的套餐方案列表，并校验筛选参数"""
    if (time_start is None) != (time_end is None):
        raise HTTPException(status_code=422, detail="time_start 和 time_end 必须同时提供")
    if (latitude is None) != (longitude is None):
        raise HTTPException(status_code=422, detail="latitude 和 longitude 必须同时提供")
    if budget_min is not None and budget_max is not None and budget_min > budget_max:
        raise HTTPException(status_code=422, detail="budget_min 不能大于 budget_max")
    if time_start and time_end:
        try:
            start_parts = tuple(int(part) for part in time_start.split(":"))
            end_parts = tuple(int(part) for part in time_end.split(":"))
        except ValueError:
            raise HTTPException(status_code=422, detail="时间必须使用 HH:MM 格式")
        if any(hour > 23 or minute > 59 for hour, minute in (start_parts, end_parts)) or start_parts >= end_parts:
            raise HTTPException(status_code=422, detail="time_end 必须晚于有效的 time_start")
    requested_styles = [item.strip() for item in (styles or "").split(",") if item.strip()]
    query = PackageRecommendationQuery(city=city, budget_min=budget_min, budget_max=budget_max, budget_strict=budget_strict, date_strict=date_strict, styles=requested_styles, shoot_date=shoot_date, time_start=time_start, time_end=time_end, duration_minutes=duration_minutes, location_text=location_text, latitude=latitude, longitude=longitude, max_distance_km=max_distance_km, require_exact_availability=require_exact_availability, sort_mode=sort_mode)
    return recommend_packages(db, current_user.id if current_user else None, cursor, limit, query, session_id)

@router.get("/projects", response_model=RecommendationProjectsResponse)
def get_recommended_projects(cursor: str | None = None, limit: int = Query(20, ge=1, le=50), city: str | None = Query(None, max_length=80), styles: str | None = Query(None, max_length=300), budget_min: int | None = Query(None, ge=0), budget_max: int | None = Query(None, ge=0), session_id: str | None = Query(None, max_length=100), db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """获取推荐给摄影师的企划列表"""
    if current_user.role != "photographer":
        raise HTTPException(status_code=403, detail="企划推荐仅面向摄影师")
    requested_styles = [item.strip() for item in (styles or "").split(",") if item.strip()]
    return recommend_projects(db, current_user, cursor, limit, city, requested_styles, budget_min, budget_max, session_id)

@router.post("/events/batch", response_model=RecommendationEventBatchResponse)
def create_recommendation_events(data: RecommendationEventBatchCreate, db: Session = Depends(get_db), current_user: User | None = Depends(get_current_active_user_optional)):
    """批量上报推荐事件（自动去重）"""
    accepted, deduplicated = record_batch(db, data, current_user.id if current_user else None); return {"accepted":accepted,"deduplicated":deduplicated}


@router.get("/metrics/algorithms")
def get_algorithm_metrics(days: int = Query(30, ge=1, le=180), db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """获取推荐算法漏斗指标（仅管理员）"""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="仅管理员可查看推荐实验指标")
    return {"days": days, "algorithms": algorithm_funnel_metrics(db, days)}
