import pytest
from fastapi import HTTPException

from backend.app.api.v1.photographers import update_work
from backend.app.schemas.photographer import PortfolioItemUpdate
from backend.app.services.photographer_service import get_all_works, get_work_by_id


def test_owner_can_update_work_metadata(db, photographer_profile, photographer_user, monkeypatch):
    monkeypatch.setattr(
        "backend.app.api.v1.photographers.refresh_ai_resource_documents_for_user",
        lambda *_args, **_kwargs: None,
    )
    work_id = next(
        work["id"]
        for work in get_all_works(db)
        if work["user_id"] == photographer_user.id
    )

    response = update_work(
        work_id,
        PortfolioItemUpdate(
            title="更新后的作品",
            tags=["胶片", "自然光"],
            description="更新后的创作说明。",
        ),
        db,
        photographer_user,
    )

    detail = get_work_by_id(db, work_id)
    assert response["message"] == "作品已更新"
    assert detail is not None
    assert detail["title"] == "更新后的作品"
    assert detail["tags"] == ["胶片", "自然光"]
    assert detail["tag"] == "胶片"
    assert detail["description"] == "更新后的创作说明。"


def test_non_owner_cannot_update_work_metadata(
    db,
    photographer_profile,
    photographer_user,
    customer_user,
):
    work_id = next(
        work["id"]
        for work in get_all_works(db)
        if work["user_id"] == photographer_user.id
    )

    with pytest.raises(HTTPException) as exc_info:
        update_work(
            work_id,
            PortfolioItemUpdate(title="不应成功"),
            db,
            customer_user,
        )

    assert exc_info.value.status_code == 403
