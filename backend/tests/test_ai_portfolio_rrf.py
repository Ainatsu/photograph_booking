import pytest

from backend.app.services.ai_retrieval_service import (
    RetrievalCriteria,
    _effective_limit,
    _portfolio_rrf_weights,
    _rank_portfolio_rrf,
)


@pytest.mark.parametrize(
    "text",
    (
        "为我找一份类似风格的作品",
        "推荐一张照片",
        "找一组样片",
        "给我1份案例",
        "只要一套方案",
        "挑一条资源",
    ),
)
def test_resource_measure_words_request_single_result(text):
    assert _effective_limit(text, 5) == 1


def _document(
    document_id: int,
    resource_id: str,
    *,
    title: str,
    tags: list[str],
    visual_score: float,
    semantic_score: float,
):
    return {
        "document_id": document_id,
        "resource_type": "portfolio_item",
        "id": resource_id,
        "owner_user_id": document_id,
        "title": title,
        "summary": "",
        "search_text": " ".join([title, *tags]),
        "tags": tags,
        "city": "重庆",
        "payload": {"id": resource_id, "title": title, "tags": tags},
        "visual_score": visual_score,
        "pgvector_score": semantic_score,
        "updated_at": None,
    }


def test_portfolio_rrf_keeps_candidates_from_both_routes(monkeypatch):
    from backend.app.services import ai_retrieval_service as retrieval

    monkeypatch.setattr(retrieval.settings, "AI_PORTFOLIO_RRF_K", 60)
    monkeypatch.setattr(retrieval.settings, "AI_PORTFOLIO_RRF_IMAGE_WEIGHT", 1.0)
    monkeypatch.setattr(retrieval.settings, "AI_PORTFOLIO_RRF_TEXT_WEIGHT", 1.0)
    monkeypatch.setattr(retrieval.settings, "AI_PORTFOLIO_RRF_CANDIDATE_MULTIPLIER", 10)
    criteria = RetrievalCriteria(text="室外作品", terms=["室外"], limit=3)
    result = _rank_portfolio_rrf(
        [
            _document(1, "visual-only", title="室内参考", tags=["室内"], visual_score=0.99, semantic_score=0.0),
            _document(2, "text-only", title="室外夜景", tags=["室外"], visual_score=0.0, semantic_score=0.95),
        ],
        criteria,
        3,
        None,
        content="找类似图片，但换成室外",
    )

    assert {item["id"] for item in result["items"]} == {"visual-only", "text-only"}
    assert result["candidate_counts"] == {"image": 1, "text": 1, "union": 2}
    assert all(item["_rag"]["fusion_mode"] == "weighted_rrf" for item in result["items"])


def test_siglip_top_10_is_pure_visual_order_with_fusion_debug_fields(monkeypatch):
    from backend.app.services import ai_retrieval_service as retrieval

    monkeypatch.setattr(retrieval.settings, "AI_PORTFOLIO_RRF_K", 60)
    monkeypatch.setattr(retrieval.settings, "AI_PORTFOLIO_RRF_IMAGE_WEIGHT", 1.0)
    monkeypatch.setattr(retrieval.settings, "AI_PORTFOLIO_RRF_TEXT_WEIGHT", 1.0)
    monkeypatch.setattr(retrieval.settings, "AI_PORTFOLIO_RRF_CANDIDATE_MULTIPLIER", 20)
    documents = [
        _document(
            index,
            f"work-{index}",
            title=f"作品 {index}",
            tags=["室外"] if index == 2 else ["室内"],
            visual_score=1.0 - index / 100,
            semantic_score=0.95 if index == 2 else 0.0,
        )
        for index in range(1, 13)
    ]

    result = _rank_portfolio_rrf(
        documents,
        RetrievalCriteria(text="室外作品", terms=["室外"], limit=3),
        3,
        None,
        content="找类似图片，但换成室外",
    )

    debug_rows = result["siglip_top_10"]
    assert len(debug_rows) == 10
    assert [row["portfolio_item_id"] for row in debug_rows] == [
        f"work-{index}" for index in range(1, 11)
    ]
    assert [row["image_rank"] for row in debug_rows] == list(range(1, 11))
    assert debug_rows[1]["text_rank"] == 1
    assert all(
        set(row) == {
            "portfolio_item_id", "visual_score", "image_rank", "text_rank", "rrf_score"
        }
        for row in debug_rows
    )


def test_text_refinement_increases_text_rrf_weight():
    image_weight, text_weight, reason = _portfolio_rrf_weights("再暗一点，换成室外")
    assert text_weight > image_weight
    assert reason == "text_refinement"


def test_explicit_negative_term_filters_portfolio_candidate(monkeypatch):
    from backend.app.services import ai_retrieval_service as retrieval

    monkeypatch.setattr(retrieval.settings, "AI_PORTFOLIO_RRF_K", 60)
    monkeypatch.setattr(retrieval.settings, "AI_PORTFOLIO_RRF_IMAGE_WEIGHT", 1.0)
    monkeypatch.setattr(retrieval.settings, "AI_PORTFOLIO_RRF_TEXT_WEIGHT", 1.0)
    monkeypatch.setattr(retrieval.settings, "AI_PORTFOLIO_RRF_CANDIDATE_MULTIPLIER", 10)
    criteria = RetrievalCriteria(text="不要室内", limit=3)
    result = _rank_portfolio_rrf(
        [
            _document(1, "indoor", title="室内棚拍", tags=["室内"], visual_score=0.99, semantic_score=0.9),
            _document(2, "outdoor", title="室外公园", tags=["室外"], visual_score=0.8, semantic_score=0.8),
        ],
        criteria,
        3,
        None,
        content="不要室内，换成室外",
    )

    assert [item["id"] for item in result["items"]] == ["outdoor"]
    assert result["weights"]["negative_terms"] == ["室内"]
