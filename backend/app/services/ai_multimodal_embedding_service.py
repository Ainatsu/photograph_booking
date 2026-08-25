"""多模态嵌入服务：为资源图片生成向量嵌入并支持视觉检索打分。"""

from __future__ import annotations

import hashlib
import base64
from pathlib import Path
from urllib.parse import unquote, urlparse
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.models.ai_resource import AIResourceDocument, AIResourceImageEmbedding
import httpx

from backend.app.services.ai_embedding_service import cosine_similarity, get_image_embedding_provider


@dataclass(frozen=True)
class ImageEmbeddingSyncResult:
    """图片嵌入同步结果统计。"""

    total_images: int
    embedded: int
    skipped: int
    model: str
    version: str
    dimensions: int


def sync_resource_image_embeddings(
    db: Session,
    *,
    owner_user_id: int | None = None,
    force: bool = False,
) -> ImageEmbeddingSyncResult:
    """同步资源图片的向量嵌入，返回同步统计结果。"""
    provider = get_image_embedding_provider()
    if provider is None:
        return ImageEmbeddingSyncResult(0, 0, 0, "disabled", settings.AI_IMAGE_EMBEDDING_VERSION, 0)

    query = db.query(AIResourceDocument).filter(AIResourceDocument.resource_type == "portfolio_item")
    if owner_user_id is not None:
        query = query.filter(AIResourceDocument.owner_user_id == owner_user_id)
    documents = query.order_by(AIResourceDocument.id.asc()).all()
    assets = [asset for document in documents for asset in _document_image_assets(document)]
    document_ids = [document.id for document in documents]
    existing_rows = db.query(AIResourceImageEmbedding).filter(
        AIResourceImageEmbedding.document_id.in_(document_ids or [-1]),
        AIResourceImageEmbedding.embedding_model == provider.model,
        AIResourceImageEmbedding.embedding_version == settings.AI_IMAGE_EMBEDDING_VERSION,
    ).all()
    existing = {(row.document_id, row.image_url): row for row in existing_rows}
    active_keys = {(asset["document_id"], asset["image_url"]) for asset in assets}
    for key, row in existing.items():
        if key not in active_keys:
            db.delete(row)

    pending = [
        asset for asset in assets
        if force
        or (asset["document_id"], asset["image_url"]) not in existing
        or existing[(asset["document_id"], asset["image_url"])].image_hash != asset["image_hash"]
    ]
    embedded = 0
    batch_size = max(1, settings.AI_IMAGE_EMBEDDING_BATCH_SIZE)
    for offset in range(0, len(pending), batch_size):
        batch = pending[offset:offset + batch_size]
        if hasattr(provider, "embed_descriptors"):
            usable = [(asset, None) for asset in batch]
            vectors = provider.embed_descriptors([asset["visual_descriptor"] for asset in batch])
        else:
            loaded = [_load_image_bytes(asset["image_url"]) for asset in batch]
            usable = [(asset, image_bytes) for asset, image_bytes in zip(batch, loaded, strict=True) if image_bytes]
            if not usable:
                continue
            vectors = provider.embed_images([image_bytes for _, image_bytes in usable])
        for (asset, image_bytes), vector in zip(usable, vectors, strict=True):
            key = (asset["document_id"], asset["image_url"])
            row = existing.get(key)
            if row is None:
                row = AIResourceImageEmbedding(
                    document_id=asset["document_id"],
                    image_url=asset["image_url"],
                    image_hash=_image_content_hash(image_bytes) if image_bytes else asset["image_hash"],
                    visual_descriptor=asset["visual_descriptor"],
                    embedding_model=provider.model,
                    embedding_version=settings.AI_IMAGE_EMBEDDING_VERSION,
                    dimensions=len(vector),
                    embedding_json=vector,
                    embedded_at=datetime.now(timezone.utc),
                )
                db.add(row)
                db.flush()
                existing[key] = row
            else:
                row.image_hash = _image_content_hash(image_bytes) if image_bytes else asset["image_hash"]
                row.visual_descriptor = asset["visual_descriptor"]
                row.dimensions = len(vector)
                row.embedding_json = vector
                row.embedded_at = datetime.now(timezone.utc)
                db.flush()
            _write_pgvector(db, row.id, vector)
            embedded += 1
    db.commit()
    return ImageEmbeddingSyncResult(
        total_images=len(assets),
        embedded=embedded,
        skipped=len(assets) - embedded,
        model=provider.model,
        version=settings.AI_IMAGE_EMBEDDING_VERSION,
        dimensions=provider.dimensions,
    )


