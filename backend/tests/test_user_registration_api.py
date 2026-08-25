from backend.app.core import config
from backend.app.services.sms_provider import get_sms_provider


def _verified_phone_token(client, phone: str) -> str:
    response = client.post(
        "/api/v1/auth/verifications/request",
        json={"channel": "phone", "target": phone, "purpose": "register"},
    )
    assert response.status_code == 200
    challenge_id = response.json()["challenge_id"]
    normalized = "+86" + phone if not phone.startswith("+") else phone
    code = get_sms_provider().get_last_code(normalized)
    assert code is not None
    response = client.post(
        "/api/v1/auth/verifications/confirm",
        json={"challenge_id": challenge_id, "code": code},
    )
    assert response.status_code == 200
    return response.json()["verification_token"]


def test_register_requires_verified_phone_and_defaults_to_customer(client):
    token = _verified_phone_token(client, "13800009999")
    response = client.post(
        "/api/v1/users/register",
        json={
            "username": "new_user99",
            "phone_verification_token": token,
            "email": " REGISTER-ROLE@TEST.COM ",
            "password": "password123",
            "display_name": "New User",
            "role": "photographer",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["role"] == "customer"
    assert body["phone"] == "+8613800009999"
    assert body["email"] is None
    assert body["pending_email"] == "register-role@test.com"


def test_registration_verification_token_is_single_use(client):
    token = _verified_phone_token(client, "13800009998")
    payload = {
        "username": "single_use1",
        "phone_verification_token": token,
        "password": "password123",
        "display_name": "First",
    }
    assert client.post("/api/v1/users/register", json=payload).status_code == 201
    payload["username"] = "single_use2"
    assert client.post("/api/v1/users/register", json=payload).status_code == 400


def test_registration_allows_phone_to_be_omitted(client):
    response = client.post(
        "/api/v1/users/register",
        json={
            "username": "username_only",
            "password": "password123",
            "display_name": "Username Only",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["id"]
    assert body["username"] == "username_only"
    assert body["phone"] is None


def test_username_availability_reports_normalized_and_taken(client):
    response = client.get("/api/v1/users/username-availability", params={"username": "@New_User"})
    assert response.status_code == 200
    assert response.json() == {
        "normalized_username": "new_user",
        "available": True,
        "reason": None,
    }


def test_duplicate_username_reports_username_conflict(client):
    payload = {
        "username": "taken_name",
        "password": "password123",
        "display_name": "First",
    }
    assert client.post("/api/v1/users/register", json=payload).status_code == 201

    response = client.post("/api/v1/users/register", json=payload)
    assert response.status_code == 400
    assert response.json()["detail"] == "该用户 ID 已被占用"


def test_duplicate_phone_reports_phone_conflict(client, monkeypatch):
    # 同一号码需要连续申请两次验证码，先放开重发间隔限制。
    monkeypatch.setattr(config.settings, "VERIFICATION_RESEND_INTERVAL_SECONDS", 0)
    phone = "13800009997"
    assert client.post(
        "/api/v1/users/register",
        json={
            "username": "phone_first",
            "phone_verification_token": _verified_phone_token(client, phone),
            "password": "password123",
            "display_name": "First",
        },
    ).status_code == 201

    response = client.post(
        "/api/v1/users/register",
        json={
            "username": "phone_second",
            "phone_verification_token": _verified_phone_token(client, phone),
            "password": "password123",
            "display_name": "Second",
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "该手机号已被注册"
