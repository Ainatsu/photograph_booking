from io import BytesIO

from io import BytesIO

from PIL import Image

from backend.app.models.ai_resource import AIResourceDocument, AIResourceImageEmbedding
from backend.app.services import ai_multimodal_embedding_service as image_service


class PixelImageProvider:
    model = "pixel-test-v1"
    dimensions = 3

    def embed_images(self, images: list[bytes]) -> list[list[float]]:
        vectors = []
        for value in images:
            image = Image.open(BytesIO(value)).convert("RGB").resize((1, 1))
            red, green, blue = image.getpixel((0, 0))
            total = max(1, red + green + blue)
            vectors.append([red / total, green / total, blue / total])
        return vectors


def _write_image(path, color):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (16, 16), color).save(path, format="PNG")


def test_native_image_index_and_query_use_real_pixels(db, monkeypatch, tmp_path):
    upload_dir = tmp_path / "uploads"
    red_path = upload_dir / "portfolio" / "red.png"
    blue_path = upload_dir / "portfolio" / "blue.png"
    query_path = upload_dir / "queries" / "red-query.png"
    _write_image(red_path, (255, 0, 0))
    _write_image(blue_path, (0, 0, 255))
    _write_image(query_path, (250, 5, 0))

    monkeypatch.setattr(image_service.settings, "UPLOAD_DIR", str(upload_dir))
    monkeypatch.setattr(image_service.settings, "AI_IMAGE_EMBEDDING_PROVIDER", "local_clip")
    monkeypatch.setattr(image_service.settings, "AI_IMAGE_EMBEDDING_VERSION", "native-test-v1")
    monkeypatch.setattr(image_service, "get_image_embedding_provider", lambda: PixelImageProvider())

    red_document = AIResourceDocument(
        resource_type="portfolio_item",
        resource_id="red-work",
        owner_user_id=1,
        title="red",
        summary="",
        search_text="red",
        tags=[],
        payload={"media_type": "image", "url": "/static/portfolio/red.png"},
        content_hash="red-document",
    )
    blue_document = AIResourceDocument(
        resource_type="portfolio_item",
        resource_id="blue-work",
        owner_user_id=2,
        title="blue",
        summary="",
        search_text="blue",
        tags=[],
        payload={"media_type": "image", "url": "/static/portfolio/blue.png"},
        content_hash="blue-document",
    )
    db.add_all([red_document, blue_document])
    db.commit()

    sync = image_service.sync_resource_image_embeddings(db)
    assert sync.embedded == 2
    rows = db.query(AIResourceImageEmbedding).order_by(AIResourceImageEmbedding.document_id).all()
    assert rows[0].embedding_json != rows[1].embedding_json
    assert rows[0].image_hash != rows[1].image_hash

    query_vector, info = image_service.visual_query_embedding(
        [{"type": "image", "url": "/static/queries/red-query.png"}]
    )
    document_scores, _ = image_service.image_candidate_scores(db, query_vector=query_vector)

    assert info["embedding_space"] == "native_image"
    assert document_scores[red_document.id] > document_scores[blue_document.id]
