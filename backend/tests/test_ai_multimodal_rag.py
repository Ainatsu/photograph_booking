import pytest

from backend.app.models.ai_resource import AIResourceImageEmbedding
from backend.app.services import ai_multimodal_embedding_service
from backend.app.services import ai_retrieval_service
from backend.app.services.ai_multimodal_embedding_service import sync_resource_image_embeddings
from backend.app.services.ai_resource_index_service import rebuild_ai_resource_documents
from backend.app.services.ai_retrieval_service import retrieve_references
from backend.app.services.ai_retrieval_service import RetrievalCriteria, _rank_documents


def _vision_analysis(*terms: str) -> dict:
    return {
        "summary": " ".join(terms),
        "style": list(terms),
        "scene": [],
        "mood": [],
        "lighting": [],
        "color": [],
        "composition": [],
        "makeup": [],
        "search_terms": list(terms),
    }


@pytest.fixture(autouse=True)
def legacy_mock_image_embedding(monkeypatch):
    monkeypatch.setattr(ai_multimodal_embedding_service.settings, "AI_IMAGE_EMBEDDING_PROVIDER", "mock")
    monkeypatch.setattr(ai_retrieval_service.settings, "AI_IMAGE_EMBEDDING_PROVIDER", "mock")


def test_portfolio_image_embeddings_are_incremental(db, photographer_profile):
    photographer_profile.portfolio = [
        {
            "id": "visual-soft",
            "url": "/static/portfolio/visual-soft.jpg",
            "media_type": "image",
            "title": "soft window portrait",
            "description": "bright natural window light cream tone",
            "tags": ["soft", "window", "cream"],
        }
    ]
    db.commit()
    rebuild_ai_resource_documents(db)

    assert db.query(AIResourceImageEmbedding).count() == 1
    unchanged = sync_resource_image_embeddings(db)
    assert unchanged.embedded == 0
    assert unchanged.skipped == 1

    updated_item = dict(photographer_profile.portfolio[0])
    updated_item["description"] = "bright natural window light warm cream tone"
    photographer_profile.portfolio = [updated_item]
    db.commit()
    rebuild_ai_resource_documents(db)

    refreshed = sync_resource_image_embeddings(db)
    assert refreshed.embedded == 0
    row = db.query(AIResourceImageEmbedding).one()
    assert "warm cream" in row.visual_descriptor


def test_reference_image_ranks_similar_portfolio_first(db, photographer_profile):
    photographer_profile.portfolio = [
        {
            "id": "soft-window",
            "url": "/static/portfolio/soft-window.jpg",
            "media_type": "image",
            "title": "soft window portrait",
            "description": "bright natural window light cream tone",
            "tags": ["soft", "window", "cream"],
        },
        {
            "id": "dark-stage",
            "url": "/static/portfolio/dark-stage.jpg",
            "media_type": "image",
            "title": "dark stage portrait",
            "description": "hard red spotlight black background",
            "tags": ["dark", "stage", "red"],
        },
    ]
    db.commit()
    rebuild_ai_resource_documents(db)

    retrieval = retrieve_references(
        db,
        "find similar portfolio images",
        resource_types=["portfolio_items"],
        vision_analysis=_vision_analysis("soft", "window", "cream", "natural light"),
        limit=2,
    )
    works = retrieval["references"]["portfolio_items"]

    assert works[0]["id"] == "soft-window"
    assert works[0]["_rag"]["visual_score"] > works[1]["_rag"]["visual_score"]
    assert works[0]["_rag"]["fusion_mode"] == "weighted_rrf"
    assert retrieval["diagnostics"]["multimodal"]["enabled"] is True
    siglip_debug = retrieval["diagnostics"]["multimodal"]["siglip_top_10"]
    assert siglip_debug[0]["portfolio_item_id"] == "soft-window"
    assert siglip_debug[0]["image_rank"] == 1
    assert siglip_debug[0]["visual_score"] > siglip_debug[1]["visual_score"]


def test_visual_match_propagates_to_owner_package(db, photographer_profile):
    photographer_profile.portfolio = [
        {
            "id": "film-work",
            "url": "/static/portfolio/film-work.jpg",
            "media_type": "image",
            "title": "cinematic seaside sunset",
            "description": "warm film grain documentary couple portrait",
            "tags": ["cinematic", "sunset", "film grain"],
        }
    ]
    photographer_profile.packages = [
        {
            "id": "film-package",
            "name": "seaside couple session",
            "price": 1200,
            "description": "cinematic documentary session",
            "styles": ["cinematic"],
        }
    ]
    db.commit()
    rebuild_ai_resource_documents(db)

    retrieval = retrieve_references(
        db,
        "find a package matching this reference",
        resource_types=["packages"],
        vision_analysis=_vision_analysis("cinematic", "seaside", "sunset", "film grain"),
    )
    packages = retrieval["references"]["packages"]

    assert packages[0]["id"] == "film-package"
    assert packages[0]["_rag"]["visual_score"] > 0
    assert retrieval["diagnostics"]["multimodal"]["matched_owners"] == 1


def test_native_image_query_uses_visual_primary_ranking_and_soft_style_terms():
    criteria = RetrievalCriteria(
        text="find a similar film image",
        terms=["film"],
        style_terms=["film"],
    )
    documents = [
        {
            "id": "visual-match",
            "resource_type": "portfolio_item",
            "title": "untagged portrait",
            "summary": "",
            "tags": [],
            "embedding": [],
            "visual_score": 0.92,
            "conversion_score": 0.1,
            "payload": {"id": "visual-match"},
        },
        {
            "id": "text-match",
            "resource_type": "portfolio_item",
            "title": "film portrait",
            "summary": "film style",
            "tags": ["film"],
            "embedding": [],
            "visual_score": 0.18,
            "conversion_score": 0.1,
            "payload": {"id": "text-match"},
        },
    ]

    ranked = _rank_documents(documents, criteria, 2, image_query=True)

    assert [item["id"] for item in ranked] == ["visual-match", "text-match"]
    assert ranked[0]["_rag"]["fusion_mode"] == "image_primary"


def test_retrieval_does_not_rebuild_image_index_in_request_path(db, photographer_profile, monkeypatch):
    photographer_profile.portfolio = [
        {
            "id": "indexed-work",
            "url": "/static/portfolio/indexed-work.jpg",
            "media_type": "image",
            "title": "indexed work",
            "description": "soft portrait",
            "tags": ["soft"],
        }
    ]
    db.commit()
    rebuild_ai_resource_documents(db)

    def fail_if_called(*args, **kwargs):
        raise AssertionError("online retrieval must not synchronize the image index")

    monkeypatch.setattr(ai_multimodal_embedding_service, "sync_resource_image_embeddings", fail_if_called)

    retrieval = retrieve_references(
        db,
        "find similar portfolio images",
        resource_types=["portfolio_items"],
        vision_analysis=_vision_analysis("soft"),
        limit=1,
    )

    assert retrieval["references"]["portfolio_items"]
