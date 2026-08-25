"""阶段C（灰度替换独立分类器）测试。

覆盖 codex-agent-llm-tool-routing-refactor-guide.md §4 阶段C 的：
- C1/C2 按用户、会话、比例灰度，以及白/黑名单与回滚开关；
- C3 灰度五项指标：工具成功率、无结果率、错误工具率、重复推荐率、写操作拦截率；
- C4 决策层接管时不再重复跑分类 LLM（开关默认关闭）；
- C5 规则识别退为离线评估与兜底组件。
"""

import json

import pytest

from backend.app.models.ai_production import AgentTrace
from backend.app.models.photographer import PhotographerProfile
from backend.app.services import agent_routing_gate as routing_gate
from backend.app.services import ai_service
from backend.app.services import ai_agent_decision_service as decision_service
from backend.app.services.agent_routing_gate import (
    ROUTING_ROLLOUT_SCHEMA_VERSION,
    resolve_routing_mode,
    resolve_routing_rollout,
    rollout_bucket,
)
from backend.app.services.ai_evaluation_service import load_golden_cases
from backend.app.services.ai_offline_eval_service import (
    evaluate_rules_tool_selection,
    replay_agent_traces,
)
from backend.app.services.ai_resource_index_service import rebuild_ai_resource_documents
from backend.app.services.ai_trace_service import (
    agent_quality_dashboard,
    decision_rollout_metrics,
    rollout_coverage,
)


TOOL_SELECTION_DATASET = "backend/evals/agent_phase_c_tool_selection.jsonl"


# ── Fakes ───────────────────────────────────────────────────────────────────


class RecordingProvider:
    def __init__(self, content: str = "好的，我按平台真实候选来回答。"):
        self.content = content
        self.messages_history: list[list[dict]] = []

    async def chat(self, messages, *, temperature=None, response_format=None):
        self.messages_history.append(messages)
        return {
            "content": self.content,
            "metadata": {"model": {"provider": "test", "model": "test-model"}},
        }


class DecisionProvider:
    def __init__(self, *decisions: dict):
        self.decisions = list(decisions) or [{}]
        self.calls: list[list[dict]] = []

    async def chat(self, messages, *, temperature=None, response_format=None):
        self.calls.append(messages)
        payload = self.decisions.pop(0) if len(self.decisions) > 1 else self.decisions[0]
        content = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
        return {
            "content": content,
            "metadata": {"model": {"provider": "test", "model": "decider-test"}},
        }


def _search_decision(**overrides) -> dict:
    payload = {
        "mode": "tool_call",
        "tool": "search_packages",
        "arguments": {"city": "重庆", "styles": ["婚礼"], "limit": 1},
        "confidence": 0.93,
        "reason": "用户在问套餐",
    }
    payload.update(overrides)
    return payload


def _rollout(monkeypatch, **overrides):
    """设置灰度配置；未指定的项保持默认值。"""
    defaults = {
        "AGENT_ROUTING_MODE": "legacy",
        "AGENT_ROUTING_BASELINE_MODE": "legacy",
        "AGENT_ROUTING_ROLLOUT_PERCENT": 100,
        "AGENT_ROUTING_ROLLOUT_UNIT": "user",
        "AGENT_ROUTING_ROLLOUT_ALLOWLIST": "",
        "AGENT_ROUTING_ROLLOUT_DENYLIST": "",
        "AI_DECISION_SKIPS_INTENT_CLASSIFIER": False,
    }
    defaults.update(overrides)
    for key, value in defaults.items():
        monkeypatch.setattr(routing_gate.settings, key, value)


def _use_providers(monkeypatch, decision_provider, final_provider):
    monkeypatch.setattr(ai_service.settings, "AI_INTENT_CLASSIFIER_MODE", "rules")
    monkeypatch.setattr(decision_service, "get_text_provider", lambda: decision_provider)
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: final_provider)


