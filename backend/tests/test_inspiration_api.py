"""MVP coverage for private inspiration CRUD and map aggregation."""


def payload(title="Harbour light", place_id="west-kowloon"):
    return {
        "title": title,
        "summary": "Blue hour portrait references",
        "content": [{"type": "paragraph", "text": "Keep the skyline quiet."}],
        "tags": ["portrait", "blue hour"],
        "location_name": "West Kowloon",
        "location_address": "Hong Kong",
        "latitude": 22.3001,
        "longitude": 114.1542,
        "place_id": place_id,
        "provider": "openstreetmap",
        "coordinate_system": "WGS84",
        "location_precision": "exact",
        "status": "draft",
    }


def test_inspiration_crud_is_private_and_archivable(client, customer_headers, photographer_headers):
    created = client.post("/api/v1/inspirations/", json=payload(), headers=customer_headers)
    assert created.status_code == 201
    inspiration_id = created.json()["id"]

    assert client.get(f"/api/v1/inspirations/{inspiration_id}", headers=photographer_headers).status_code == 404

    updated = client.put(
        f"/api/v1/inspirations/{inspiration_id}",
        json={"title": "Saved harbour light", "status": "saved"},
        headers=customer_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "saved"

    assert client.delete(f"/api/v1/inspirations/{inspiration_id}", headers=customer_headers).status_code == 204
    assert client.get("/api/v1/inspirations/", headers=customer_headers).json() == []


def test_inspiration_map_groups_same_place(client, customer_headers):
    for title in ("First", "Second"):
        assert client.post("/api/v1/inspirations/", json=payload(title), headers=customer_headers).status_code == 201

    response = client.get("/api/v1/inspirations/map", headers=customer_headers)
    assert response.status_code == 200
    assert response.json()["points"][0]["count"] == 2
    assert len(response.json()["points"][0]["preview"]) == 2
    assert [item["title"] for item in response.json()["points"][0]["preview"]] == ["First", "Second"]


def test_inspiration_map_uses_first_content_image_as_preview(client, customer_headers):
    data = payload("Image reference")
    data["content"] = [
        {"type": "paragraph", "text": "A quiet blue-hour frame."},
        {"type": "image", "url": "/static/inspirations/original.jpg", "thumb_url": "/static/inspirations/thumb.jpg"},
    ]
    assert client.post("/api/v1/inspirations/", json=data, headers=customer_headers).status_code == 201

    response = client.get("/api/v1/inspirations/map", headers=customer_headers)

    assert response.status_code == 200
    assert response.json()["points"][0]["preview"][0]["cover_url"] == "/static/inspirations/thumb.jpg"


def test_inspiration_rejects_partial_coordinates(client, customer_headers):
    data = payload()
    data.pop("longitude")
    assert client.post("/api/v1/inspirations/", json=data, headers=customer_headers).status_code == 422


def test_inspiration_detail_exposes_nullable_generation_and_retry_route(client, customer_headers):
    created = client.post("/api/v1/inspirations/", json=payload(), headers=customer_headers)
    inspiration_id = created.json()["id"]
    detail = client.get(f"/api/v1/inspirations/{inspiration_id}", headers=customer_headers)
    assert detail.status_code == 200
    assert detail.json()["generation"] is None

    retry = client.post(f"/api/v1/inspirations/{inspiration_id}/generation/retry", headers=customer_headers)
    assert retry.status_code == 200
    assert retry.json()["generation"] is None
