import pytest
from pydantic import ValidationError

from backend.app.services.ai_agent_decision_contracts import SearchWebInput
from backend.app.services.ai_tool_policy_service import authorize_tool_call
from backend.app.services.ai_web_search_context_service import build_web_search_context
from backend.app.services.ai_web_search_citation_service import enforce_web_citations
from backend.app.services.ai_agent_decision_service import infer_explicit_web_search_decision
from backend.app.services.web_search_provider import WebSearchProviderError


def test_search_web_limit_cannot_exceed_five():
    with pytest.raises(ValidationError):
        SearchWebInput(query="Hong Kong events", limit=6)


def test_search_web_rejects_urls_in_domain_filters():
    parsed = SearchWebInput(query="Hong Kong events", include_domains=["https://example.com/path"])
    assert parsed.include_domains == []


def test_search_web_is_authorized_as_read_only():
    authorization = authorize_tool_call("search_web", arguments={"query": "Hong Kong events", "limit": 5})
    assert authorization.allowed is True
    assert authorization.spec.risk_level.value == "read_only"


def test_web_context_marks_external_content_untrusted_and_keeps_real_url():
    context = build_web_search_context({
        "task_form_id": "conversation_1_message_2",
        "query": "Hong Kong events",
        "items": [{"rank": 1, "title": "Example", "url": "https://example.com/a", "domain": "example.com", "snippet": "Text"}],
    })
    assert "untrusted external data" in context
    assert "https://example.com/a" in context


def test_citation_enforcement_removes_fake_url_and_appends_real_source():
    content, warnings = enforce_web_citations(
        "Claim https://fake.example/a",
        [{"rank": 1, "title": "Real", "url": "https://example.com/real"}],
    )
    assert "fake.example" not in content
    assert "https://example.com/real" in content
    assert warnings == ["unapproved_url_removed", "source_list_appended"]


def test_wrong_web_number_url_mapping_is_rejected():
    content, warnings = enforce_web_citations(
        "[WEB-1](https://example.com/two)",
        [{"rank": 1, "title": "One", "url": "https://example.com/one"}],
    )
    assert "https://example.com/two" not in content
    assert "https://example.com/one" in content
    assert "invalid_web_citation_removed" in warnings


def test_explicit_web_search_does_not_fall_back_to_photographer_search():
    decision = infer_explicit_web_search_decision("大理有哪些推荐的拍摄地点？联网搜索")
    assert decision is not None
    assert decision.tool == "search_web"
    assert "大理" in decision.arguments["query"]


def test_provider_error_codes_are_structured():
    error = WebSearchProviderError("provider_auth_failed", 401)
    assert error.code == "provider_auth_failed"
    assert error.status_code == 401