@pytest.fixture
def wedding_packages(db, photographer_user):
    profile = PhotographerProfile(
        user_id=photographer_user.id,
        location="重庆",
        styles=["婚礼跟拍", "婚宴"],
        packages=[
            {
                "id": "pkg-cq-wedding-day",
                "name": "婚宴全天跟拍",
                "price": 2680,
                "duration": 480,
                "description": "婚礼仪式与晚宴全程跟拍",
                "includes": ["精修80张", "含妆造"],
                "styles": ["婚礼跟拍"],
                "image_count": 80,
            },
            {
                "id": "pkg-cq-wedding-half",
                "name": "婚礼半天套餐",
                "price": 1580,
                "duration": 240,
                "description": "婚礼上午仪式跟拍",
                "includes": ["精修40张"],
                "styles": ["婚宴"],
                "image_count": 40,
            },
        ],
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    rebuild_ai_resource_documents(db)
    return profile


# ── C1 / C2 灰度分桶 ────────────────────────────────────────────────────────


class TestRoutingRollout:
    def test_percent_full_keeps_phase_b_semantics(self, monkeypatch):
        """只改 AGENT_ROUTING_MODE 时行为与阶段B 一致：全量生效，不分桶。"""
        _rollout(monkeypatch, AGENT_ROUTING_MODE="tool_loop")
        rollout = resolve_routing_rollout(user_id=1, conversation_id=2)
        assert rollout.mode == "tool_loop"
        assert rollout.in_rollout is True
        assert rollout.reason == "percent_full"
        assert rollout.bucket is None

    def test_percent_zero_falls_back_to_baseline(self, monkeypatch):
        _rollout(monkeypatch, AGENT_ROUTING_MODE="tool_loop", AGENT_ROUTING_ROLLOUT_PERCENT=0)
        rollout = resolve_routing_rollout(user_id=1)
        assert rollout.mode == "legacy"
        assert rollout.reason == "percent_zero"

    def test_target_equal_to_baseline_skips_bucketing(self, monkeypatch):
        _rollout(monkeypatch, AGENT_ROUTING_MODE="legacy", AGENT_ROUTING_ROLLOUT_PERCENT=30)
        rollout = resolve_routing_rollout(user_id=1)
        assert rollout.mode == "legacy"
        assert rollout.reason == "target_is_baseline"

    def test_baseline_can_be_shadow_while_target_is_tool_loop(self, monkeypatch):
        """线上常见组合：全量 shadow 观察，同时按比例放 tool_loop（§7.6）。"""
        _rollout(
            monkeypatch,
            AGENT_ROUTING_MODE="tool_loop",
            AGENT_ROUTING_BASELINE_MODE="shadow",
            AGENT_ROUTING_ROLLOUT_PERCENT=0,
        )
        assert resolve_routing_rollout(user_id=1).mode == "shadow"

    def test_bucket_is_stable_for_the_same_user(self, monkeypatch):
        _rollout(monkeypatch, AGENT_ROUTING_MODE="tool_loop", AGENT_ROUTING_ROLLOUT_PERCENT=50)
        first = resolve_routing_rollout(user_id=42)
        second = resolve_routing_rollout(user_id=42)
        assert first.bucket == second.bucket
        assert first.mode == second.mode
        assert first.identity == "user:42"

    def test_rollout_percent_roughly_matches_the_bucket_share(self, monkeypatch):
        _rollout(monkeypatch, AGENT_ROUTING_MODE="tool_loop", AGENT_ROUTING_ROLLOUT_PERCENT=10)
        modes = [resolve_routing_mode(user_id=index) for index in range(1, 301)]
        share = modes.count("tool_loop") / len(modes)
        assert 0.03 <= share <= 0.20

    def test_conversation_unit_buckets_by_conversation(self, monkeypatch):
        _rollout(
            monkeypatch,
            AGENT_ROUTING_MODE="tool_loop",
            AGENT_ROUTING_ROLLOUT_PERCENT=50,
            AGENT_ROUTING_ROLLOUT_UNIT="conversation",
        )
        rollout = resolve_routing_rollout(user_id=1, conversation_id=99)
        assert rollout.unit == "conversation"
        assert rollout.identity == "conversation:99"
        assert rollout.bucket == rollout_bucket("conversation:99")

    def test_global_unit_is_all_or_nothing(self, monkeypatch):
        _rollout(
            monkeypatch,
            AGENT_ROUTING_MODE="tool_loop",
            AGENT_ROUTING_ROLLOUT_PERCENT=50,
            AGENT_ROUTING_ROLLOUT_UNIT="global",
        )
        rollout = resolve_routing_rollout(user_id=1)
        assert rollout.mode == "legacy"
        assert rollout.bucket is None

    def test_allowlist_forces_the_target_mode(self, monkeypatch):
        _rollout(
            monkeypatch,
            AGENT_ROUTING_MODE="tool_loop",
            AGENT_ROUTING_ROLLOUT_PERCENT=0,
            AGENT_ROUTING_ROLLOUT_ALLOWLIST="7, 8",
        )
        assert resolve_routing_rollout(user_id=8).reason == "allowlist"
        assert resolve_routing_rollout(user_id=8).mode == "tool_loop"
        assert resolve_routing_rollout(user_id=9).mode == "legacy"

    def test_denylist_wins_over_allowlist(self, monkeypatch):
        """临时止血：黑名单必须能立刻把某个账号踢回 legacy（§8）。"""
        _rollout(
            monkeypatch,
            AGENT_ROUTING_MODE="tool_loop",
            AGENT_ROUTING_ROLLOUT_ALLOWLIST="7",
            AGENT_ROUTING_ROLLOUT_DENYLIST="7",
        )
        rollout = resolve_routing_rollout(user_id=7)
        assert rollout.reason == "denylist"
        assert rollout.mode == "legacy"

    @pytest.mark.parametrize("bad_mode", ["", "unknown", "tool-loop", None])
    def test_unknown_mode_degrades_to_legacy(self, monkeypatch, bad_mode):
        """配错模式名不能把请求打进未定义分支，只能退回 legacy。"""
        _rollout(monkeypatch, AGENT_ROUTING_MODE=bad_mode)
        assert resolve_routing_rollout(user_id=1).mode == "legacy"

    def test_mode_and_unit_are_case_insensitive(self, monkeypatch):
        _rollout(
            monkeypatch,
            AGENT_ROUTING_MODE=" TOOL_LOOP ",
            AGENT_ROUTING_ROLLOUT_UNIT="Conversation",
            AGENT_ROUTING_ROLLOUT_PERCENT=50,
        )
        rollout = resolve_routing_rollout(user_id=1, conversation_id=99)
        assert rollout.target_mode == "tool_loop"
        assert rollout.unit == "conversation"

    @pytest.mark.parametrize("percent,expected", [(-10, 0), (0, 0), (55, 55), (140, 100)])
    def test_percent_is_clamped(self, percent, expected):
        assert routing_gate.normalize_rollout_percent(percent) == expected

    def test_anonymous_identity_still_buckets(self, monkeypatch):
        _rollout(monkeypatch, AGENT_ROUTING_MODE="tool_loop", AGENT_ROUTING_ROLLOUT_PERCENT=50)
        rollout = resolve_routing_rollout()
        assert rollout.identity == "user:anonymous"
        assert rollout.bucket == rollout_bucket("user:anonymous")

    def test_as_dict_never_leaks_the_identity(self, monkeypatch):
        """归因字段可以进消息元数据，但用户标识不必落库（§5.5）。"""
        _rollout(monkeypatch, AGENT_ROUTING_MODE="tool_loop", AGENT_ROUTING_ROLLOUT_PERCENT=50)
        payload = resolve_routing_rollout(user_id=42).as_dict()
        assert payload["schema_version"] == ROUTING_ROLLOUT_SCHEMA_VERSION
        assert "identity" not in payload
        assert set(payload) == {
            "schema_version",
            "mode",
            "target_mode",
            "baseline_mode",
            "unit",
            "percent",
            "in_rollout",
            "reason",
            "bucket",
        }


# ── C2 端到端：命中与未命中 ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_user_outside_the_rollout_never_calls_the_decider(
    db, customer_user, wedding_packages, monkeypatch
):
    """未命中灰度的用户完全走既有链路，连决策器都不调用。"""
    decision_provider = DecisionProvider(_search_decision())
    final_provider = RecordingProvider()
    _use_providers(monkeypatch, decision_provider, final_provider)
    _rollout(
        monkeypatch,
        AGENT_ROUTING_MODE="tool_loop",
        AGENT_ROUTING_ROLLOUT_PERCENT=0,
    )
    conversation = ai_service.create_conversation(db, customer_user.id)

    _, message = await ai_service.send_ai_message(
        db, customer_user.id, conversation.id, "推荐重庆婚礼拍摄方案"
    )

    assert decision_provider.calls == []
    assert "agent_decision" not in message.message_metadata
    routing = message.message_metadata["agent_routing"]
    assert routing["mode"] == "legacy"
    assert routing["target_mode"] == "tool_loop"
    assert routing["in_rollout"] is False
    assert routing["reason"] == "percent_zero"


