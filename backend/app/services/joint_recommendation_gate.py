"""Deterministic rollout gate for the joint availability/ranking experience."""

import hashlib

from backend.app.core.config import settings


def is_joint_recommendation_enabled(identity: str | int | None) -> bool:
    """判断指定用户是否启用联合推荐（确定性灰度开关）。"""
    if not settings.JOINT_RECOMMENDATION_ENABLED:
        return False
    percentage = max(0, min(100, int(settings.JOINT_RECOMMENDATION_ROLLOUT_PERCENT)))
    if percentage >= 100:
        return True
    if percentage <= 0:
        return False
    stable_identity = str(identity or "anonymous")
    bucket = int(hashlib.sha256(stable_identity.encode("utf-8")).hexdigest()[:8], 16) % 100
    return bucket < percentage
