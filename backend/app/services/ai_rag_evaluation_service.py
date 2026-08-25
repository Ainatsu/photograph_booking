"""AI RAG 检索评估服务：加载用例并批量评估混合检索效果。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.app.services.ai_embedding_service import get_embedding_provider
from backend.app.services.ai_retrieval_service import RetrievalCriteria, _rank_documents


RAG_EVALUATION_SCHEMA_VERSION = "hybrid_rag_eval_v1"


def load_rag_cases(path: str | Path) -> list[dict[str, Any]]:
    """从 JSONL 文件加载 RAG 检索评估用例。"""
    cases = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            value = line.strip()
            if not value or value.startswith("#"):
                continue
            case = json.loads(value)
            case.setdefault("id", f"line-{line_number}")
            cases.append(case)
    return cases


def evaluate_rag_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """批量评估 RAG 检索用例并汇总准确率。"""
    results = [evaluate_rag_case(case) for case in cases]
    passed = sum(1 for item in results if item["passed"])
    total = len(results)
    return {
        "schema_version": RAG_EVALUATION_SCHEMA_VERSION,
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "accuracy": round(passed / total, 4) if total else 0.0,
        "results": results,
    }


def evaluate_rag_case(case: dict[str, Any]) -> dict[str, Any]:
    """评估单个 RAG 用例：检索文档并校验期望命中与禁入 ID。"""
    provider = get_embedding_provider()
    if provider is None:
        raise ValueError("rag_evaluation_requires_embedding_provider")
    query = case.get("query") or ""
    query_vector = provider.embed([query])[0]
    raw_documents = case.get("documents") or []
    document_vectors = provider.embed([item.get("search_text") or "" for item in raw_documents])
    documents = [
        {
            **document,
            "embedding": vector,
            "embedding_model": provider.model,
            "payload": document.get("payload") or {
                "id": document.get("id"),
                "name": document.get("title"),
            },
        }
        for document, vector in zip(raw_documents, document_vectors, strict=True)
    ]
    criteria = RetrievalCriteria.model_validate({
        "text": query,
        "terms": case.get("terms") or [],
        **(case.get("filters") or {}),
    })
    results = _rank_documents(
        documents,
        criteria,
        limit=case.get("limit") or 3,
        query_vector=query_vector,
    )
    result_ids = [item.get("id") for item in results]
    expected_top_id = case.get("expected_top_id")
    forbidden_ids = set(case.get("forbidden_ids") or [])
    passed = (
        (expected_top_id is None or (result_ids and result_ids[0] == expected_top_id))
        and not forbidden_ids.intersection(result_ids)
    )
    return {
        "id": case.get("id"),
        "passed": passed,
        "expected_top_id": expected_top_id,
        "result_ids": result_ids,
        "forbidden_ids_returned": sorted(forbidden_ids.intersection(result_ids)),
    }
