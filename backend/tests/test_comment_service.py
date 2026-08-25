import pytest
from fastapi import HTTPException

from backend.app.models.comment import Comment
from backend.app.services.comment_service import create_comment, list_comments
from backend.app.services.photographer_service import get_all_packages, get_all_works


def _first_work_id(db):
    return get_all_works(db)[0]["id"]


def _first_package_id(db):
    return get_all_packages(db)[0]["id"]


def test_create_work_comment(db, customer_user, photographer_profile):
    work_id = _first_work_id(db)

    result = create_comment(db, customer_user.id, "portfolio", work_id, "这组照片很有氛围")

    assert result["content"] == "这组照片很有氛围"
    assert result["target_type"] == "portfolio"
    assert result["target_id"] == work_id
    assert result["user_display_name"] == customer_user.display_name
    assert db.query(Comment).filter_by(target_id=work_id).count() == 1


def test_list_comments_includes_total_and_user(db, customer_user, photographer_user, photographer_profile):
    package_id = _first_package_id(db)
    first = create_comment(db, customer_user.id, "package", package_id, "适合周末拍摄")
    second = create_comment(db, photographer_user.id, "package", package_id, "欢迎提前沟通风格")

    result = list_comments(db, "package", package_id)

    assert result["total"] == 2
    assert [item["id"] for item in result["items"]] == [second["id"], first["id"]]
    assert result["items"][0]["user_display_name"] == photographer_user.display_name


def test_create_comment_rejects_missing_target(db, customer_user):
    with pytest.raises(HTTPException) as exc:
        create_comment(db, customer_user.id, "portfolio", "missing-work", "不存在的目标")

    assert exc.value.status_code == 404


def test_comment_api_create_and_list(client, db, customer_headers, customer_user, photographer_profile):
    work_id = _first_work_id(db)

    create_res = client.post(
        "/api/v1/comments",
        json={
            "target_type": "portfolio",
            "target_id": work_id,
            "content": "非常喜欢这一张",
        },
        headers=customer_headers,
    )
    assert create_res.status_code == 201
    assert create_res.json()["user_display_name"] == customer_user.display_name

    list_res = client.get(
        "/api/v1/comments",
        params={"target_type": "portfolio", "target_id": work_id},
    )
    assert list_res.status_code == 200
    assert list_res.json()["total"] == 1
    assert list_res.json()["items"][0]["content"] == "非常喜欢这一张"


def test_comment_api_requires_auth(client, db, photographer_profile):
    work_id = _first_work_id(db)

    res = client.post(
        "/api/v1/comments",
        json={
            "target_type": "portfolio",
            "target_id": work_id,
            "content": "未登录评论",
        },
    )

    assert res.status_code == 401
