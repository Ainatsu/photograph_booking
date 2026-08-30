import json

from backend.app.services import ai_publish_polish_service


class PolishProvider:
    def __init__(self):
        self.messages = None

    async def chat(self, messages, **kwargs):
        self.messages = messages
        assert kwargs["response_format"] == {"type": "json_object"}
        return {
            "content": json.dumps({
                "fields": {
                    "title": "港岛自然光人像拍摄",
                    "description": "希望在傍晚自然光下完成一组轻松、真实的人像作品。",
                    "deliverables": "精修 30 张",
                    "style_tags": ["自然光", "人像", "自然光"],
                    "reference_images": ["must-not-be-returned.jpg"],
                }
            }, ensure_ascii=False),
            "metadata": {"model": {"provider": "test", "model": "polish"}},
        }


def test_publish_polish_requires_login(client):
    response = client.post("/api/v1/ai/publish/polish", json={
        "content_type": "work",
        "fields": {"title": "测试作品"},
    })
    assert response.status_code == 401


def test_publish_polish_only_returns_allow_listed_text_fields(monkeypatch, client, customer_headers):
    provider = PolishProvider()
    monkeypatch.setattr(ai_publish_polish_service, "get_text_provider", lambda: provider)

    response = client.post("/api/v1/ai/publish/polish", json={
        "content_type": "project",
        "fields": {
            "title": "港岛人像",
            "description": "想拍自然一点",
            "deliverables": "",
            "style_tags": ["自然光"],
            "reference_images": ["private-local-image.jpg"],
        },
    }, headers=customer_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["fields"] == {
        "title": "港岛自然光人像拍摄",
        "description": "希望在傍晚自然光下完成一组轻松、真实的人像作品。",
        "deliverables": "",
        "style_tags": ["自然光", "人像"],
    }
    assert data["polished_field_count"] == 3
    assert "private-local-image.jpg" not in provider.messages[-1]["content"]


def test_publish_polish_rejects_empty_text(client, customer_headers):
    response = client.post("/api/v1/ai/publish/polish", json={
        "content_type": "work",
        "fields": {"title": "", "description": "", "tags": []},
    }, headers=customer_headers)
    assert response.status_code == 400
    assert "请先填写" in response.json()["detail"]
