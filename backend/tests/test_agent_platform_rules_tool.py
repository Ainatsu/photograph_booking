"""search_platform_rules 工具与 rule_query 意图的契约与路由回归测试。

覆盖：入参契约、工具注册与鉴权、决策层 read_tool 计划、决策/意图 prompt 的
规则查询引导与版本号、LLMIntentCandidate 与 INTENT_POLICIES 的 rule_query 条目、
规则式意图识别器的命中与误报防护、ai_service 的规则接地 prompt 常量。
"""

import pytest
from pydantic import ValidationError

from backend.app.services.ai_agent_contracts import (
    INTENT_POLICIES,
    LLMIntentCandidate,
    apply_intent_policy,
)
from backend.app.services.ai_agent_decision_contracts import (
    AgentDecision,
    SearchPlatformRulesInput,
)
from backend.app.services.ai_agent_decision_prompt import (
    DECISION_PROMPT_VERSION,
    build_decision_system_prompt,
)
from backend.app.services.ai_agent_decision_service import (
    DECISION_ELIGIBLE_INTENTS,
    AgentDecisionOutcome,
    resolve_decision_plan,
)
from backend.app.services.ai_intent_prompt import (
    INTENT_PROMPT_VERSION,
    INTENT_CLASSIFICATION_SYSTEM_PROMPT,
)
from backend.app.services.ai_orchestrator_service import recognize_intent_by_rules
from backend.app.services.ai_prompts import (
    PLATFORM_RULES_GROUNDING_PROMPT,
    PLATFORM_RULES_NO_HITS_PROMPT,
)
from backend.app.services.ai_tool_policy_service import (
    TOOL_REGISTRY,
    authorize_tool_call,
    build_tool_catalog,
    resolve_tool_name,
)


def _rules_decision_outcome(**overrides) -> AgentDecisionOutcome:
    payload = {
        "mode": "tool_call",
        "tool": "search_platform_rules",
        "arguments": {"query": "取消订单 退款 政策", "limit": 5},
        "confidence": 0.95,
        "reason": "平台规则问题",
    }
    payload.update(overrides)
    return AgentDecisionOutcome(
        decision=AgentDecision.model_validate(payload),
        parser="model",
    )


# ── 入参契约 ────────────────────────────────────────────────────────────────


class TestSearchPlatformRulesInputContract:
    def test_valid_input_normalizes_query(self):
        parsed = SearchPlatformRulesInput.model_validate(
            {"query": "  取消订单\n  退款政策  ", "limit": 3}
        )
        assert parsed.query == "取消订单 退款政策"
        assert parsed.limit == 3

    def test_query_is_required_and_bounded(self):
        with pytest.raises(ValidationError):
            SearchPlatformRulesInput.model_validate({"limit": 5})
        with pytest.raises(ValidationError):
            SearchPlatformRulesInput.model_validate({"query": "退"})
        with pytest.raises(ValidationError):
            SearchPlatformRulesInput.model_validate({"query": "退" * 301})

    def test_limit_bounds_and_default(self):
        assert SearchPlatformRulesInput.model_validate({"query": "退款"}).limit == 5
        with pytest.raises(ValidationError):
            SearchPlatformRulesInput.model_validate({"query": "退款", "limit": 0})
        with pytest.raises(ValidationError):
            SearchPlatformRulesInput.model_validate({"query": "退款", "limit": 11})

    def test_extra_fields_rejected(self):
        with pytest.raises(ValidationError):
            SearchPlatformRulesInput.model_validate(
                {"query": "退款", "photographer_id": 7}
            )


# ── 工具注册与鉴权 ──────────────────────────────────────────────────────────


class TestToolRegistration:
    def test_spec_is_read_only_without_confirmation(self):
        spec = TOOL_REGISTRY["search_platform_rules"]
        assert spec.risk_level.value == "read_only"
        assert spec.required_confirmations == 0
        assert spec.llm_selectable is True
        assert spec.proposal_only is False
        assert spec.description

    def test_authorize_allows_direct_execution(self):
        authorization = authorize_tool_call(
            "search_platform_rules",
            arguments={"query": "退款政策", "limit": 3},
            user_role="customer",
        )
        assert authorization.allowed is True
        assert authorization.requires_confirmation is False
        assert authorization.normalized_input["query"] == "退款政策"

    def test_aliases_resolve(self):
        assert resolve_tool_name("search_rules") == "search_platform_rules"
        assert resolve_tool_name("query_rules") == "search_platform_rules"

    def test_catalog_visible_only_for_decision_layer(self):
        catalog = build_tool_catalog(user_role="customer", include_read_tools=True)
        assert "search_platform_rules" in {item["name"] for item in catalog}
        legacy_catalog = build_tool_catalog(user_role="customer", include_read_tools=False)
        assert "search_platform_rules" not in {item["name"] for item in legacy_catalog}

    def test_catalog_hidden_when_disabled(self, monkeypatch):
        monkeypatch.setattr("backend.app.core.config.settings.AI_PLATFORM_RULES_ENABLED", False)
        catalog = build_tool_catalog(user_role="customer", include_read_tools=True)
        assert "search_platform_rules" not in {item["name"] for item in catalog}


