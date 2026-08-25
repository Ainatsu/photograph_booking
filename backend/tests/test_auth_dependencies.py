from backend.app.core.security import create_access_token


def _bad_sub_headers() -> dict[str, str]:
    token = create_access_token({"sub": "legacy-user-id"})
    return {"Authorization": f"Bearer {token}"}


def test_like_set_rejects_non_numeric_token_sub(client):
    res = client.post(
        "/api/v1/likes/set",
        json={"target_type": "portfolio", "target_id": "auth-probe"},
        params={"liked": True},
        headers=_bad_sub_headers(),
    )

    assert res.status_code == 401


def test_favorite_toggle_rejects_non_numeric_token_sub(client):
    res = client.post(
        "/api/v1/favorites/toggle",
        json={
            "work_id": "auth-probe",
            "photographer_id": 1,
            "work_data": {"title": "Auth probe"},
        },
        headers=_bad_sub_headers(),
    )

    assert res.status_code == 401