@pytest.mark.asyncio
async def test_allowlisted_user_gets_the_tool_loop(
    db, customer_user, wedding_packages, monkeypatch
):
    """白名单账号即使比例为 0 也能走新链路：测试环境启用就靠它（C1）。"""
    decision_provider = DecisionProvider(_search_decision())
    final_provider = RecordingProvider()
    _use_providers(monkeypatch, decision_provider, final_provider)
    _rollout(
        monkeypatch,
        AGENT_ROUTING_MODE="tool_loop",
        AGENT_ROUTING_ROLLOUT_PERCENT=0,
        AGENT_ROUTING_ROLLOUT_ALLOWLIST=str(customer_user.id),
    )
    conversation = ai_service.create_conversation(db, customer_user.id)

    _, message = await ai_service.send_ai_message(
        db, customer_user.id, conversation.id, "推荐重庆婚礼拍摄方案"
    )
    metadata = message.message_metadata

    assert len(decision_provider.calls) == 1
    assert metadata["agent_routing"]["reason"] == "allowlist"
    assert metadata["agent_decision"]["routing_mode"] == "tool_loop"
    assert metadata["agent_decision"]["applied"] is True
    assert metadata["tool_call"]["tool"] == "search_packages"


@pytest.mark.asyncio
async def test_routing_attribution_is_recorded_for_legacy_traffic_too(
    db, customer_user, wedding_packages, monkeypatch
):
    """灰度覆盖率要能算出来，所以 legacy 侧也要落 routing 归因。"""
    final_provider = RecordingProvider()
    _use_providers(monkeypatch, DecisionProvider(_search_decision()), final_provider)
    _rollout(monkeypatch)
    conversation = ai_service.create_conversation(db, customer_user.id)

    await ai_service.send_ai_message(db, customer_user.id, conversation.id, "推荐重庆婚礼方案")
    trace = db.query(AgentTrace).order_by(AgentTrace.id.desc()).first()

    assert trace.quality_flags["routing_mode"] == "legacy"
    assert trace.quality_flags["routing_in_rollout"] is True
    assert trace.quality_flags["routing_reason"] == "target_is_baseline"


