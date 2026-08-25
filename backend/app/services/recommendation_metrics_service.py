"""推荐算法指标：按算法版本统计转化漏斗数据。"""

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from backend.app.models.analytics import AnalyticsEvent


def algorithm_funnel_metrics(db: Session, days: int = 30) -> list[dict]:
    """统计近 N 天各算法版本的曝光-转化漏斗指标。"""
    cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, days))
    tracked_events = {
        "package_impression": "impressions",
        "package_click": "opens",
        "package_view": "opens",
        "package_booking_intent": "booking_starts",
        "joint_rec_impression": "impressions",
        "joint_rec_open": "opens",
        "joint_rec_booking_start": "booking_starts",
        "joint_rec_booking_success": "booking_successes",
    }
    grouped: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    events = db.query(AnalyticsEvent).filter(
        AnalyticsEvent.created_at >= cutoff,
        AnalyticsEvent.event_type.in_(tracked_events),
    ).all()
    for event in events:
        metadata = event.event_metadata or {}
        version = str(metadata.get("algorithm_version") or "unknown")
        grouped[version][tracked_events[event.event_type]] += 1
    results = []
    for version, counts in sorted(grouped.items()):
        impressions = counts["impressions"]
        starts = counts["booking_starts"]
        results.append({
            "algorithm_version": version,
            "impressions": impressions,
            "opens": counts["opens"],
            "booking_starts": starts,
            "booking_successes": counts["booking_successes"],
            "open_rate": round(counts["opens"] / impressions, 4) if impressions else 0.0,
            "booking_start_rate": round(starts / impressions, 4) if impressions else 0.0,
            "booking_success_rate": round(counts["booking_successes"] / starts, 4) if starts else 0.0,
        })
    return results