def visual_query_embedding(
    attachments: list[dict[str, Any]] | None,
    vision_analysis: dict[str, Any] | None = None,
) -> tuple[list[float] | None, dict[str, Any]]:
    """直接从用户上传图片像素生成查询向量。"""
    provider = get_image_embedding_provider()
    image_urls = [
        str(item.get("url") or "").strip()
        for item in attachments or []
        if item.get("type") == "image" and str(item.get("url") or "").strip()
    ]
    if provider is None:
        return None, {"provider": "disabled", "model": None, "dimensions": 0}
    if not image_urls and hasattr(provider, "embed_descriptors") and vision_analysis:
        vector = provider.embed_descriptors([visual_query_descriptor(vision_analysis)])[0]
        return vector, {
            "provider": settings.AI_IMAGE_EMBEDDING_PROVIDER,
            "model": provider.model,
            "version": settings.AI_IMAGE_EMBEDDING_VERSION,
            "dimensions": len(vector),
            "embedding_space": "legacy_descriptor",
        }
    if not image_urls:
        return None, {"provider": settings.AI_IMAGE_EMBEDDING_PROVIDER, "model": provider.model, "dimensions": 0}
    images = [value for url in image_urls if (value := _load_image_bytes(url))]
    if not images:
        return None, {
            "provider": settings.AI_IMAGE_EMBEDDING_PROVIDER,
            "model": provider.model,
            "dimensions": provider.dimensions,
            "error": "image_load_failed",
        }
    vectors = provider.embed_images(images)
    vector = _mean_normalized_vector(vectors)
    return vector, {
        "provider": settings.AI_IMAGE_EMBEDDING_PROVIDER,
        "model": provider.model,
        "version": settings.AI_IMAGE_EMBEDDING_VERSION,
        "dimensions": len(vector),
        "image_count": len(images),
        "embedding_space": "native_image",
    }


def image_candidate_scores(
    db: Session,
    *,
    query_vector: list[float] | None,
    limit: int = 100,
) -> tuple[dict[int, float], dict[int, float]]:
    """按视觉相似度给文档与作者打分，返回两组分数映射。"""
    if not query_vector:
        return {}, {}
    provider = get_image_embedding_provider()
    if provider is None:
        return {}, {}

    if db.get_bind().dialect.name == "postgresql":
        vector_literal = "[" + ",".join(f"{value:.10f}" for value in query_vector) + "]"
        rows = db.execute(
            text(
                "SELECT e.document_id, d.owner_user_id, "
                "1 - (e.embedding_vector <=> CAST(:query_vector AS vector)) AS visual_score "
                "FROM ai_resource_image_embeddings e "
                "JOIN ai_resource_documents d ON d.id = e.document_id "
                "WHERE e.embedding_model = :model AND e.embedding_version = :version "
                "AND e.embedding_vector IS NOT NULL "
                "ORDER BY e.embedding_vector <=> CAST(:query_vector AS vector) LIMIT :limit"
            ),
            {
                "query_vector": vector_literal,
                "model": provider.model,
                "version": settings.AI_IMAGE_EMBEDDING_VERSION,
                "limit": max(1, min(limit, 500)),
            },
        ).mappings().all()
        triples = [
            (int(row["document_id"]), int(row["owner_user_id"]), float(row["visual_score"] or 0.0))
            for row in rows
        ]
    else:
        rows = db.query(AIResourceImageEmbedding, AIResourceDocument.owner_user_id).join(
            AIResourceDocument,
            AIResourceDocument.id == AIResourceImageEmbedding.document_id,
        ).filter(
            AIResourceImageEmbedding.embedding_model == provider.model,
            AIResourceImageEmbedding.embedding_version == settings.AI_IMAGE_EMBEDDING_VERSION,
        ).all()
        triples = [
            (row.document_id, owner_user_id, max(0.0, cosine_similarity(query_vector, row.embedding_json)))
            for row, owner_user_id in rows
        ]

    document_scores: dict[int, float] = {}
    owner_scores: dict[int, float] = {}
    for document_id, owner_user_id, score in triples:
        document_scores[document_id] = max(document_scores.get(document_id, 0.0), score)
        owner_scores[owner_user_id] = max(owner_scores.get(owner_user_id, 0.0), score)
    return document_scores, owner_scores


def visual_query_descriptor(analysis: dict[str, Any] | None) -> str:
    """将视觉分析结果拼成用于嵌入的文本描述。"""
    if not analysis:
        return ""
    parts = []
    summary = str(analysis.get("summary") or "").strip()
    if summary:
        parts.append(summary)
    for key in ("style", "scene", "mood", "lighting", "color", "composition", "makeup", "search_terms"):
        values = analysis.get(key) or []
        if isinstance(values, str):
            values = [values]
        cleaned = [str(value).strip() for value in values if str(value).strip()]
        if cleaned:
            parts.append(f"{key}: {' '.join(cleaned)}")
    return "\n".join(parts)