# ── C3 灰度五项指标 ────────────────────────────────────────────────────────


class TestRolloutMetrics:
    def test_tool_call_rates_are_mutually_exclusive(self):
        metrics = decision_rollout_metrics([
            {"tool_call_tool": "search_packages", "tool_call_status": "success"},
            {"tool_call_tool": "search_packages", "tool_call_status": "success"},
            {"tool_call_tool": "search_packages", "tool_call_status": "empty"},
            {"tool_call_tool": "search_projects", "tool_call_status": "failed"},
        ])
        assert metrics["tool_calls"] == 4
        assert metrics["tool_success_rate"] == 0.5
        assert metrics["no_result_rate"] == 0.25
        assert metrics["tool_error_rate"] == 0.25

    def test_wrong_tool_rate_counts_tools_the_backend_refused(self):
        metrics = decision_rollout_metrics([
            {
                "decision_routing_mode": "tool_loop",
                "decision_tool": "search_projects",
                "decision_not_applied_reason": "role_not_allowed:customer",
            },
            {
                "decision_routing_mode": "tool_loop",
                "decision_tool": "search_packages",
                "decision_not_applied_reason": None,
            },
        ])
        assert metrics["tool_proposals"] == 2
        assert metrics["wrong_tool_rate"] == 0.5

    def test_low_confidence_fallback_is_not_a_wrong_tool(self):
        """回退不等于选错工具：置信度不足是门槛问题，不该污染错误工具率。"""
        metrics = decision_rollout_metrics([
            {
                "decision_routing_mode": "tool_loop",
                "decision_tool": "search_packages",
                "decision_fallback_reason": "low_confidence: 0.4",
            },
        ])
        assert metrics["wrong_tool_rate"] == 0.0

    def test_write_block_rate_is_one_when_writes_stay_in_the_legacy_flow(self):
        metrics = decision_rollout_metrics([
            {
                "decision_routing_mode": "tool_loop",
                "decision_mode": "confirm",
                "decision_tool": "create_booking",
                "decision_applied": False,
                "decision_not_applied_reason": "legacy_flow_active:booking_flow",
            },
            {
                "decision_routing_mode": "tool_loop",
                "decision_mode": "tool_call",
                "decision_tool": "follow_photographer",
                "decision_applied": False,
                "decision_not_applied_reason": "proposal_only_tool:follow_photographer",
            },
        ])
        assert metrics["write_proposals"] == 2
        assert metrics["write_block_rate"] == 1.0

    def test_write_block_rate_drops_when_a_write_slips_through(self):
        metrics = decision_rollout_metrics([
            {
                "decision_routing_mode": "tool_loop",
                "decision_mode": "confirm",
                "decision_tool": "create_booking",
                "decision_applied": True,
            },
            {
                "decision_routing_mode": "tool_loop",
                "decision_mode": "confirm",
                "decision_tool": "create_booking",
                "decision_applied": False,
                "decision_not_applied_reason": "proposal_only_tool:create_booking",
            },
        ])
        assert metrics["write_block_rate"] == 0.5

    def test_repeat_recommendation_rate_uses_recommendation_turns(self):
        metrics = decision_rollout_metrics([
            {"recommended_count": 2, "repeat_recommendation": False},
            {
                "recommended_count": 1,
                "recommendation_refinement": True,
                "repeat_recommendation": True,
                "repeat_recommendation_count": 1,
            },
            {"decision_routing_mode": "tool_loop"},
        ])
        assert metrics["recommendation_turns"] == 2
        assert metrics["repeat_recommendation_rate"] == 0.5
        assert metrics["repeat_after_refinement_rate"] == 1.0

    def test_empty_window_reports_zeros_instead_of_dividing_by_zero(self):
        metrics = decision_rollout_metrics([])
        assert metrics["tool_calls"] == 0
        assert metrics["tool_success_rate"] == 0.0
        assert metrics["write_block_rate"] == 0.0

    def test_coverage_rate_splits_the_two_sides(self, monkeypatch):
        _rollout(monkeypatch, AGENT_ROUTING_MODE="tool_loop", AGENT_ROUTING_ROLLOUT_PERCENT=50)
        coverage = rollout_coverage([
            {"routing_mode": "tool_loop", "routing_in_rollout": True, "routing_reason": "bucket_in"},
            {"routing_mode": "legacy", "routing_in_rollout": False, "routing_reason": "bucket_out"},
            {"routing_mode": "legacy", "routing_in_rollout": False, "routing_reason": "bucket_out"},
        ])
        assert coverage["total"] == 3
        assert coverage["coverage_rate"] == 0.3333
        assert coverage["modes"] == {"legacy": 2, "tool_loop": 1}
        assert coverage["reasons"]["bucket_out"] == 2
        assert coverage["target_mode"] == "tool_loop"
        assert coverage["percent"] == 50


