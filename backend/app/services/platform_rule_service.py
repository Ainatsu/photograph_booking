"""平台规则文档的切分、入库与向量检索服务。

规则文档位于 docs/rules/*.md（README.md 是语料说明，跳过）。每条规则形如
"- 规 XX-n：…"，规则块含其缩进续行与子条目；切分后的 chunk 以
resource_type="platform_rule" 存入 ai_resource_documents，向量复用
ai_resource_embeddings（Postgres 上走 pgvector 余弦，SQLite 降级为
embedding_json + Python 余弦）。规则文档不参与摄影师混合检索的
REFERENCE_KEYS 通道，检索入口只有本模块的 search_platform_rules。
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.models.ai_resource import AIResourceDocument, AIResourceEmbedding

RULE_RESOURCE_TYPE = "platform_rule"
# owner_user_id 非空约束的哨兵值：规则是平台级文档，不归属于任何真实用户。
RULE_SYSTEM_OWNER_ID = 0
PLATFORM_RULES_CONTEXT_SCHEMA_VERSION = "platform_rules_v1"

_SKIPPED_FILENAMES = {"README.md"}
_RULE_LINE_RE = re.compile(r"^\s*-\s*规\s*(?P<rule_id>[A-Z]{2,4}-\d+)\s*[：:]\s*(?P<body>.*)$")
_H1_RE = re.compile(r"^#\s+(?P<title>.+?)\s*$")
_H2_RE = re.compile(r"^##\s+(?P<title>.+?)\s*$")

# 单条规则片段注入 prompt 时的长度上限，防止超长规则块挤占上下文。
_MAX_RULE_TEXT_CHARS = 1600


@dataclass(frozen=True)
class RuleChunk:
    """一条规则的切分结果：规则块 + 文档与小节上下文。"""

    doc_key: str
    doc_title: str
    section: str
    rule_id: str
    text: str

    @property
    def resource_id(self) -> str:
        """稳定的资源 ID，如 order-payment-rules#OR-11。"""
        return f"{self.doc_key}#{self.rule_id}"


def collect_rule_chunks(rules_dir: str | Path | None = None) -> list[RuleChunk]:
    """读取规则目录下全部文档并切分为规则块。"""
    directory = Path(rules_dir or settings.AI_PLATFORM_RULES_DIR)
    if not directory.is_dir():
        return []
    chunks: list[RuleChunk] = []
    for path in sorted(directory.glob("*.md")):
        if path.name in _SKIPPED_FILENAMES:
            continue
        chunks.extend(parse_rule_document(path))
    return chunks


def parse_rule_document(path: Path) -> list[RuleChunk]:
    """解析单个规则文档：按「规 XX-n」条目切分，缩进续行与子条目归属当前规则。"""
    doc_key = path.stem
    doc_title = doc_key
    section = ""
    chunks: list[RuleChunk] = []
    current_rule_id: str | None = None
    current_lines: list[str] = []

    def _flush() -> None:
        nonlocal current_rule_id, current_lines
        if current_rule_id is not None:
            text = "\n".join(current_lines).strip()
            if text:
                chunks.append(
                    RuleChunk(
                        doc_key=doc_key,
                        doc_title=doc_title,
                        section=section,
                        rule_id=current_rule_id,
                        text=text,
                    )
                )
        current_rule_id = None
        current_lines = []

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        h1 = _H1_RE.match(line)
        if h1:
            _flush()
            doc_title = h1.group("title").strip()
            continue
        h2 = _H2_RE.match(line)
        if h2:
            _flush()
            section = h2.group("title").strip()
            continue
        match = _RULE_LINE_RE.match(line)
        if match:
            _flush()
            current_rule_id = match.group("rule_id")
            current_lines = [f"规 {current_rule_id}：{match.group('body').strip()}"]
            continue
        # 缩进续行、子条目或普通列表行归属当前规则块；顶格的说明段落不并入。
        if current_rule_id is not None and (raw_line[:1] in {" ", "\t", "-", "*"}):
            current_lines.append(line.strip())
    _flush()
    return chunks


def _chunk_summary(text: str) -> str:
    """取规则首句作为简介，用于嵌入文本与检索结果的快速预览。"""
    first_line = text.split("\n", 1)[0]
    return first_line[:120]


