"""平台规则向量检索测试：mock embedding 下命中、空库、top_k 与开关。"""

import pytest

from backend.app.services.platform_rule_service import (
    build_platform_rules_context,
    search_platform_rules,
    sync_platform_rules,
)

_RULES_MD = """# 订单规则

## 退款规则

- 规 OR-1：客户责任取消订单，距预约时间超过 72 小时退还 90%。
- 规 OR-2：客户责任取消订单，距预约时间 24 到 72 小时退还 50%。
- 规 OR-3：客户责任取消订单，距预约时间不足 24 小时不予退款。

## 交付规则

- 规 OR-4：验收窗口为交付提交后 5 天，期满系统自动验收。
"""


@pytest.fixture
def rules_store(db, tmp_path):
    (tmp_path / "order-rules.md").write_text(_RULES_MD, encoding="utf-8")
    (tmp_path / "README.md").write_text("# 索引\n", encoding="utf-8")
    sync_platform_rules(db, rules_dir=str(tmp_path))
    return db


class TestSearchPlatformRules:
    def test_returns_hits_with_rule_metadata(self, rules_store):
        hits = search_platform_rules(rules_store, "取消订单退款比例怎么算")
        assert hits, "入库后不应返回空结果"
        for hit in hits:
            assert hit["rule_id"].startswith("OR-")
            assert hit["doc_key"] == "order-rules"
            assert hit["text"].startswith("规 ")
            assert 0.0 <= hit["score"] <= 1.0
        # 分数按降序排列。
        scores = [hit["score"] for hit in hits]
        assert scores == sorted(scores, reverse=True)

    def test_hits_are_limited_by_top_k(self, rules_store):
        all_hits = search_platform_rules(rules_store, "退款", limit=10)
        assert len(all_hits) == 4
        limited = search_platform_rules(rules_store, "退款", limit=2)
        assert len(limited) == 2
        assert limited == all_hits[:2]

    def test_exact_rule_text_ranks_first(self, rules_store):
        query = "验收窗口为交付提交后 5 天"
        hits = search_platform_rules(rules_store, query)
        assert hits[0]["rule_id"] == "OR-4"

    def test_empty_query_returns_nothing(self, rules_store):
        assert search_platform_rules(rules_store, "   ") == []

    def test_empty_store_returns_nothing(self, db):
        assert search_platform_rules(db, "退款政策") == []

    def test_disabled_setting_returns_nothing(self, rules_store, monkeypatch):
        monkeypatch.setattr("backend.app.core.config.settings.AI_PLATFORM_RULES_ENABLED", False)
        assert search_platform_rules(rules_store, "退款政策") == []


class TestBuildContext:
    def test_context_contains_rule_ids_and_text(self, rules_store):
        hits = search_platform_rules(rules_store, "退款", limit=2)
        context = build_platform_rules_context(hits)
        assert context is not None
        assert "search_platform_rules" in context
        for hit in hits:
            assert f"规 {hit['rule_id']}" in context
            assert hit["section"] in context

    def test_empty_hits_context_is_none(self):
        assert build_platform_rules_context([]) is None
        assert build_platform_rules_context(None) is None
