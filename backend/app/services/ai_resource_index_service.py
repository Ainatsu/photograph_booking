"""AI 资源索引文档的构建、加载、重建与刷新服务。"""

import hashlib
import json
from typing import Any

from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.models.ai_resource import AIResourceDocument, AIResourceEmbedding
from backend.app.models.photographer import PhotographerProfile
from backend.app.services.ai_resource_context_service import (
    CONTEXT_SCHEMA_VERSION,
    build_resource_documents,
)
from backend.app.services.photographer_service import _fix_missing_ids


DOCUMENT_KEYS_BY_TYPE = {
    "photographer": "photographers",
    "portfolio_item": "portfolio_items",
    "package": "packages",
}


def load_or_rebuild_resource_documents(db: Session) -> dict[str, list[dict[str, Any]]]:
    """加载资源文档；仅在文档索引为空时重建文档，不在查询链路同步向量。"""
    documents = load_resource_documents(db)
    if any(documents.values()):
        return documents
    # 向量构建属于发布后的索引任务或显式 reindex 脚本，不能阻塞在线检索请求。
    rebuild_ai_resource_documents(db, sync_embeddings=False)
    return load_resource_documents(db)


def load_resource_documents(db: Session) -> dict[str, list[dict[str, Any]]]:
    """从数据库加载全部资源文档及其对应嵌入。"""
    rows = (
        db.query(AIResourceDocument)
        .order_by(AIResourceDocument.resource_type.asc(), AIResourceDocument.id.asc())
        .all()
    )
    from backend.app.services.ai_embedding_service import get_embedding_provider
    embedding_provider = get_embedding_provider()
    embedding_query = db.query(AIResourceEmbedding).filter(
        AIResourceEmbedding.embedding_version == settings.AI_EMBEDDING_VERSION
    )
    if embedding_provider is not None:
        embedding_query = embedding_query.filter(
            AIResourceEmbedding.embedding_model == embedding_provider.model
        )
    embedding_rows = embedding_query.order_by(AIResourceEmbedding.embedded_at.desc()).all()
    embeddings_by_document = {}
    for embedding_row in embedding_rows:
        embeddings_by_document.setdefault(embedding_row.document_id, embedding_row)
    documents = _empty_documents()
    for row in rows:
        key = DOCUMENT_KEYS_BY_TYPE.get(row.resource_type)
        if not key:
            continue
        documents[key].append(_row_to_document(row, embeddings_by_document.get(row.id)))
    return documents


def rebuild_ai_resource_documents(
    db: Session,
    owner_user_id: int | None = None,
    *,
    sync_embeddings: bool = True,
) -> int:
    """从摄影师档案重建资源文档，返回索引条数。"""
    _fix_missing_ids(db)
    query = db.query(PhotographerProfile)
    if owner_user_id is not None:
        query = query.filter(PhotographerProfile.user_id == owner_user_id)
    profiles = query.all()

    # 只在摄影师资源类型内做增删：全量重建不得清除其他类型的行（如 platform_rule 规则文档）。
    existing_query = db.query(AIResourceDocument).filter(
        AIResourceDocument.resource_type.in_(DOCUMENT_KEYS_BY_TYPE)
    )
    if owner_user_id is not None:
        existing_query = existing_query.filter(AIResourceDocument.owner_user_id == owner_user_id)
    existing_rows = {
        (row.resource_type, row.resource_id): row
        for row in existing_query.all()
    }

    indexed_count = 0
    active_keys = set()
    for document in _iter_documents(build_resource_documents(profiles)):
        key = (document["resource_type"], str(document.get("id", "")))
        active_keys.add(key)
        values = _document_values(document)
        row = existing_rows.get(key)
        if row is None:
            row = AIResourceDocument(**values)
            db.add(row)
        else:
            for field, value in values.items():
                setattr(row, field, value)
        indexed_count += 1

    for key, row in existing_rows.items():
        if key not in active_keys:
            db.delete(row)

    db.commit()
    if sync_embeddings:
        from backend.app.services.ai_embedding_service import sync_resource_embeddings
        from backend.app.services.ai_multimodal_embedding_service import sync_resource_image_embeddings
        sync_resource_embeddings(db, owner_user_id=owner_user_id)
        sync_resource_image_embeddings(db, owner_user_id=owner_user_id)
    return indexed_count


