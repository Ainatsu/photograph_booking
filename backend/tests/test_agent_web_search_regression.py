"""针对 2026-09-08 agenttest8 联网搜索失败的回归测试。

两条线上失败记录的根因：
1. trace #342：序数正则把“查一查”的“一”当成“第一个”，resource_reference 命中后
   整个决策层（含 search_web 确定性触发）被跳过。
2. trace #341：决策模型把时效性外部问题路由成 chat。

覆盖：ORDINAL_PATTERNS 不再误匹配普通用语、显式联网搜索谓词、决策 prompt 的
search_web 引导。
"""

import pytest

from backend.app.services.agent_working_memory_service import resolve_resource_reference
from backend.app.services.ai_agent_decision_prompt import (
    DECISION_PROMPT_VERSION,
    build_decision_system_prompt,
)
from backend.app.services.ai_agent_decision_service import (
    infer_explicit_web_search_decision,
    is_explicit_web_search_request,
)


@pytest.fixture
def active_memory() -> dict:
    memory = {
        "status": "active",
        "task_type": "portfolio_item_search",
        "resources": [
            {"index": 1, "resource_type": "portfolio_items", "resource_id": "r1", "snapshot": {}},
            {"index": 2, "resource_type": "portfolio_items", "resource_id": "r2", "snapshot": {}},
            {"index": 3, "resource_type": "portfolio_items", "resource_id": "r3", "snapshot": {}},
        ],
        "selected_resource": {"index": 1, "resource_type": "portfolio_items", "resource_id": "r1", "snapshot": {}},
    }
    return memory


class TestOrdinalReferenceResolution:
    def test_ordinary_reduplication_is_not_ordinal(self, active_memory):
        # trace #342 的原始消息：其中的“一”属于“查一查”，不是“第一个”。
        assert resolve_resource_reference(active_memory, "帮我查一查富士xt6的最新消息。") is None

    @pytest.mark.parametrize("text", ["唯一的问题是价格", "稍等一下", "再聊一聊", "一查便知"])
    def test_common_one_phrases_are_not_ordinals(self, active_memory, text):
        assert resolve_resource_reference(active_memory, text) is None

    @pytest.mark.parametrize(
        ("text", "expected_index"),
        [
            ("第一个的详情", 1),
            ("看看第 2 个作品", 2),
            ("第三个怎么样", 3),
            ("第1个的价格", 1),
        ],
    )
    def test_explicit_ordinals_still_resolve(self, active_memory, text, expected_index):
        reference = resolve_resource_reference(active_memory, text)
        assert reference is not None
        assert reference["index"] == expected_index


class TestExplicitWebSearchPredicate:
    def test_button_template_message_is_detected(self):
        message = (
            "请联网搜索并仅根据最新公开网页资料回答：帮我查一查富士xt6的最新消息。\n"
            "请附上来源，并明确区分网页事实与推断。"
        )
        assert is_explicit_web_search_request(message) is True
        decision = infer_explicit_web_search_decision(message)
        assert decision is not None
        assert decision.tool == "search_web"
        assert "富士xt6" in decision.arguments["query"]

    @pytest.mark.parametrize("text", ["大理最近有没有什么旅游相关的政策。", "帮我找重庆的婚礼套餐"])
    def test_plain_requests_are_not_explicit_web_search(self, text):
        assert is_explicit_web_search_request(text) is False
        assert infer_explicit_web_search_decision(text) is None

    def test_explicit_web_search_beats_resource_reference(self, active_memory):
        # 显式联网搜索请求不该被 active 任务里的序数引用劫持。
        message = "请联网搜索并仅根据最新公开网页资料回答：第一个套餐的最新评价"
        assert is_explicit_web_search_request(message) is True


class TestDecisionPromptWebSearchGuidance:
    def test_prompt_version_bumped(self):
        assert DECISION_PROMPT_VERSION == "agent_decision_v3"

    def test_prompt_guides_time_sensitive_questions_to_search_web(self):
        prompt = build_decision_system_prompt([{"name": "search_web"}])
        assert "search_web" in prompt
        assert "实时" in prompt
        assert "政策" in prompt

    def test_prompt_keeps_weather_tool_rule(self):
        prompt = build_decision_system_prompt([{"name": "get_shoot_context"}])
        assert "get_shoot_context" in prompt