@pytest.mark.asyncio
async def test_repeat_recommendation_is_measured_across_turns(
    db, customer_user, wedding_packages, monkeypatch
):
    """“换一个”这轮如果又推了同一个资源，重复推荐率必须能看出来。"""
    decision_provider = DecisionProvider(_search_decision())
    final_provider = RecordingProvider()
    _use_providers(monkeypatch, decision_provider, final_provider)
    _rollout(monkeypatch, AGENT_ROUTING_MODE="tool_loop")
    conversation = ai_service.create_conversation(db, customer_user.id)

    _, first = await ai_service.send_ai_message(
        db, customer_user.id, conversation.id, "推荐重庆婚礼拍摄方案"
    )
    first_overlap = first.message_metadata["recommendation_overlap"]
    assert first_overlap["recommended_count"] >= 1
    assert first_overlap["repeat_count"] == 0
    assert first_overlap["refinement"] is False

    _, second = await ai_service.send_ai_message(
        db, customer_user.id, conversation.id, "这个不太满意，换一个"
    )
    second_overlap = second.message_metadata["recommendation_overlap"]
    # 排除逻辑生效时第二轮不会重复推荐上一轮的资源。
    assert second_overlap["repeat_count"] == 0
    assert set(second_overlap["repeated_resource_ids"]) == set()

    dashboard = agent_quality_dashboard(db)
    assert dashboard["rollout_metrics"]["repeat_recommendation_rate"] == 0.0
    assert dashboard["rollout_metrics"]["recommendation_turns"] >= 1