def refresh_ai_resource_documents_for_user(db: Session, owner_user_id: int) -> int:
    """刷新指定用户的资源文档；后台索引开启时改为异步入队。"""
    if not settings.AI_INDEX_WORKER_ENABLED:
        return rebuild_ai_resource_documents(db, owner_user_id=owner_user_id)
    indexed_count = rebuild_ai_resource_documents(
        db,
        owner_user_id=owner_user_id,
        sync_embeddings=False,
    )
    from backend.app.services.ai_index_job_service import enqueue_index_job
    enqueue_index_job(
        db,
        owner_user_id=owner_user_id,
        reason="resource_changed",
    )
    return indexed_count


def _document_to_row(document: dict[str, Any]) -> AIResourceDocument:
    """将文档字典转为 AIResourceDocument 记录。"""
    return AIResourceDocument(**_document_values(document))


def _document_values(document: dict[str, Any]) -> dict[str, Any]:
    """提取文档字典中可入库的字段值。"""
    price_min, price_max = _document_price_range(document)
    return {
        "resource_type": document["resource_type"],
        "resource_id": str(document.get("id", "")),
        "owner_user_id": document["owner_user_id"],
        "title": document.get("title") or "",
        "summary": document.get("summary") or "",
        "search_text": document.get("search_text") or "",
        "tags": document.get("tags") or [],
        "city": document.get("city"),
        "price_min": price_min,
        "price_max": price_max,
        "payload": document.get("payload") or {},
        "content_hash": _content_hash(document),
    }


def _row_to_document(
    row: AIResourceDocument,
    embedding_row: AIResourceEmbedding | None = None,
) -> dict[str, Any]:
    """将数据库行（含嵌入）还原为文档字典。"""
    payload = row.payload or {}
    price_label = _payload_price_label(payload)
    price_tags = payload.get("price_tags") or []
    return {
        "schema_version": CONTEXT_SCHEMA_VERSION,
        "document_id": row.id,
        "resource_type": row.resource_type,
        "id": row.resource_id,
        "owner_user_id": row.owner_user_id,
        "title": row.title or "",
        "summary": row.summary or "",
        "search_text": row.search_text or "",
        "tags": row.tags or [],
        "city": row.city,
        "price": row.price_min,
        "price_min": row.price_min,
        "price_max": row.price_max,
        "price_label": price_label,
        "price_tags": price_tags,
        "payload": payload,
        "content_hash": row.content_hash,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "embedding": embedding_row.embedding_json if embedding_row else None,
        "embedding_model": embedding_row.embedding_model if embedding_row else None,
        "embedding_version": embedding_row.embedding_version if embedding_row else None,
    }


def _document_price_range(document: dict[str, Any]) -> tuple[float | None, float | None]:
    """提取文档的价格区间 (min, max)。"""
    payload = document.get("payload") or {}
    if document.get("resource_type") == "photographer":
        price_range = payload.get("price_range") or {}
        return _to_float(price_range.get("min")), _to_float(price_range.get("max"))

    price = _to_float(document.get("price"))
    return price, price


def _payload_price_label(payload: dict[str, Any]) -> str | None:
    """从 payload 中提取价格标签。"""
    if "price_label" in payload:
        return payload.get("price_label")
    price_range = payload.get("price_range") or {}
    return price_range.get("label")


def _content_hash(document: dict[str, Any]) -> str:
    """计算文档内容的 SHA-256 摘要，用于变更检测。"""
    content = {
        "schema_version": CONTEXT_SCHEMA_VERSION,
        "resource_type": document.get("resource_type"),
        "id": str(document.get("id", "")),
        "owner_user_id": document.get("owner_user_id"),
        "title": document.get("title"),
        "summary": document.get("summary"),
        "search_text": document.get("search_text"),
        "tags": document.get("tags"),
        "city": document.get("city"),
        "price": document.get("price"),
        "price_label": document.get("price_label"),
        "price_tags": document.get("price_tags"),
        "payload": document.get("payload"),
    }
    raw = json.dumps(content, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _iter_documents(documents: dict[str, list[dict[str, Any]]]):
    """按固定顺序遍历各类型资源文档。"""
    for key in ("photographers", "portfolio_items", "packages"):
        yield from documents.get(key, [])


def _empty_documents() -> dict[str, list[dict[str, Any]]]:
    """返回各资源类型的空文档容器。"""
    return {
        "photographers": [],
        "portfolio_items": [],
        "packages": [],
    }


def _to_float(value: Any) -> float | None:
    """将任意值安全转为 float，失败返回 None。"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
