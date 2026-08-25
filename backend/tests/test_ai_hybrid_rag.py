from backend.app.models.ai_resource import AIResourceDocument, AIResourceEmbedding
from backend.app.services.ai_embedding_service import sync_resource_embeddings
from backend.app.services.ai_resource_index_service import rebuild_ai_resource_documents
from backend.app.services.ai_retrieval_service import retrieve_references
from backend.app.services.ai_rag_evaluation_service import evaluate_rag_cases, load_rag_cases
from pathlib import Path


def test_resource_embeddings_are_created_and_incremental(db, photographer_profile):
    document_count = rebuild_ai_resource_documents(db)

    assert db.query(AIResourceDocument).count() == document_count
    assert db.query(AIResourceEmbedding).count() == document_count

    unchanged = sync_resource_embeddings(db)
    assert unchanged.embedded == 0
    assert unchanged.skipped == document_count

    photographer_profile.user.bio = "更新后的自然光、清新、生活感摄影简介"
    db.commit()
    rebuild_ai_resource_documents(db, owner_user_id=photographer_profile.user_id)

    refreshed = db.query(AIResourceEmbedding).join(AIResourceDocument).filter(
        AIResourceDocument.resource_type == "photographer",
        AIResourceDocument.owner_user_id == photographer_profile.user_id,
    ).one()
    document = db.query(AIResourceDocument).filter(
        AIResourceDocument.resource_type == "photographer",
        AIResourceDocument.owner_user_id == photographer_profile.user_id,
    ).one()
    assert refreshed.content_hash == document.content_hash


def test_hybrid_rag_semantic_recall_without_literal_keyword(db, photographer_profile):
    photographer_profile.portfolio = [
        {
            "id": "soft-light",
            "url": "/static/soft.jpg",
            "title": "晨间校园",
            "description": "自然光通透，清新柔和的校园氛围",
            "tags": ["清新", "自然光"],
        },
        {
            "id": "dark-commercial",
            "url": "/static/dark.jpg",
            "title": "暗调商业棚拍",
            "description": "高反差硬朗灯光与黑色背景",
            "tags": ["商业", "暗调"],
        },
    ]
    db.commit()
    rebuild_ai_resource_documents(db)

    retrieval = retrieve_references(
        db,
        "找温柔明亮氛围的作品",
        resource_types=["portfolio_items"],
        limit=2,
    )
    works = retrieval["references"]["portfolio_items"]

    assert works
    assert works[0]["id"] == "soft-light"
    assert works[0]["_rag"]["semantic_score"] > 0
    assert retrieval["diagnostics"]["retrieval_mode"] == "hybrid"


def test_hybrid_rag_preserves_hard_city_and_budget_filters(db, photographer_profile):
    photographer_profile.location = "北京"
    photographer_profile.packages = [
        {
            "id": "within-budget",
            "name": "自然纪实写真",
            "price": 900,
            "duration": 120,
            "description": "轻松生活感与自然纪实",
            "styles": ["纪实"],
        },
        {
            "id": "over-budget",
            "name": "自然纪实高端方案",
            "price": 2600,
            "duration": 180,
            "description": "轻松生活感与自然纪实",
            "styles": ["纪实"],
        },
    ]
    db.commit()
    rebuild_ai_resource_documents(db)

    retrieval = retrieve_references(
        db,
        "找北京预算1000以内、有生活感的套餐",
        resource_types=["packages"],
    )
    packages = retrieval["references"]["packages"]

    assert [item["id"] for item in packages] == ["within-budget"]
    assert packages[0]["_rag"]["business_score"] > 0


def test_hybrid_rag_golden_dataset():
    dataset = Path(__file__).resolve().parents[1] / "evals" / "hybrid_rag_golden.jsonl"
    report = evaluate_rag_cases(load_rag_cases(dataset))
    assert report["accuracy"] == 1.0, report