@pytest.mark.asyncio
async def test_overlap_is_flagged_when_the_same_resource_comes_back(
    db, customer_user, wedding_packages, monkeypatch
):
    """直接构造重叠场景，确认指标不是恒为 0。"""
    previous = {"seen_resource_ids": ["pkg-cq-wedding-day"]}
    current = {"recommended_resource_ids": ["pkg-cq-wedding-day", "pkg-cq-wedding-half"]}
    overlap = ai_service._recommendation_overlap(
        previous=previous,
        current=current,
        refinement=True,
    )
    assert overlap["repeat_count"] == 1
    assert overlap["repeat_ratio"] == 0.5
    assert overlap["repeated_resource_ids"] == ["pkg-cq-wedding-day"]

    metrics = decision_rollout_metrics([
        {
            "recommended_count": overlap["recommended_count"],
            "recommendation_refinement": overlap["refinement"],
            "repeat_recommendation": bool(overlap["repeat_count"]),
        }
    ])
    assert metrics["repeat_recommendation_rate"] == 1.0
    assert metrics["repeat_after_refinement_rate"] == 1.0


@pytest.mark.asyncio
async def test_dashboard_reports_no_result_rate_for_empty_searches(
    db, customer_user, wedding_packages, monkeypatch
):
    decision_provider = DecisionProvider(
        _search_decision(arguments={"city": "拉萨", "styles": ["婚礼"], "limit": 3})
    )
    final_provider = RecordingProvider()
    _use_providers(monkeypatch, decision_provider, final_provider)
    _rollout(monkeypatch, AGENT_ROUTING_MODE="tool_loop")
    conversation = ai_service.create_conversation(db, customer_user.id)

    _, message = await ai_service.send_ai_message(
        db, customer_user.id, conversation.id, "拉萨有婚礼套餐吗"
    )
    assert message.message_metadata["tool_call"]["status"] == "empty"

    metrics = agent_quality_dashboard(db)["rollout_metrics"]
    assert metrics["tool_calls"] == 1
    assert metrics["no_result_rate"] == 1.0
    assert metrics["tool_success_rate"] == 0.0


# ── C4 分类器去重（默认关闭）────────────────────────────────────────────────


def _count_classifier_calls(monkeypatch):
    """包一层计数器，用来验证一条消息到底做了几次"理解"。"""
    calls: list[str | None] = []
    original = ai_service.classify_intent

    async def counting_classify(content, attachments=None, **kwargs):
        calls.append(content)
        return await original(content, attachments, **kwargs)

    monkeypatch.setattr(ai_service, "classify_intent", counting_classify)
    return calls


@pytest.mark.asyncio
async def test_classifier_is_skipped_when_the_decision_layer_takes_over(
    db, customer_user, wedding_packages, monkeypatch
):
    """C4：开关打开且决策层接管时，同一条消息只理解一次。"""
    decision_provider = DecisionProvider(_search_decision())
    final_provider = RecordingProvider()
    _use_providers(monkeypatch, decision_provider, final_provider)
    _rollout(
        monkeypatch,
        AGENT_ROUTING_MODE="tool_loop",
        AI_DECISION_SKIPS_INTENT_CLASSIFIER=True,
    )
    calls = _count_classifier_calls(monkeypatch)
    conversation = ai_service.create_conversation(db, customer_user.id)

    _, message = await ai_service.send_ai_message(
        db, customer_user.id, conversation.id, "推荐重庆婚礼拍摄方案"
    )
    metadata = message.message_metadata

    assert calls == []
    assert "intent_classification" not in metadata
    assert metadata["agent_routing"]["classifier_deferred"] is True
    assert metadata["agent_routing"]["classifier_skipped"] is True
    # 省掉分类不等于放弃质量：工具照样拿到真实候选。
    assert metadata["tool_call"]["status"] == "success"
    assert metadata["references"]["packages"]