def _chunk_content_hash(chunk: RuleChunk) -> str:
    """规则块内容的 SHA-256 摘要，用于变更检测与嵌入跳过。"""
    raw = "|".join(
        (
            PLATFORM_RULES_CONTEXT_SCHEMA_VERSION,
            chunk.doc_key,
            chunk.rule_id,
            chunk.doc_title,
            chunk.section,
            chunk.text,
        )
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _chunk_values(chunk: RuleChunk) -> dict[str, Any]:
    """将规则块转为 AIResourceDocument 的字段值。"""
    return {
        "resource_type": RULE_RESOURCE_TYPE,
        "resource_id": chunk.resource_id,
        "owner_user_id": RULE_SYSTEM_OWNER_ID,
        "title": f"{chunk.doc_title}｜{chunk.section}｜规 {chunk.rule_id}",
        "summary": _chunk_summary(chunk.text),
        "search_text": chunk.text,
        "tags": ["平台规则", chunk.doc_key],
        "city": None,
        "price_min": None,
        "price_max": None,
        "payload": {
            "schema_version": PLATFORM_RULES_CONTEXT_SCHEMA_VERSION,
            "rule_id": chunk.rule_id,
            "doc_key": chunk.doc_key,
            "doc_title": chunk.doc_title,
            "section": chunk.section,
            "source_file": f"{chunk.doc_key}.md",
        },
        "content_hash": _chunk_content_hash(chunk),
    }


def sync_platform_rules(
    db: Session,
    *,
    rules_dir: str | Path | None = None,
    sync_embeddings: bool = True,
    force: bool = False,
) -> dict[str, Any]:
    """把规则目录的最新内容 upsert 进资源文档表，并同步向量嵌入。"""
    chunks = collect_rule_chunks(rules_dir)
    existing_rows = db.query(AIResourceDocument).filter(
        AIResourceDocument.resource_type == RULE_RESOURCE_TYPE
    ).all()
    existing_by_id = {row.resource_id: row for row in existing_rows}
    active_ids = {chunk.resource_id for chunk in chunks}

    for chunk in chunks:
        values = _chunk_values(chunk)
        row = existing_by_id.get(chunk.resource_id)
        if row is None:
            row = AIResourceDocument(**values)
            db.add(row)
        else:
            for field, value in values.items():
                setattr(row, field, value)

    for resource_id, row in existing_by_id.items():
        if resource_id not in active_ids:
            db.delete(row)
    db.commit()

    embedding_result = None
    if sync_embeddings:
        from backend.app.services.ai_embedding_service import sync_resource_embeddings

        # owner 过滤把同步范围限定在规则文档（owner=0），不触碰摄影师资源的嵌入。
        embedding_result = sync_resource_embeddings(
            db,
            owner_user_id=RULE_SYSTEM_OWNER_ID,
            force=force,
        ).__dict__
    return {
        "documents": len(chunks),
        "deleted": len(existing_by_id) - len(active_ids & set(existing_by_id)),
        "embeddings": embedding_result,
    }


def ensure_platform_rules_indexed(db: Session) -> dict[str, Any]:
    """启动时的幂等入口：内容与嵌入都已就绪时跳过，否则执行同步。"""
    if not settings.AI_PLATFORM_RULES_ENABLED:
        return {"skipped": True, "reason": "disabled"}
    rules_dir = Path(settings.AI_PLATFORM_RULES_DIR)
    if not rules_dir.is_dir():
        return {"skipped": True, "reason": "rules_dir_missing", "dir": str(rules_dir)}

    chunks = collect_rule_chunks(rules_dir)
    expected_hashes = {chunk.resource_id: _chunk_content_hash(chunk) for chunk in chunks}
    rows = db.query(AIResourceDocument).filter(
        AIResourceDocument.resource_type == RULE_RESOURCE_TYPE
    ).all()
    if len(rows) == len(expected_hashes) and all(
        expected_hashes.get(row.resource_id) == row.content_hash for row in rows
    ):
        from backend.app.services.ai_embedding_service import get_embedding_provider

        provider = get_embedding_provider()
        if provider is not None:
            embedded_count = db.query(AIResourceEmbedding).filter(
                AIResourceEmbedding.document_id.in_([row.id for row in rows] or [-1]),
                AIResourceEmbedding.embedding_model == provider.model,
                AIResourceEmbedding.embedding_version == settings.AI_EMBEDDING_VERSION,
            ).count()
            if embedded_count == len(rows):
                return {"skipped": True, "reason": "up_to_date", "documents": len(rows)}
    return sync_platform_rules(db, rules_dir=rules_dir)


@dataclass(frozen=True)
class RuleSearchHit:
    """一条规则检索命中。"""

    rule_id: str
    doc_key: str
    doc_title: str
    section: str
    text: str
    score: float

    def as_dict(self) -> dict[str, Any]:
        """序列化为 JSON 兼容字典。"""
        return {
            "rule_id": self.rule_id,
            "doc_key": self.doc_key,
            "doc_title": self.doc_title,
            "section": self.section,
            "text": self.text,
            "score": round(self.score, 4),
        }


def search_platform_rules(
    db: Session,
    query: str | None,
    *,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """按语义相似度检索平台规则片段，返回按得分降序的命中列表。"""
    if not settings.AI_PLATFORM_RULES_ENABLED:
        return []
    text = (query or "").strip()
    if not text:
        return []
    top_k = max(1, min(int(limit or settings.AI_PLATFORM_RULES_TOP_K), 10))

    from backend.app.services.ai_embedding_service import (
        cosine_similarity,
        get_embedding_provider,
        pgvector_candidate_scores,
        query_embedding,
    )

    vector, _meta = query_embedding(text)
    if vector is None:
        return []

    rows = db.query(AIResourceDocument).filter(
        AIResourceDocument.resource_type == RULE_RESOURCE_TYPE
    ).all()
    if not rows:
        return []

    candidate_scores = pgvector_candidate_scores(
        db,
        query_vector=vector,
        resource_types=[RULE_RESOURCE_TYPE],
        limit=top_k,
    )
    scored: list[tuple[AIResourceDocument, float]] = []
    if candidate_scores:
        rows_by_id = {row.id: row for row in rows}
        for document_id, score in candidate_scores.items():
            row = rows_by_id.get(document_id)
            if row is not None:
                scored.append((row, score))
    else:
        # SQLite / pgvector 未命中：加载规则文档的 JSON 向量做内存余弦。
        provider = get_embedding_provider()
        embedding_rows = db.query(AIResourceEmbedding).filter(
            AIResourceEmbedding.document_id.in_([row.id for row in rows]),
            AIResourceEmbedding.embedding_version == settings.AI_EMBEDDING_VERSION,
        )
        if provider is not None:
            embedding_rows = embedding_rows.filter(
                AIResourceEmbedding.embedding_model == provider.model
            )
        embeddings_by_doc: dict[int, list[float]] = {}
        for embedding_row in embedding_rows.order_by(
            AIResourceEmbedding.embedded_at.desc()
        ).all():
            embeddings_by_doc.setdefault(embedding_row.document_id, embedding_row.embedding_json)
        for row in rows:
            embedding = embeddings_by_doc.get(row.id)
            if embedding:
                scored.append((row, cosine_similarity(vector, embedding)))

    scored.sort(key=lambda item: item[1], reverse=True)
    hits: list[dict[str, Any]] = []
    for row, score in scored[:top_k]:
        payload = row.payload or {}
        rule_id = payload.get("rule_id") or (row.resource_id.split("#", 1)[-1])
        hits.append(
            RuleSearchHit(
                rule_id=rule_id,
                doc_key=payload.get("doc_key") or "",
                doc_title=payload.get("doc_title") or "",
                section=payload.get("section") or "",
                text=(row.search_text or "")[:_MAX_RULE_TEXT_CHARS],
                # 与 pgvector 路径一致，分数统一钳位到 [0, 1]。
                score=max(0.0, min(1.0, float(score))),
            ).as_dict()
        )
    return hits


def build_platform_rules_context(hits: list[dict[str, Any]] | None) -> str | None:
    """把检索命中组装为注入模型的规则上下文；无命中返回 None。"""
    if not hits:
        return None
    lines = [
        "以下是 search_platform_rules 检索到的平台规则原文片段（按相关度排序）："
    ]
    for hit in hits:
        text = (hit.get("text") or "")[:_MAX_RULE_TEXT_CHARS]
        lines.append(
            f"- 【规 {hit.get('rule_id')}｜{hit.get('doc_title')}｜{hit.get('section')}】{text}"
        )
    return "\n".join(lines)
