from datetime import datetime, timezone

import pytest

from backend.app.core.security import verify_password
from backend.app.services.photographer_service import get_profile_by_user_id
from backend.app.services.user_service import change_password, create_user, logout_all_devices, update_username
from backend.app.models.photographer import PhotographerProfile


def test_temporary_username_can_be_replaced_and_cooldown_applies(db):
    user = create_user(db, "stage-e@example.com", None, "password123", "用户", "customer")
    user.username = "user_100"
    user.username_requires_update = True
    db.commit()

    update_username(db, user, "formal_user")
    assert user.username == "formal_user"
    assert user.username_requires_update is False
    with pytest.raises(ValueError, match="30 天"):
        update_username(db, user, "formal_user2")


def test_change_password_increments_token_version(db):
    user = create_user(db, "password-stage-e@example.com", None, "password123", "用户", "customer")
    old_version = user.token_version or 0
    change_password(db, user, "password123", "new-password123")
    assert user.token_version == old_version + 1
    assert user.password_changed_at is not None
    assert verify_password("new-password123", user.hashed_password)


def test_logout_all_devices_increments_token_version(db):
    user = create_user(db, "logout-stage-e@example.com", None, "password123", "用户", "customer")
    logout_all_devices(db, user)
    assert user.token_version == 1


def test_public_profile_email_requires_verified_opt_in(db):
    user = create_user(db, "public-stage-e@example.com", None, "password123", "摄影师", "photographer")
    profile = PhotographerProfile(user_id=user.id)
    db.add(profile)
    db.commit()

    assert get_profile_by_user_id(db, user.id)["public_email"] is None
    user.show_email_on_profile = True
    user.email_verified_at = datetime.now(timezone.utc)
    db.commit()
    assert get_profile_by_user_id(db, user.id)["public_email"] == "public-stage-e@example.com"
