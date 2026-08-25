"""资源向量嵌入服务：文本向量化、同步与相似度检索。"""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from typing import Protocol

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.models.ai_resource import AIResourceDocument, AIResourceEmbedding


class EmbeddingProvider(Protocol):
    """向量嵌入 Provider 协议，统一模型信息与嵌入接口。"""
    model: str
    dimensions: int

    def embed(self, texts: list[str]) -> list[list[float]]:
        """将文本列表批量转换为向量列表。"""
        ...


class ImageEmbeddingProvider(Protocol):
    """原生图片向量 Provider，向量必须来自图片像素而不是图片描述文本。"""

    model: str
    dimensions: int

    def embed_images(self, images: list[bytes]) -> list[list[float]]:
        ...


class MockEmbeddingProvider:
    """可重复的字符 n-gram embedding，用于 SQLite、本地开发和测试。"""

    def __init__(self, model: str, dimensions: int):
        """初始化 mock provider 的模型名与向量维度。"""
        self.model = model
        self.dimensions = dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        """对每条文本生成可重复的哈希向量。"""
        return [_hashed_embedding(value, self.dimensions) for value in texts]


class DisabledImageEmbeddingProvider:
    """显式关闭原生图片向量，避免误把文本哈希当成视觉向量。"""

    model = "disabled"
    dimensions = 0

    def embed_images(self, images: list[bytes]) -> list[list[float]]:
        return []


class MockImageEmbeddingProvider:
    """兼容旧测试与 SQLite 的描述向量，不代表原生视觉 embedding。"""

    def __init__(self, model: str, dimensions: int):
        self.model = model
        self.dimensions = dimensions

    def embed_images(self, images: list[bytes]) -> list[list[float]]:
        return [_hashed_embedding(value.hex(), self.dimensions) for value in images]

    def embed_descriptors(self, descriptors: list[str]) -> list[list[float]]:
        return [_hashed_embedding(value, self.dimensions) for value in descriptors]


class LocalSiglipImageEmbeddingProvider:
    """使用 Hugging Face SigLIP 从真实图片像素生成归一化向量。

    依赖在首次启用时惰性加载，未安装时抛出明确错误，不影响文本 embedding 和普通聊天。
    """

    def __init__(self, *, model: str, dimensions: int, device: str):
        self.model = model
        self.dimensions = dimensions
        self.device = device
        self._processor = None
        self._model = None

    def _load(self):
        if self._processor is not None and self._model is not None:
            return self._processor, self._model
        try:
            import torch
            from transformers import AutoConfig, AutoImageProcessor, AutoModel
            from transformers.utils import logging as transformers_logging
        except ImportError as exc:
            raise RuntimeError(
                "local_clip_requires_torch_transformers: install torch and transformers"
            ) from exc
        previous_verbosity = transformers_logging.get_verbosity()
        transformers_logging.set_verbosity_error()
        try:
            processor = AutoImageProcessor.from_pretrained(self.model)
            config = AutoConfig.from_pretrained(self.model)
            model = AutoModel.from_pretrained(self.model, config=config).to(self.device)
        finally:
            transformers_logging.set_verbosity(previous_verbosity)
        model.eval()
        self._processor = processor
        self._model = model
        self._torch = torch
        return processor, model

    def embed_images(self, images: list[bytes]) -> list[list[float]]:
        if not images:
            return []
        from io import BytesIO

        from PIL import Image

        processor, model = self._load()
        pil_images = [Image.open(BytesIO(value)).convert("RGB") for value in images]
        inputs = processor(images=pil_images, return_tensors="pt")
        inputs = {key: value.to(self.device) for key, value in inputs.items()}
        with self._torch.inference_mode():
            if hasattr(model, "get_image_features"):
                raw = model.get_image_features(**inputs)
            else:
                raw = model.vision_model(**inputs)

            if isinstance(raw, self._torch.Tensor):
                features = raw
            else:
                features = getattr(raw, "pooler_output", None)
                if features is None:
                    features = getattr(raw, "image_embeds", None)
                if features is None:
                    raise RuntimeError(f"image_embedding_unexpected_output_type:{type(raw)}")

        features = features / features.norm(dim=-1, keepdim=True).clamp_min(1e-12)
        vectors = features.detach().cpu().tolist()
        if any(len(vector) != self.dimensions for vector in vectors):
            raise ValueError("image_embedding_dimension_mismatch")
        return vectors