@pytest.mark.asyncio
async def test_classifier_is_restored_when_the_decision_layer_falls_back(
    db, customer_user, wedding_packages, monkeypatch
):
    """决策层没接管就必须把那次分类补回来，既有路由质量不能下降。"""
    decision_provider = DecisionProvider("not json at all")
    final_provider = RecordingProvider()
    _use_providers(monkeypatch, decision_provider, final_provider)
    _rollout(
        monkeypatch,
        AGENT_ROUTING_MODE="tool_loop",
        AI_DECISION_SKIPS_INTENT_CLASSIFIER=True,
    )
    calls = _count_classifier_calls(monkeypatch)
    conversation = ai_service.create_conversation(db, customer_user.id)

    _, message = await ai_service.send_ai_message(
        db, customer_user.id, conversation.id, "推荐重庆婚礼拍摄方案"
    )
    metadata = message.message_metadata

    assert len(calls) == 1
    assert "intent_classification" in metadata
    assert metadata["agent_routing"]["classifier_skipped"] is False
    assert metadata["agent_decision"]["fallback_reason"] == "invalid_json"
    assert metadata["intent"]["intent"] == "resource_search"


@pytest.mark.asyncio
async def test_classifier_still_runs_when_the_switch_is_off(
    db, customer_user, wedding_packages, monkeypatch
):
    """默认关闭：阶段B 的行为不变，分类器照旧先跑。"""
    decision_provider = DecisionProvider(_search_decision())
    final_provider = RecordingProvider()
    _use_providers(monkeypatch, decision_provider, final_provider)
    _rollout(monkeypatch, AGENT_ROUTING_MODE="tool_loop")
    monkeypatch.setattr(ai_service.settings, "AI_DECISION_SKIPS_INTENT_CLASSIFIER", False)
    calls = _count_classifier_calls(monkeypatch)
    conversation = ai_service.create_conversation(db, customer_user.id)

    _, message = await ai_service.send_ai_message(
        db, customer_user.id, conversation.id, "推荐重庆婚礼拍摄方案"
    )

    assert len(calls) == 1
    assert message.message_metadata["agent_routing"]["classifier_deferred"] is False
    assert "intent_classification" in message.message_metadata


@pytest.mark.asyncio
async def test_skip_switch_is_ignored_in_shadow_mode(
    db, customer_user, wedding_packages, monkeypatch
):
    """shadow 只观察不接管，必须保留分类器，否则影子对比失去基线。"""
    decision_provider = DecisionProvider(_search_decision())
    final_provider = RecordingProvider()
    _use_providers(monkeypatch, decision_provider, final_provider)
    _rollout(
        monkeypatch,
        AGENT_ROUTING_MODE="shadow",
        AI_DECISION_SKIPS_INTENT_CLASSIFIER=True,
    )
    calls = _count_classifier_calls(monkeypatch)
    conversation = ai_service.create_conversation(db, customer_user.id)

    _, message = await ai_service.send_ai_message(
        db, customer_user.id, conversation.id, "推荐重庆婚礼拍摄方案"
    )

    assert len(calls) == 1
    assert message.message_metadata["agent_routing"]["classifier_deferred"] is False
    assert message.message_metadata["agent_decision"]["applied"] is False


# ── C5 离线评估 ────────────────────────────────────────────────────────────


class TestRulesToolSelection:
    def test_golden_dataset_passes(self):
        """规则识别退为兜底后仍要选得出正确工具（§4-C.5）。"""
        report = evaluate_rules_tool_selection(load_golden_cases(TOOL_SELECTION_DATASET))
        assert report["total"] >= 10
        assert report["accuracy"] == 1.0

    def test_chat_cases_expect_no_tool(self):
        report = evaluate_rules_tool_selection([
            {"id": "knowledge", "input": "逆光人像怎么补光", "expected": {"tool": None}},
        ])
        assert report["results"][0]["actual_tool"] is None
        assert report["passed"] == 1

    def test_mismatch_is_reported_not_swallowed(self):
        report = evaluate_rules_tool_selection([
            {"id": "wrong", "input": "推荐重庆婚礼套餐", "expected": {"tool": "search_projects"}},
        ])
        assert report["accuracy"] == 0.0
        assert report["results"][0]["actual_tool"] == "search_packages"