def _document_image_assets(document: AIResourceDocument) -> list[dict[str, Any]]:
    """提取文档中的图片资源及对应描述与哈希。"""
    payload = document.payload or {}
    if (payload.get("media_type") or "image") != "image":
        return []
    urls = [payload.get("url"), payload.get("compressed_url"), payload.get("thumbnail_url")]
    unique_urls = list(dict.fromkeys(str(url).strip() for url in urls if str(url or "").strip()))
    descriptor = "\n".join(
        part for part in (
            str(document.title or "").strip(),
            str(document.summary or "").strip(),
            " ".join(str(tag) for tag in (document.tags or [])),
            " ".join(str(tag) for tag in (payload.get("photographer_styles") or [])),
            str(payload.get("photographer_location") or "").strip(),
        ) if part
    )
    return [
        {
            "document_id": document.id,
            "image_url": url,
            "visual_descriptor": descriptor or url,
            "image_hash": (
                hashlib.sha256(f"{url}\n{descriptor}".encode("utf-8")).hexdigest()
                if settings.AI_IMAGE_EMBEDDING_PROVIDER.lower() == "mock"
                else _stored_image_hash(url)
            ),
        }
        for url in unique_urls
    ]


def _stored_image_hash(image_url: str) -> str:
    image_bytes = _load_image_bytes(image_url)
    return _image_content_hash(image_bytes) if image_bytes else hashlib.sha256(image_url.encode("utf-8")).hexdigest()


def _image_content_hash(image_bytes: bytes) -> str:
    return hashlib.sha256(image_bytes).hexdigest()


def _load_image_bytes(image_url: str) -> bytes | None:
    """读取本地上传图片或下载受限大小的 HTTP 图片。"""
    parsed = urlparse(image_url)
    if parsed.scheme == "data":
        header, separator, encoded = image_url.partition(",")
        if not separator or ";base64" not in header.lower():
            raise ValueError("image_embedding_invalid_data_uri")
        data = base64.b64decode(encoded, validate=True)
    elif parsed.scheme in {"http", "https"}:
        response = httpx.get(
            image_url,
            timeout=settings.AI_IMAGE_EMBEDDING_TIMEOUT_SECONDS,
            follow_redirects=True,
        )
        response.raise_for_status()
        content_type = (response.headers.get("content-type") or "").lower()
        if content_type and not content_type.startswith("image/"):
            raise ValueError("image_embedding_invalid_content_type")
        data = response.content
    else:
        raw_path = unquote(parsed.path if parsed.scheme else image_url)
        if raw_path.startswith("/static/"):
            raw_path = raw_path[len("/static/"):]
        candidate = (Path(settings.UPLOAD_DIR).resolve() / raw_path.lstrip("/\\")).resolve()
        upload_root = Path(settings.UPLOAD_DIR).resolve()
        try:
            candidate.relative_to(upload_root)
        except ValueError as exc:
            raise ValueError("image_embedding_path_outside_upload_dir") from exc
        if not candidate.is_file():
            return None
        data = candidate.read_bytes()
    if not data or len(data) > settings.AI_IMAGE_EMBEDDING_MAX_BYTES:
        raise ValueError("image_embedding_invalid_size")
    return data


def _mean_normalized_vector(vectors: list[list[float]]) -> list[float]:
    if not vectors:
        return []
    dimensions = len(vectors[0])
    if dimensions == 0 or any(len(vector) != dimensions for vector in vectors):
        raise ValueError("image_embedding_dimension_mismatch")
    mean = [sum(vector[index] for vector in vectors) / len(vectors) for index in range(dimensions)]
    norm = sum(value * value for value in mean) ** 0.5
    return [value / norm for value in mean] if norm else mean


def _write_pgvector(db: Session, embedding_id: int, vector: list[float]) -> None:
    """在 PostgreSQL 上写入 pgvector 向量列。"""
    if db.get_bind().dialect.name != "postgresql":
        return
    vector_literal = "[" + ",".join(f"{value:.10f}" for value in vector) + "]"
    db.execute(
        text(
            "UPDATE ai_resource_image_embeddings SET embedding_vector = CAST(:vector AS vector) "
            "WHERE id = :embedding_id"
        ),
        {"vector": vector_literal, "embedding_id": embedding_id},
    )