# ── 决策层计划 ──────────────────────────────────────────────────────────────


class TestDecisionPlan:
    def test_rule_query_intent_yields_read_tool_plan(self):
        plan = resolve_decision_plan(
            _rules_decision_outcome(),
            legacy_intent_name="rule_query",
            user_role="customer",
        )
        assert plan.action == "read_tool"
        assert plan.applied is True
        assert plan.tool == "search_platform_rules"
        assert plan.arguments["query"] == "取消订单 退款 政策"

    def test_chat_intent_also_routes_to_read_tool(self):
        plan = resolve_decision_plan(
            _rules_decision_outcome(),
            legacy_intent_name="chat",
            user_role="customer",
        )
        assert plan.action == "read_tool"

    def test_invalid_arguments_block_execution(self):
        plan = resolve_decision_plan(
            _rules_decision_outcome(arguments={"query": "退款", "city": "重庆"}),
            legacy_intent_name="rule_query",
            user_role="customer",
        )
        assert plan.action == "legacy"
        assert plan.not_applied_reason.startswith("invalid_arguments:")

    def test_rule_query_is_decision_eligible_and_mapped(self):
        assert "rule_query" in DECISION_ELIGIBLE_INTENTS


# ── Prompt 引导与版本号 ─────────────────────────────────────────────────────


class TestPromptGuidance:
    def test_decision_prompt_version_bumped(self):
        assert DECISION_PROMPT_VERSION == "agent_decision_v4"

    def test_decision_prompt_guides_rule_questions_to_tool(self):
        prompt = build_decision_system_prompt([{"name": "search_platform_rules"}])
        assert "search_platform_rules" in prompt
        assert "退款" in prompt
        assert "不要凭记忆" in prompt

    def test_intent_prompt_version_bumped(self):
        assert INTENT_PROMPT_VERSION == "intent_classifier_v6"

    def test_intent_prompt_defines_rule_query(self):
        assert '"rule_query"' in INTENT_CLASSIFICATION_SYSTEM_PROMPT

    def test_grounding_prompts_require_rule_ids_and_forbid_invention(self):
        assert "规则编号" in PLATFORM_RULES_GROUNDING_PROMPT
        assert "不得凭记忆" in PLATFORM_RULES_GROUNDING_PROMPT
        assert "没有命中" in PLATFORM_RULES_NO_HITS_PROMPT
        assert "不要凭记忆" in PLATFORM_RULES_NO_HITS_PROMPT


# ── 意图合约与规则识别器 ────────────────────────────────────────────────────


class TestRuleQueryIntent:
    def test_candidate_schema_accepts_rule_query(self):
        candidate = LLMIntentCandidate(intent="rule_query", confidence=0.9)
        assert candidate.intent == "rule_query"

    def test_intent_policy_entry(self):
        policy = INTENT_POLICIES["rule_query"]
        assert policy["route"] == "rule_query"
        assert policy["requires_confirmation"] is False
        applied = apply_intent_policy("rule_query")
        assert applied["route"] == "rule_query"
        assert applied["missing_slots"] == []

    @pytest.mark.parametrize(
        "text",
        [
            "取消订单的话退款是怎么算的",
            "定金比例是多少",
            "验收期是多久",
            "入驻审核要多久",
            "作品最多能传几张图",
            "AI 生图每天限额多少",
            "退款政策是什么",
        ],
    )
    def test_rule_questions_recognized(self, text):
        intent = recognize_intent_by_rules(text)
        assert intent.intent == "rule_query", text
        assert intent.route == "rule_query"

    @pytest.mark.parametrize(
        "text",
        [
            "帮我取消订单",
            "我要预约拍摄",
            "帮我找重庆的婚礼套餐",
            "大理最近有没有什么旅游相关的政策",
            "婚礼跟拍要注意什么",
            "帮我发布一个套餐",
        ],
    )
    def test_non_rule_queries_not_hijacked(self, text):
        intent = recognize_intent_by_rules(text)
        assert intent.intent != "rule_query", text
