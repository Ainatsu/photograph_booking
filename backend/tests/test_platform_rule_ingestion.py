"""平台规则文档切分与入库测试：chunker、幂等 upsert、失效删除与重建防误删。"""

import pytest

from backend.app.models.ai_resource import AIResourceDocument
from backend.app.services.ai_resource_index_service import rebuild_ai_resource_documents
from backend.app.services.platform_rule_service import (
    RULE_RESOURCE_TYPE,
    collect_rule_chunks,
    ensure_platform_rules_indexed,
    parse_rule_document,
    sync_platform_rules,
)

# 与 docs/rules 同结构的迷你语料：覆盖 H1/H2、规则编号、子条目与跳过 README。
_SAMPLE_DOC = """# 订单规则

适用对象：全部订单。

## 退款规则

- 规 OR-1：取消订单须填写原因：
  - 客户发起时必须说明理由；
  - 摄影师发起时同样必须说明理由。
- 规 OR-2：退款按时间梯度计算：
  - 超过 72 小时退 90%；
  - 24 到 72 小时退 50%。

## 交付规则

- 规 OR-3：验收窗口为交付后 5 天。
"""


def _write_rules_dir(tmp_path, docs: dict[str, str]) -> str:
    (tmp_path / "README.md").write_text("# 规则索引\n\n这是元文档，不应入库。\n", encoding="utf-8")
    for name, content in docs.items():
        (tmp_path / name).write_text(content, encoding="utf-8")
    return str(tmp_path)


class TestRuleChunker:
    def test_real_rules_directory_is_parsed(self):
        chunks = collect_rule_chunks()
        # 真实语料 7 份文档、145 条规则；若大规模删改规则文档，请同步更新此断言。
        assert len(chunks) >= 100
        doc_keys = {chunk.doc_key for chunk in chunks}
        assert "order-payment-rules" in doc_keys
        assert all(chunk.doc_key != "README" for chunk in chunks)

    def test_chunk_structure_and_ids(self, tmp_path):
        doc = tmp_path / "order-rules.md"
        doc.write_text(_SAMPLE_DOC, encoding="utf-8")
        chunks = parse_rule_document(doc)
        assert [chunk.rule_id for chunk in chunks] == ["OR-1", "OR-2", "OR-3"]
        assert chunks[0].doc_title == "订单规则"
        assert chunks[0].section == "退款规则"
        assert chunks[0].resource_id == "order-rules#OR-1"

    def test_sub_bullets_stay_with_their_rule(self, tmp_path):
        doc = tmp_path / "order-rules.md"
        doc.write_text(_SAMPLE_DOC, encoding="utf-8")
        chunks = {chunk.rule_id: chunk for chunk in parse_rule_document(doc)}
        assert "客户发起时必须说明理由" in chunks["OR-1"].text
        assert "摄影师发起时同样必须说明理由" in chunks["OR-1"].text
        assert "超过 72 小时退 90%" in chunks["OR-2"].text
        # 子条目不能溢出到相邻规则块。
        assert "退 90%" not in chunks["OR-1"].text
        assert chunks["OR-3"].text == "规 OR-3：验收窗口为交付后 5 天。"


class TestSyncPlatformRules:
    def test_sync_upserts_and_skips_readme(self, db, tmp_path):
        rules_dir = _write_rules_dir(tmp_path, {"order-rules.md": _SAMPLE_DOC})
        result = sync_platform_rules(db, rules_dir=rules_dir)
        assert result["documents"] == 3
        rows = db.query(AIResourceDocument).filter_by(resource_type=RULE_RESOURCE_TYPE).all()
        assert {row.resource_id for row in rows} == {
            "order-rules#OR-1",
            "order-rules#OR-2",
            "order-rules#OR-3",
        }
        for row in rows:
            payload = row.payload or {}
            assert payload["rule_id"]
            assert payload["doc_key"] == "order-rules"
            assert row.search_text.startswith(f"规 {payload['rule_id']}：")
            assert row.owner_user_id == 0

    def test_sync_is_idempotent(self, db, tmp_path):
        rules_dir = _write_rules_dir(tmp_path, {"order-rules.md": _SAMPLE_DOC})
        sync_platform_rules(db, rules_dir=rules_dir)
        first_ids = sorted(
            row.id
            for row in db.query(AIResourceDocument).filter_by(resource_type=RULE_RESOURCE_TYPE)
        )
        sync_platform_rules(db, rules_dir=rules_dir)
        rows = db.query(AIResourceDocument).filter_by(resource_type=RULE_RESOURCE_TYPE).all()
        assert sorted(row.id for row in rows) == first_ids
        assert len(rows) == 3

    def test_sync_deletes_stale_rules(self, db, tmp_path):
        rules_dir = _write_rules_dir(tmp_path, {"order-rules.md": _SAMPLE_DOC})
        sync_platform_rules(db, rules_dir=rules_dir)
        # 移除 OR-3 后重新同步：失效规则必须被清掉。
        (tmp_path / "order-rules.md").write_text(
            _SAMPLE_DOC.split("- 规 OR-3")[0], encoding="utf-8"
        )
        result = sync_platform_rules(db, rules_dir=rules_dir)
        assert result["documents"] == 2
        remaining = {
            row.resource_id
            for row in db.query(AIResourceDocument).filter_by(resource_type=RULE_RESOURCE_TYPE)
        }
        assert "order-rules#OR-3" not in remaining

    def test_ensure_skips_when_up_to_date(self, db, tmp_path, monkeypatch):
        rules_dir = _write_rules_dir(tmp_path, {"order-rules.md": _SAMPLE_DOC})
        monkeypatch.setattr("backend.app.core.config.settings.AI_PLATFORM_RULES_DIR", rules_dir)
        first = ensure_platform_rules_indexed(db)
        assert first.get("documents") == 3
        second = ensure_platform_rules_indexed(db)
        assert second.get("skipped") is True
        assert second.get("reason") == "up_to_date"
        # 内容变化后不再跳过。
        (tmp_path / "order-rules.md").write_text(
            _SAMPLE_DOC + "- 规 OR-9：新增规则。\n", encoding="utf-8"
        )
        third = ensure_platform_rules_indexed(db)
        assert third.get("documents") == 4

    def test_ensure_skips_when_disabled(self, db, tmp_path, monkeypatch):
        monkeypatch.setattr("backend.app.core.config.settings.AI_PLATFORM_RULES_ENABLED", False)
        result = ensure_platform_rules_indexed(db)
        assert result == {"skipped": True, "reason": "disabled"}


class TestRebuildDoesNotPurgeRules:
    def test_full_rebuild_keeps_platform_rule_rows(self, db, tmp_path, photographer_profile):
        """全量重建摄影师资源索引时，规则文档行不能被当成 stale 清掉。"""
        rules_dir = _write_rules_dir(tmp_path, {"order-rules.md": _SAMPLE_DOC})
        sync_platform_rules(db, rules_dir=rules_dir)
        assert (
            db.query(AIResourceDocument).filter_by(resource_type=RULE_RESOURCE_TYPE).count()
            == 3
        )

        rebuild_ai_resource_documents(db, sync_embeddings=False)

        assert (
            db.query(AIResourceDocument).filter_by(resource_type=RULE_RESOURCE_TYPE).count()
            == 3
        )
