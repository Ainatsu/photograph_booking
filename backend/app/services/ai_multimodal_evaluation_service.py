"""加载多模态用例并对嵌入检索结果进行评估，返回准确率统计。"""

import json
from pathlib import Path
from typing import Any

from backend.app.core.config import settings
from backend.app.services.ai_embedding_service import MockEmbeddingProvider, cosine_similarity


def load_multimodal_cases(path: str | Path) -> list[dict[str, Any]]:
    """从文件逐行读取多模态评估用例（每行一个 JSON 对象）。"""
    return [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def evaluate_multimodal_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """逐条评估用例的检索排名，返回通过数、失败数与准确率。"""
    provider = MockEmbeddingProvider("multimodal-eval", settings.AI_EMBEDDING_DIMENSIONS)
    results = []
    for case in cases:
        query_vector = provider.embed([case["query_descriptor"]])[0]
        ranked = sorted(
            (
                cosine_similarity(query_vector, provider.embed([candidate["descriptor"]])[0]),
                candidate["id"],
            )
            for candidate in case["candidates"]
        )
        ranked.reverse()
        result_ids = [item[1] for item in ranked]
        passed = bool(result_ids) and result_ids[0] == case["expected_top_id"]
        results.append({
            "id": case["id"],
            "passed": passed,
            "expected_top_id": case["expected_top_id"],
            "result_ids": result_ids,
        })
    passed_count = sum(1 for result in results if result["passed"])
    return {
        "schema_version": "multimodal_rag_eval_v1",
        "total": len(results),
        "passed": passed_count,
        "failed": len(results) - passed_count,
        "accuracy": passed_count / len(results) if results else 0.0,
        "results": results,
    }