class OpenAICompatibleEmbeddingProvider:
    """通过 OpenAI 兼容接口调用外部嵌入服务的 Provider。"""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        dimensions: int,
        timeout: int,
    ):
        """初始化外部嵌入服务的连接参数。"""
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.dimensions = dimensions
        self.timeout = timeout

    def embed(self, texts: list[str]) -> list[list[float]]:
        """调用 OpenAI 兼容接口批量生成文本向量。"""
        payload = {
            "model": self.model,
            "input": texts,
            "dimensions": self.dimensions,
        }
        response = httpx.post(
            f"{self.base_url}/embeddings",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = sorted(response.json().get("data") or [], key=lambda item: item.get("index", 0))
        vectors = [item.get("embedding") or [] for item in data]
        if len(vectors) != len(texts):
            raise ValueError("embedding_response_count_mismatch")
        if any(len(vector) != self.dimensions for vector in vectors):
            raise ValueError("embedding_dimension_mismatch")
        return vectors


@dataclass(frozen=True)
class EmbeddingSyncResult:
    """记录一次向量同步的统计结果。"""
    total_documents: int
    embedded: int
    skipped: int
    model: str
    version: str
    dimensions: int


def get_embedding_provider() -> EmbeddingProvider | None:
    """按配置创建嵌入 Provider，disabled 时返回 None。"""
    provider = (settings.AI_TEXT_EMBEDDING_PROVIDER or settings.AI_EMBEDDING_PROVIDER or "mock").lower()
    if provider == "disabled":
        return None
    if provider == "mock":
        return MockEmbeddingProvider(
            model=f"mock-hash-{settings.AI_EMBEDDING_VERSION}",
            dimensions=settings.AI_EMBEDDING_DIMENSIONS,
        )
    if provider == "openai_compatible":
        api_key = settings.AI_EMBEDDING_API_KEY or settings.AI_API_KEY
        base_url = settings.AI_EMBEDDING_BASE_URL or settings.AI_BASE_URL
        if not api_key or not base_url:
            raise ValueError("embedding_provider_not_configured")
        return OpenAICompatibleEmbeddingProvider(
            api_key=api_key,
            base_url=base_url,
            model=settings.AI_EMBEDDING_MODEL,
            dimensions=settings.AI_EMBEDDING_DIMENSIONS,
            timeout=settings.AI_REQUEST_TIMEOUT,
        )
    raise ValueError(f"unsupported_embedding_provider:{provider}")


def get_image_embedding_provider() -> ImageEmbeddingProvider | None:
    """按独立配置创建原生图片 embedding Provider。"""
    provider = (settings.AI_IMAGE_EMBEDDING_PROVIDER or "disabled").lower()
    if provider in {"disabled", "none", "off"}:
        return None
    if provider == "mock":
        return MockImageEmbeddingProvider(
            model=f"mock-image-hash-{settings.AI_IMAGE_EMBEDDING_VERSION}",
            dimensions=settings.AI_EMBEDDING_DIMENSIONS,
        )
    if provider in {"local_clip", "local_siglip", "siglip"}:
        return _cached_local_image_provider(
            settings.AI_IMAGE_EMBEDDING_MODEL,
            settings.AI_IMAGE_EMBEDDING_DIMENSIONS,
            settings.AI_IMAGE_EMBEDDING_DEVICE,
        )
    raise ValueError(f"unsupported_image_embedding_provider:{provider}")


def warmup_image_embedding_provider() -> dict[str, str | int] | None:
    """在应用启动时加载本地视觉模型，避免首个图片检索请求承担冷启动耗时。"""
    provider = get_image_embedding_provider()
    if provider is None:
        return None
    loader = getattr(provider, "_load", None)
    if callable(loader):
        loader()
    return {
        "provider": settings.AI_IMAGE_EMBEDDING_PROVIDER,
        "model": provider.model,
        "dimensions": provider.dimensions,
    }


@lru_cache(maxsize=4)
def _cached_local_image_provider(model: str, dimensions: int, device: str) -> ImageEmbeddingProvider:
    return LocalSiglipImageEmbeddingProvider(model=model, dimensions=dimensions, device=device)


def sync_resource_embeddings(
    db: Session,
    *,
    owner_user_id: int | None = None,
    force: bool = False,
) -> EmbeddingSyncResult:
    """为资源文档批量生成并持久化向量，返回同步统计。"""
    provider = get_embedding_provider()
    if provider is None:
        return EmbeddingSyncResult(0, 0, 0, "disabled", settings.AI_EMBEDDING_VERSION, 0)

    query = db.query(AIResourceDocument)
    if owner_user_id is not None:
        query = query.filter(AIResourceDocument.owner_user_id == owner_user_id)
    documents = query.order_by(AIResourceDocument.id.asc()).all()
    existing_rows = db.query(AIResourceEmbedding).filter(
        AIResourceEmbedding.document_id.in_([item.id for item in documents] or [-1]),
        AIResourceEmbedding.embedding_model == provider.model,
        AIResourceEmbedding.embedding_version == settings.AI_EMBEDDING_VERSION,
    ).all()
    existing_by_document = {item.document_id: item for item in existing_rows}
    pending = [
        document
        for document in documents
        if force
        or document.id not in existing_by_document
        or existing_by_document[document.id].content_hash != document.content_hash
    ]

    embedded_count = 0
    batch_size = max(1, settings.AI_EMBEDDING_BATCH_SIZE)
    for offset in range(0, len(pending), batch_size):
        batch = pending[offset: offset + batch_size]
        vectors = provider.embed([embedding_text(document) for document in batch])
        for document, vector in zip(batch, vectors, strict=True):
            row = existing_by_document.get(document.id)
            if row is None:
                row = AIResourceEmbedding(
                    document_id=document.id,
                    embedding_model=provider.model,
                    embedding_version=settings.AI_EMBEDDING_VERSION,
                    dimensions=len(vector),
                    embedding_json=vector,
                    content_hash=document.content_hash,
                    embedded_at=datetime.now(timezone.utc),
                )
                db.add(row)
                db.flush()
                existing_by_document[document.id] = row
            else:
                row.dimensions = len(vector)
                row.embedding_json = vector
                row.content_hash = document.content_hash
                row.embedded_at = datetime.now(timezone.utc)
                db.flush()
            _write_pgvector(db, row.id, vector)
            embedded_count += 1
    db.commit()
    return EmbeddingSyncResult(
        total_documents=len(documents),
        embedded=embedded_count,
        skipped=len(documents) - embedded_count,
        model=provider.model,
        version=settings.AI_EMBEDDING_VERSION,
        dimensions=provider.dimensions,
    )


def query_embedding(query_text: str) -> tuple[list[float] | None, dict[str, str | int | None]]:
    """为查询文本生成向量并附带 provider 元信息。"""
    provider = get_embedding_provider()
    if provider is None or not query_text.strip():
        return None, {"provider": "disabled", "model": None, "dimensions": 0}
    vector = provider.embed([query_text])[0]
    return vector, {
        "provider": settings.AI_EMBEDDING_PROVIDER,
        "model": provider.model,
        "version": settings.AI_EMBEDDING_VERSION,
        "dimensions": len(vector),
    }


def pgvector_candidate_scores(
    db: Session,
    *,
    query_vector: list[float] | None,
    resource_types: list[str],
    limit: int = 50,
) -> dict[int, float]:
    """在 PostgreSQL 上用 pgvector 计算候选文档的语义相似度。"""
    if not query_vector or db.get_bind().dialect.name != "postgresql":
        return {}
    provider = get_embedding_provider()
    if provider is None:
        return {}
    normalized_types = [
        value for value in resource_types
        if value in {"photographer", "portfolio_item", "package"}
    ]
    if not normalized_types:
        return {}
    type_params = ", ".join(f":type_{index}" for index in range(len(normalized_types)))
    vector_literal = "[" + ",".join(f"{value:.10f}" for value in query_vector) + "]"
    params = {
        "query_vector": vector_literal,
        "embedding_model": provider.model,
        "embedding_version": settings.AI_EMBEDDING_VERSION,
        "limit": max(1, min(limit, 200)),
        **{f"type_{index}": value for index, value in enumerate(normalized_types)},
    }
    rows = db.execute(
        text(
            "SELECT d.id AS document_id, "
            "1 - (e.embedding_vector <=> CAST(:query_vector AS vector)) AS semantic_score "
            "FROM ai_resource_embeddings e "
            "JOIN ai_resource_documents d ON d.id = e.document_id "
            "WHERE e.embedding_model = :embedding_model "
            "AND e.embedding_version = :embedding_version "
            "AND e.embedding_vector IS NOT NULL "
            f"AND d.resource_type IN ({type_params}) "
            "ORDER BY e.embedding_vector <=> CAST(:query_vector AS vector) "
            "LIMIT :limit"
        ),
        params,
    ).mappings().all()
    return {
        int(row["document_id"]): max(0.0, min(1.0, float(row["semantic_score"] or 0.0)))
        for row in rows
    }


def embedding_text(document: AIResourceDocument) -> str:
    """将资源文档关键字段拼接为用于嵌入的文本。"""
    return "\n".join(
        part
        for part in (
            f"资源类型：{document.resource_type}",
            f"标题：{document.title}" if document.title else None,
            f"城市：{document.city}" if document.city else None,
            f"简介：{document.summary}" if document.summary else None,
            f"标签：{'、'.join(document.tags or [])}" if document.tags else None,
            document.search_text,
        )
        if part
    )


def cosine_similarity(left: list[float] | None, right: list[float] | None) -> float:
    """计算两个向量的余弦相似度，无效输入返回 0。"""
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return max(-1.0, min(1.0, dot / (left_norm * right_norm)))


def _write_pgvector(db: Session, embedding_id: int, vector: list[float]) -> None:
    """将向量写入 pgvector 列（非 PostgreSQL 时跳过）。"""
    if db.get_bind().dialect.name != "postgresql":
        return
    vector_literal = "[" + ",".join(f"{value:.10f}" for value in vector) + "]"
    db.execute(
        text(
            "UPDATE ai_resource_embeddings "
            "SET embedding_vector = CAST(:vector AS vector) "
            "WHERE id = :embedding_id"
        ),
        {"vector": vector_literal, "embedding_id": embedding_id},
    )


def _hashed_embedding(value: str, dimensions: int) -> list[float]:
    """基于字符 n-gram 哈希生成确定性向量。"""
    normalized = _normalize_semantic_text(value)
    compact = re.sub(r"\s+", "", normalized.lower())
    tokens = set(re.findall(r"[a-z0-9]+", normalized.lower()))
    tokens.update(compact[index:index + size] for size in (1, 2, 3) for index in range(max(0, len(compact) - size + 1)))
    vector = [0.0] * dimensions
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:8], "big") % dimensions
        sign = 1.0 if digest[8] % 2 == 0 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(item * item for item in vector))
    return [item / norm for item in vector] if norm else vector


def _normalize_semantic_text(value: str) -> str:
    """展开近义词，增强语义文本的检索命中。"""
    expansions = {
        "温柔": "温柔 清新 柔和",
        "明亮": "明亮 自然光 通透",
        "电影感": "电影感 胶片 叙事",
        "复古感": "复古感 复古 胶片",
        "生活感": "生活感 自然 纪实",
        "情侣": "情侣 双人 纪念日",
        "性价比": "性价比 实惠 预算",
    }
    result = value
    for source, replacement in expansions.items():
        result = result.replace(source, replacement)
    return result
