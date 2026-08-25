"""推荐事件服务：批量记录推荐曝光与点击等行为事件。"""

from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from backend.app.models.analytics import AnalyticsEvent
from backend.app.models.recommendation import RecommendationExposure, RecommendationItemStats

ALLOWED_EVENTS = {"portfolio_impression", "portfolio_click", "portfolio_view", "portfolio_dwell", "portfolio_like", "portfolio_favorite", "portfolio_comment", "photographer_follow_from_work", "package_view_from_work", "booking_intent_from_work", "portfolio_unlike", "portfolio_unfavorite", "portfolio_not_interested", "package_impression", "package_click", "package_view", "package_favorite", "package_unfavorite", "package_booking_intent", "project_impression", "project_click", "project_view", "project_apply", "project_application_selected", "joint_rec_impression", "joint_rec_open", "joint_rec_filter_change", "joint_rec_select_slot", "joint_rec_booking_start", "joint_rec_booking_success", "joint_rec_no_result"}

def record_batch(db: Session, batch, viewer_user_id: int | None):
    """批量写入推荐事件并更新统计，返回接受与去重数量。"""
    accepted = deduplicated = 0
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
    for data in batch.events:
        if data.event_type not in ALLOWED_EVENTS: continue
        if data.recommendation_id and db.query(AnalyticsEvent).filter(AnalyticsEvent.actor_id == viewer_user_id, AnalyticsEvent.event_type == data.event_type, AnalyticsEvent.target_id == data.target_id, AnalyticsEvent.created_at >= cutoff).first():
            deduplicated += 1; continue
        owner_id = data.owner_user_id or viewer_user_id
        if owner_id is None: continue
        metadata = dict(data.metadata or {})
        metadata.update({k: v for k, v in {"recommendation_id": data.recommendation_id, "request_id": data.request_id, "session_id": data.session_id, "scene": data.scene, "position": data.position, "algorithm_version": data.algorithm_version, "candidate_source": data.candidate_source, "owner_user_id": data.owner_user_id}.items() if v is not None})
        db.add(AnalyticsEvent(user_id=owner_id, actor_id=viewer_user_id, event_type=data.event_type, target_type=data.target_type, target_id=data.target_id, event_metadata=metadata))
        stats = db.query(RecommendationItemStats).filter_by(target_type=data.target_type, target_id=data.target_id).first()
        field = {"portfolio_impression": "impression_count", "portfolio_click": "click_count", "portfolio_view": "click_count", "portfolio_like": "like_count", "portfolio_favorite": "favorite_count", "portfolio_comment": "comment_count", "booking_intent_from_work": "booking_intent_count", "package_impression": "impression_count", "package_click": "click_count", "package_view": "click_count", "package_favorite": "favorite_count", "package_booking_intent": "booking_intent_count", "joint_rec_impression": "impression_count", "joint_rec_open": "click_count", "joint_rec_booking_start": "booking_intent_count"}.get(data.event_type)
        if stats and field: setattr(stats, field, getattr(stats, field) + 1); stats.last_event_at = datetime.now(timezone.utc)
        if data.event_type in {"portfolio_impression", "package_impression", "project_impression", "joint_rec_impression"} and data.recommendation_id and data.position is not None:
            db.add(RecommendationExposure(recommendation_id=data.recommendation_id, request_id=data.request_id, viewer_user_id=viewer_user_id, session_id=data.session_id, target_type=data.target_type, target_id=data.target_id, position=data.position, scene=data.scene or "gallery_for_you", candidate_source=data.candidate_source or "unknown", algorithm_version=data.algorithm_version or "work_hybrid_v1"))
        accepted += 1
    db.commit()
    return accepted, deduplicated