@pytest.mark.asyncio
async def test_offline_replay_reports_metrics_and_rules_agreement(
    db, customer_user, wedding_packages, monkeypatch
):
    """回放灰度日志：不调用 LLM，也能算出指标与"规则 vs 决策"一致率。"""
    decision_provider = DecisionProvider(_search_decision())
    final_provider = RecordingProvider()
    _use_providers(monkeypatch, decision_provider, final_provider)
    _rollout(monkeypatch, AGENT_ROUTING_MODE="tool_loop")
    conversation = ai_service.create_conversation(db, customer_user.id)

    await ai_service.send_ai_message(
        db, customer_user.id, conversation.id, "推荐重庆婚礼拍摄方案"
    )

    report = replay_agent_traces(db, days=7)
    assert report["traces"] == 1
    assert report["rollout"]["modes"] == {"tool_loop": 1}
    assert report["rollout"]["coverage_rate"] == 1.0
    assert report["metrics"]["tool_success_rate"] == 1.0
    assert report["metrics"]["write_block_rate"] == 0.0  # 本轮没有写提案
    agreement = report["rules_vs_decision"]
    assert agreement["compared"] == 1
    # 规则也会把这句话判成套餐检索，所以两侧应当一致。
    assert agreement["tool_agreement_rate"] == 1.0
    assert agreement["disagreements"] == []


@pytest.mark.asyncio
async def test_offline_replay_hides_user_text_by_default(
    db, customer_user, wedding_packages, monkeypatch
):
    """分歧样本默认不带原文，需要人工复核时才显式打开（§5.5）。"""
    decision_provider = DecisionProvider(
        _search_decision(tool="search_portfolio_items", arguments={"city": "重庆", "limit": 1})
    )
    final_provider = RecordingProvider()
    _use_providers(monkeypatch, decision_provider, final_provider)
    _rollout(monkeypatch, AGENT_ROUTING_MODE="tool_loop")
    conversation = ai_service.create_conversation(db, customer_user.id)

    await ai_service.send_ai_message(
        db, customer_user.id, conversation.id, "推荐重庆婚礼套餐"
    )

    quiet = replay_agent_traces(db, days=7)
    assert quiet["rules_vs_decision"]["tool_agreement_rate"] == 0.0
    sample = quiet["rules_vs_decision"]["disagreements"][0]
    assert sample["rules_tool"] == "search_packages"
    assert sample["decision_tool"] == "search_portfolio_items"
    assert "content" not in sample

    verbose = replay_agent_traces(db, days=7, include_text=True)
    assert verbose["rules_vs_decision"]["disagreements"][0]["content"] == "推荐重庆婚礼套餐"


@pytest.mark.asyncio
async def test_offline_replay_skips_turns_without_a_model_decision(
    db, customer_user, wedding_packages, monkeypatch
):
    """legacy 流量没有决策原文，只进指标不进一致率分母。"""
    final_provider = RecordingProvider()
    _use_providers(monkeypatch, DecisionProvider(_search_decision()), final_provider)
    _rollout(monkeypatch)
    conversation = ai_service.create_conversation(db, customer_user.id)

    await ai_service.send_ai_message(db, customer_user.id, conversation.id, "推荐重庆婚礼方案")

    report = replay_agent_traces(db, days=7)
    assert report["traces"] == 1
    assert report["rules_vs_decision"]["compared"] == 0
    assert report["rules_vs_decision"]["tool_agreement_rate"] == 0.0
    assert report["rollout"]["modes"] == {"legacy": 1}


def test_offline_replay_on_an_empty_database(db):
    report = replay_agent_traces(db, days=7)
    assert report["traces"] == 0
    assert report["metrics"]["tool_calls"] == 0
    assert report["rollout"]["total"] == 0
    assert report["rules_vs_decision"]["compared"] == 0
