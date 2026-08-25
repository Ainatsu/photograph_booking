from datetime import datetime, timezone

from backend.app.core import config
from backend.app.core.security import create_access_token
from backend.app.api.deps import _decode_user_from_token
from backend.app.services.identity_service import resolve_login_identifier
from backend.app.services.user_service import create_user, authenticate_user


def test_login_resolves_verified_email_phone_and_username(db):
    user = create_user(db, "legacy@example.com", None, "correct123", "用户", "customer")
    user.username = "photo_user"
    user.phone = "+8613800138000"
    user.phone_verified_at = datetime.now(timezone.utc)
    db.commit()

    assert authenticate_user(db, " LEGACY@EXAMPLE.COM ", "correct123").id == user.id
    assert authenticate_user(db, "+8613800138000", "correct123").id == user.id
    assert authenticate_user(db, "@PHOTO_USER", "correct123").id == user.id


def test_unverified_identity_is_not_login_identifier(db):
    user = create_user(db, "pending@example.com", "+8613800138001", "correct123", "用户", "customer")
    user.username = "pending_user"
    user.email_verified_at = None
    db.commit()

    assert resolve_login_identifier(db, "pending@example.com") is None
    assert resolve_login_identifier(db, "+8613800138001") is None
    assert authenticate_user(db, "pending@example.com", "correct123") is None


def test_token_version_is_enforced_only_when_enabled(db, customer_user, monkeypatch):
    customer_user.token_version = 2
    db.commit()
    token = create_access_token({"sub": str(customer_user.id), "ver": 1})

    monkeypatch.setattr(config.settings, "TOKEN_VERSION_ENFORCEMENT_ENABLED", True)
    try:
        from fastapi import HTTPException
        try:
            _decode_user_from_token(token, db)
            assert False, "stale token should be rejected"
        except HTTPException as exc:
            assert exc.status_code == 401
    finally:
        monkeypatch.setattr(config.settings, "TOKEN_VERSION_ENFORCEMENT_ENABLED", False)

    assert _decode_user_from_token(token, db).id == customer_user.id
