"""阶段B（统一工具调用 + 决策层）测试。

覆盖 codex-agent-llm-tool-routing-refactor-guide.md 的：
- §7.1 单元：工具入参契约、决策协议校验、参数清理；
- §7.2 决策：四种模式、置信度门槛、非法输出回退；
- §7.3 工具执行：search_* 真实检索、排除、角色限制；
- §7.5 安全：伪造 ID / 越权工具 / 未确认写操作 / 非法参数；
- §7.4 + §6.1~§6.5 会话回归：tool_loop 端到端与 shadow 影子对比。
"""

import json

import pytest
from pydantic import ValidationError

from backend.app.models.ai_production import AgentTrace
from backend.app.models.order import Order
from backend.app.models.photographer import PhotographerProfile
from backend.app.models.project import ProjectStatus, ShootProject
from backend.app.services import ai_service
from backend.app.services import ai_agent_decision_service as decision_service
from backend.app.services import ai_search_tool_service as search_tool_service
from backend.app.services.ai_agent_contracts import AgentIntent
from backend.app.services.ai_agent_decision_contracts import (
    DECISION_SCHEMA_VERSION,
    AgentDecision,
    SearchPackagesInput,
    SearchProjectsInput,
    clean_condition_text,
    decision_condition_slots,
    sanitize_arguments,
    single_question,
)
from backend.app.services.ai_agent_decision_service import (
    compare_decision_with_intent,
    decide_agent_action,
    infer_explicit_search_decision,
    resolve_decision_plan,
)
from backend.app.services.ai_resource_index_service import rebuild_ai_resource_documents
from backend.app.services.ai_search_tool_service import (
    build_tool_result_prompt,
    is_search_tool,
    run_search_tool,
    search_tool_for_resource_types,
)
from backend.app.services.ai_tool_policy_service import (
    authorize_tool_call,
    build_tool_catalog,
    resolve_tool_name,
)
from backend.app.services.ai_trace_service import agent_quality_dashboard


# ── Fake providers ──────────────────────────────────────────────────────────


def test_explicit_dali_plan_uses_package_tool_without_history():
    decision = infer_explicit_search_decision("推荐在大理的方案")
    assert decision is not None
    assert decision.tool == "search_packages"
    assert decision.arguments["city"] == "大理"


@pytest.mark.asyncio
async def test_model_project_tool_is_corrected_for_explicit_dali_plan():
    provider = DecisionProvider(
        _search_decision(tool="search_projects", arguments={"city": "大理", "limit": 3})
    )
    outcome = await decide_agent_action(
        content="推荐在大理的方案",
        user_role="customer",
        history=[{"role": "assistant", "content": "刚才在推荐企划"}],
        search_context={"slots": {"resource_types": ["projects"], "city": "重庆"}},
        provider=provider,
    )
    assert outcome.parser == "model"
    assert outcome.decision is not None
    assert outcome.decision.tool == "search_packages"
    assert outcome.decision.arguments["city"] == "大理"


class RecordingProvider:
    """记录最终 LLM 收到的消息，并返回固定文本。"""

    def __init__(self, content: str = "好的，我按平台真实候选来回答。"):
        self.content = content
        self.messages_history: list[list[dict]] = []

    async def chat(self, messages, *, temperature=None, response_format=None):
        self.messages_history.append(messages)
        return {
            "content": self.content,
            "metadata": {"model": {"provider": "test", "model": "test-model"}},
        }

    @property
    def system_prompts(self) -> list[str]:
        return [
            message["content"]
            for messages in self.messages_history
            for message in messages
            if message["role"] == "system"
        ]


class DecisionProvider:
    """按顺序返回预设决策 JSON；用完后重复最后一个。"""

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


class BrokenDecisionProvider:
    async def chat(self, messages, *, temperature=None, response_format=None):
        raise RuntimeError("provider down")


def _use_tool_loop(monkeypatch, decision_provider, final_provider, mode: str = "tool_loop"):
    monkeypatch.setattr(ai_service.settings, "AGENT_ROUTING_MODE", mode)
    monkeypatch.setattr(ai_service.settings, "AI_INTENT_CLASSIFIER_MODE", "rules")
    monkeypatch.setattr(decision_service, "get_text_provider", lambda: decision_provider)
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: final_provider)


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def wedding_packages(db, photographer_user):
    """重庆摄影师，套餐用“婚礼跟拍/婚宴”这类变体写法标注。"""
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


@pytest.fixture
def open_project(db, customer_user):
    """一条已发布的重庆婚礼企划，用于 search_projects。"""
    project = ShootProject(
        customer_id=customer_user.id,
        title="重庆婚礼当天跟拍征集",
        description="需要一位擅长婚礼纪实的摄影师，全天跟拍。",
        category="婚礼",
        style_tags=["婚礼"],
        city="重庆",
        budget_min=2000,
        budget_max=4000,
        visibility="public",
        status=ProjectStatus.OPEN,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


# ── §7.1 工具入参契约 ───────────────────────────────────────────────────────


class TestSearchInputContract:
    def test_styles_are_normalized_and_deduped(self):
        """婚庆/婚宴/婚礼跟拍 是同一个题材，进检索层前必须收敛成“婚礼”。"""
        payload = SearchPackagesInput.model_validate(
            {"city": "重庆", "styles": ["婚庆", "婚宴", "婚礼跟拍"]}
        )
        assert payload.styles == ["婚礼"]
        assert payload.city == "重庆"

    def test_limit_defaults_to_three(self):
        assert SearchPackagesInput.model_validate({}).limit == 3

    @pytest.mark.parametrize("limit", [0, -1, 11, 100])
    def test_limit_out_of_range_is_rejected(self, limit):
        with pytest.raises(ValidationError):
            SearchPackagesInput.model_validate({"limit": limit})

    @pytest.mark.parametrize(
        "field, value",
        [
            ("package_id", "pkg-cq-wedding-day"),
            ("photographer_id", 7),
            ("resource_ids", ["pkg-1"]),
        ],
    )
    def test_model_cannot_invent_platform_id_fields(self, field, value):
        """§5.1：平台实体 ID 只能由后端补全，模型多塞字段一律校验失败。"""
        with pytest.raises(ValidationError):
            SearchPackagesInput.model_validate({field: value})

    def test_projects_input_has_no_photographer_name(self):
        with pytest.raises(ValidationError):
            SearchProjectsInput.model_validate({"photographer_name": "小李"})

    @pytest.mark.parametrize("value", ["这个", "换一个", "上一个", "随便"])
    def test_control_words_are_not_conditions(self, value):
        assert clean_condition_text(value) is None
        assert SearchPackagesInput.model_validate({"city": value}).city is None

    def test_whole_sentence_is_not_a_condition(self):
        assert SearchPackagesInput.model_validate(
            {"city": "帮我找重庆的婚礼摄影师"}
        ).city is None

    def test_real_city_survives(self):
        assert SearchPackagesInput.model_validate({"city": "重庆"}).city == "重庆"

    def test_inverted_budget_range_is_rejected(self):
        with pytest.raises(ValidationError):
            SearchPackagesInput.model_validate({"budget_min": 5000, "budget_max": 2000})

    def test_negative_budget_is_rejected(self):
        with pytest.raises(ValidationError):
            SearchPackagesInput.model_validate({"budget_max": -1})

    def test_query_text_is_flattened_and_truncated(self):
        payload = SearchPackagesInput.model_validate({"query_text": "重庆\n婚礼套餐" + "长" * 200})
        assert "\n" not in payload.query_text
        assert len(payload.query_text) == 120

    def test_backend_owned_exclude_ids_are_dropped(self):
        """排除列表只能由后端从 search_context 生成（§5.1）。"""
        arguments, dropped = sanitize_arguments(
            {"city": "重庆", "exclude_resource_ids": ["pkg-cq-wedding-day"]}
        )
        assert arguments == {"city": "重庆"}
        assert dropped == ["exclude_resource_ids"]

    def test_sanitize_arguments_tolerates_garbage(self):
        assert sanitize_arguments(None) == ({}, [])
        assert sanitize_arguments("not-a-dict") == ({}, [])


# ── §7.2 决策协议 ───────────────────────────────────────────────────────────


class TestDecisionProtocol:
    def test_tool_call_requires_tool(self):
        with pytest.raises(ValidationError):
            AgentDecision.model_validate({"mode": "tool_call", "confidence": 0.9})

    def test_confirm_requires_tool(self):
        with pytest.raises(ValidationError):
            AgentDecision.model_validate({"mode": "confirm", "confidence": 0.9})

    def test_clarify_requires_question(self):
        with pytest.raises(ValidationError):
            AgentDecision.model_validate({"mode": "clarify", "confidence": 0.9})

    def test_clarify_keeps_only_one_question(self):
        """§5.3：一轮最多问一个问题。"""
        decision = AgentDecision.model_validate({
            "mode": "clarify",
            "question": "你在哪个城市拍？预算大概多少？还有日期呢？",
            "confidence": 0.9,
        })
        assert decision.question == "你在哪个城市拍？"
        assert decision.needs_clarification is True

    def test_single_question_truncates_statement_without_question_mark(self):
        assert single_question("请告诉我城市" + "啊" * 300) == ("请告诉我城市" + "啊" * 300)[:120]
        assert single_question("   ") is None
        assert single_question(None) is None

    def test_chat_mode_clears_tool_and_arguments(self):
        """chat 不允许边聊边偷偷调用工具。"""
        decision = AgentDecision.model_validate({
            "mode": "chat",
            "tool": "search_packages",
            "arguments": {"city": "重庆"},
            "question": "还需要什么？",
            "confidence": 0.8,
        })
        assert decision.tool is None
        assert decision.arguments == {}
        assert decision.question is None
        assert decision.needs_clarification is False

    def test_tool_call_clears_clarification_fields(self):
        decision = AgentDecision.model_validate({
            "mode": "tool_call",
            "tool": "search_packages",
            "needs_clarification": True,
            "question": "要不要含妆造？",
            "confidence": 0.95,
        })
        assert decision.needs_clarification is False
        assert decision.question is None

    @pytest.mark.parametrize("confidence", [-0.1, 1.5])
    def test_confidence_must_be_a_probability(self, confidence):
        with pytest.raises(ValidationError):
            AgentDecision.model_validate({"mode": "chat", "confidence": confidence})

    def test_unknown_mode_and_extra_fields_are_rejected(self):
        with pytest.raises(ValidationError):
            AgentDecision.model_validate({"mode": "book_now", "confidence": 0.9})
        with pytest.raises(ValidationError):
            AgentDecision.model_validate(
                {"mode": "chat", "confidence": 0.9, "answer": "直接给你答案"}
            )

    def test_schema_version_is_pinned(self):
        decision = AgentDecision.model_validate({"mode": "chat", "confidence": 0.9})
        assert decision.schema_version == DECISION_SCHEMA_VERSION
        with pytest.raises(ValidationError):
            AgentDecision.model_validate(
                {"schema_version": "agent_decision_v99", "mode": "chat", "confidence": 0.9}
            )

    def test_condition_slots_extracted_for_shadow_diff(self):
        decision = AgentDecision.model_validate({
            "mode": "tool_call",
            "tool": "search_packages",
            "arguments": {"city": "重庆", "styles": ["婚礼"], "budget_max": 3000, "limit": 2},
            "confidence": 0.9,
        })
        assert decision_condition_slots(decision) == {
            "city": "重庆",
            "styles": ["婚礼"],
            "budget_max": 3000,
            "limit": 2,
        }
        assert decision_condition_slots(None) == {}


# ── §7.5 工具鉴权与安全 ─────────────────────────────────────────────────────


class TestToolAuthorization:
    def test_missing_and_unknown_tool(self):
        assert authorize_tool_call(None).error_code == "missing_tool"
        assert authorize_tool_call("drop_database").error_code == (
            "unregistered_tool:drop_database"
        )

    def test_aliases_resolve_to_registered_names(self):
        assert resolve_tool_name("search_package") == "search_packages"
        assert resolve_tool_name("get_photographer_availability") == "get_available_slots"
        assert resolve_tool_name("  search_project ") == "search_projects"
        assert resolve_tool_name("what_is_this") == "what_is_this"
        authorization = authorize_tool_call("search_package", arguments={"city": "重庆"})
        assert authorization.allowed is True
        assert authorization.tool == "search_packages"

    def test_forged_resource_id_is_refused_and_recorded(self):
        """伪造 package_id：不是"清洗掉后照常检索"，而是整次调用不通过。"""
        authorization = authorize_tool_call(
            "search_packages",
            arguments={"city": "重庆", "package_id": "pkg-does-not-exist"},
        )
        assert authorization.allowed is False
        assert authorization.error_code.startswith("invalid_arguments:")
        assert authorization.dropped_fields == ("package_id",)

    def test_customer_cannot_search_projects(self):
        authorization = authorize_tool_call(
            "search_projects", arguments={"city": "重庆"}, user_role="customer"
        )
        assert authorization.allowed is False
        assert authorization.error_code == "role_not_allowed:customer"

    def test_photographer_can_search_projects(self):
        authorization = authorize_tool_call(
            "search_projects", arguments={"city": "重庆"}, user_role="photographer"
        )
        assert authorization.allowed is True
        assert authorization.normalized_input["city"] == "重庆"

    @pytest.mark.parametrize(
        "tool", ["create_booking", "create_project", "publish_package", "follow_photographer"]
    )
    def test_write_tools_are_proposal_only(self, tool):
        """§5.2：写操作决策层只能提出，落库仍走既有确认流程。"""
        authorization = authorize_tool_call(
            tool, arguments={}, user_role="photographer", allow_writes=True
        )
        assert authorization.allowed is False
        assert authorization.error_code == f"proposal_only_tool:{tool}"
        assert authorization.requires_confirmation is True

    def test_write_tools_blocked_before_role_check_when_writes_disabled(self):
        authorization = authorize_tool_call(
            "create_booking", arguments={}, user_role="customer", allow_writes=False
        )
        assert authorization.allowed is False
        assert authorization.error_code == "writes_not_allowed:create_booking"

    @pytest.mark.parametrize("tool", ["get_available_slots", "search_bookable_packages"])
    def test_internal_tools_are_not_llm_selectable(self, tool):
        """带平台 ID 入参的内部工具不给模型选，避免它为凑参数编 ID。"""
        authorization = authorize_tool_call(
            tool, arguments={"photographer_id": 1}, user_role="customer"
        )
        assert authorization.allowed is False
        assert authorization.error_code == f"tool_not_selectable:{tool}"


class TestToolCatalog:
    def test_customer_read_only_catalog(self):
        names = [
            item["name"] for item in build_tool_catalog(user_role="customer", allow_writes=False)
        ]
        assert names == ["search_photographers", "search_portfolio_items", "search_packages"]

    def test_photographer_catalog_includes_projects_and_write_proposals(self):
        catalog = build_tool_catalog(user_role="photographer", allow_writes=True)
        names = {item["name"] for item in catalog}
        assert "search_projects" in names
        assert "publish_package" in names
        assert "get_available_slots" not in names
        writes = [item for item in catalog if item["name"] == "publish_package"]
        assert writes[0]["requires_confirmation"] is True
        assert writes[0]["execution"] == "backend_confirm_flow"

    def test_customer_catalog_hides_photographer_only_tools(self):
        names = {
            item["name"] for item in build_tool_catalog(user_role="customer", allow_writes=True)
        }
        assert "search_projects" not in names
        assert "publish_package" not in names
        assert "create_booking" in names


# ── §7.3 工具执行 ───────────────────────────────────────────────────────────


class TestSearchToolExecution:
    def test_search_tool_registry_helpers(self):
        assert is_search_tool("search_packages") is True
        assert is_search_tool("create_booking") is False
        assert search_tool_for_resource_types(["packages"]) == "search_packages"
        assert search_tool_for_resource_types(["projects"]) == "search_projects"
        # 多资源类型无法映射成单一工具，回退给既有编排
        assert search_tool_for_resource_types(["packages", "photographers"]) is None
        assert search_tool_for_resource_types([]) is None

    def test_search_packages_returns_real_candidates(self, db, wedding_packages):
        tool_call = run_search_tool(
            db,
            tool_name="search_packages",
            arguments={"city": "重庆", "styles": ["婚礼"], "limit": 3},
        )
        assert tool_call["status"] == "success"
        result = tool_call["result"]
        assert result["resource_type"] == "packages"
        assert result["count"] == len(result["items"]) > 0
        assert all(str(item_id).startswith("pkg-cq-wedding") for item_id in result["resource_ids"])
        # payload 是 retrieval 形状，ai_service 直接复用它构建 references / 引用白名单
        assert tool_call["payload"]["references"]["packages"] == result["items"]
        assert tool_call["retrieval"] is tool_call["payload"]

    def test_search_packages_respects_backend_exclusions(self, db, wedding_packages):
        first = run_search_tool(
            db, tool_name="search_packages", arguments={"city": "重庆", "styles": ["婚礼"], "limit": 1}
        )
        excluded = first["result"]["resource_ids"][0]
        second = run_search_tool(
            db,
            tool_name="search_packages",
            arguments={
                "city": "重庆",
                "styles": ["婚礼"],
                "limit": 1,
                "exclude_resource_ids": [excluded],
            },
        )
        remaining = second["result"]["resource_ids"]
        assert remaining and excluded not in remaining
        assert second["result"]["criteria"]["exclude_resource_ids"] == [excluded]

    def test_budget_max_filters_expensive_package(self, db, wedding_packages):
        tool_call = run_search_tool(
            db,
            tool_name="search_packages",
            arguments={"city": "重庆", "styles": ["婚礼"], "budget_max": 2000},
        )
        assert tool_call["result"]["resource_ids"] == ["pkg-cq-wedding-half"]

    def test_query_text_is_synthesized_from_conditions(self, db, wedding_packages):
        """没有 query_text 时用结构化条件拼，绝不把用户的反馈原话当关键词。"""
        tool_call = run_search_tool(
            db, tool_name="search_packages", arguments={"city": "重庆", "styles": ["婚礼"]}
        )
        text = tool_call["result"]["criteria"]["text"]
        assert "重庆" in text and "婚礼" in text and "套餐" in text
        assert "不太满意" not in text

    def test_image_search_tool_forwards_pixels_and_vision_terms(self, db, monkeypatch):
        captured = {}

        def fake_retrieve_references(db_session, content, **kwargs):
            captured["db"] = db_session
            captured["content"] = content
            captured.update(kwargs)
            return {
                "context_schema_version": "test",
                "criteria": {"text": content},
                "references": {
                    "photographers": [],
                    "portfolio_items": [],
                    "packages": [],
                    "projects": [],
                },
                "diagnostics": {},
            }

        monkeypatch.setattr(search_tool_service, "retrieve_references", fake_retrieve_references)
        attachments = [{"type": "image", "url": "/static/ai/reference.jpg"}]
        analysis = {
            "summary": "胶片 暖色 自然光",
            "style": ["胶片", "暖色"],
            "scene": [],
            "mood": [],
            "lighting": ["自然光"],
            "color": [],
            "composition": [],
            "makeup": [],
            "search_terms": ["胶片", "暖色", "自然光"],
        }

        tool_call = run_search_tool(
            db,
            tool_name="search_portfolio_items",
            arguments={"limit": 3},
            vision_analysis=analysis,
            image_attachments=attachments,
        )

        assert captured["image_attachments"] == attachments
        assert captured["vision_analysis"] == analysis
        assert "胶片" in captured["content"]
        assert "暖色" in captured["content"]

    def test_original_request_single_item_overrides_model_limit_after_vision_rewrite(
        self, db, monkeypatch
    ):
        captured = {}

        def fake_retrieve_references(db_session, content, **kwargs):
            captured["content"] = content
            captured.update(kwargs)
            return {
                "context_schema_version": "test",
                "criteria": {"text": content, "limit": kwargs["limit"]},
                "references": {
                    "photographers": [],
                    "portfolio_items": [],
                    "packages": [],
                    "projects": [],
                },
                "diagnostics": {},
            }

        monkeypatch.setattr(search_tool_service, "retrieve_references", fake_retrieve_references)
        tool_call = run_search_tool(
            db,
            tool_name="search_portfolio_items",
            arguments={"query_text": "胶片 暖色", "limit": 5},
            vision_analysis={"search_terms": ["胶片", "暖色"]},
            image_attachments=[{"type": "image", "url": "/static/ai/reference.jpg"}],
            request_content="为我找一份类似风格的作品。",
        )

        assert captured["limit"] == 1
        assert "一份" not in captured["content"]
        assert tool_call["input"]["limit"] == 1
        assert tool_call["result"]["criteria"]["limit"] == 1

    def test_city_without_resources_returns_empty_not_wrong_city(self, db, wedding_packages):
        tool_call = run_search_tool(
            db, tool_name="search_packages", arguments={"city": "拉萨", "styles": ["婚礼"]}
        )
        assert tool_call["status"] == "empty"
        assert tool_call["result"]["count"] == 0
        assert tool_call["result"]["items"] == []


class TestProjectSearchTool:
    def test_customer_cannot_execute_project_search(self, db, customer_user, open_project):
        """执行层也要自己守角色，不能只依赖上游鉴权。"""
        tool_call = run_search_tool(
            db, tool_name="search_projects", arguments={"city": "重庆"}, user=customer_user
        )
        assert tool_call["status"] == "failed"
        assert tool_call["result"]["error"] == "role_not_allowed"
        assert tool_call["payload"] is None
        assert tool_call["result"]["items"] == []

    def test_missing_user_is_refused(self, db, open_project):
        tool_call = run_search_tool(db, tool_name="search_projects", arguments={})
        assert tool_call["status"] == "failed"
        assert tool_call["result"]["error"] == "role_not_allowed"

    def test_photographer_gets_real_projects(
        self, db, photographer_user, wedding_packages, open_project
    ):
        tool_call = run_search_tool(
            db,
            tool_name="search_projects",
            arguments={"city": "重庆", "styles": ["婚礼"], "limit": 3},
            user=photographer_user,
        )
        assert tool_call["status"] == "success"
        result = tool_call["result"]
        assert result["resource_type"] == "projects"
        assert result["resource_ids"] == [open_project.id]
        assert result["items"][0]["title"] == open_project.title
        # 企划不属于文档检索三件套，不能借用摄影师/作品/套餐那套回答约束
        assert tool_call["retrieval"] is None
        assert tool_call["payload"]["references"]["projects"] == result["items"]
        assert tool_call["payload"]["references"]["packages"] == []

    def test_unsupported_tool_name_fails_closed(self, db):
        tool_call = run_search_tool(db, tool_name="search_orders", arguments={})
        assert tool_call["status"] == "failed"
        assert tool_call["result"]["error"] == "unsupported_search_tool"


class TestToolResultPrompt:
    def test_prompt_names_the_resource_type_and_forbids_invention(
        self, db, photographer_user, wedding_packages, open_project
    ):
        tool_call = run_search_tool(
            db, tool_name="search_projects", arguments={"city": "重庆"}, user=photographer_user
        )
        prompt = build_tool_result_prompt(tool_call)
        assert "企划" in prompt
        assert "不要编造" in prompt
        assert "search_projects" in prompt
        # 真实标题进 prompt，内部打分不给用户看
        assert open_project.title in prompt
        assert "不要向用户展示内部打分" in prompt

    def test_prompt_is_none_without_tool_call(self):
        assert build_tool_result_prompt(None) is None


# ── §7.2 决策调用与回退 ─────────────────────────────────────────────────────


def _search_decision(**overrides):
    payload = {
        "schema_version": DECISION_SCHEMA_VERSION,
        "mode": "tool_call",
        "tool": "search_packages",
        "arguments": {"city": "重庆", "styles": ["婚礼"], "limit": 3},
        "confidence": 0.93,
        "reason": "用户在问套餐",
    }
    payload.update(overrides)
    return payload


class TestDecideAgentAction:
    @pytest.mark.asyncio
    async def test_happy_path_parses_model_decision(self):
        outcome = await decide_agent_action(
            content="推荐重庆婚礼套餐",
            user_role="customer",
            provider=DecisionProvider(_search_decision()),
        )
        assert outcome.parser == "model"
        assert outcome.fallback_reason is None
        assert outcome.decision.tool == "search_packages"
        assert outcome.decision.arguments["city"] == "重庆"
        trace = outcome.as_trace()
        assert trace["protocol_version"] == DECISION_SCHEMA_VERSION
        assert trace["prompt_version"]
        assert trace["mode"] == "tool_call"
        assert trace["raw_output"]

    @pytest.mark.asyncio
    async def test_markdown_fenced_json_is_accepted(self):
        raw = "```json\n" + json.dumps(_search_decision(), ensure_ascii=False) + "\n```"
        outcome = await decide_agent_action(
            content="推荐重庆婚礼套餐", user_role="customer", provider=DecisionProvider(raw)
        )
        assert outcome.parser == "model"
        assert outcome.decision.tool == "search_packages"

    @pytest.mark.asyncio
    async def test_tool_alias_is_rewritten_to_registered_name(self):
        outcome = await decide_agent_action(
            content="推荐重庆婚礼套餐",
            user_role="customer",
            provider=DecisionProvider(_search_decision(tool="search_package")),
        )
        assert outcome.parser == "model"
        assert outcome.decision.tool == "search_packages"

    @pytest.mark.asyncio
    async def test_empty_content_never_calls_the_model(self):
        provider = DecisionProvider(_search_decision())
        outcome = await decide_agent_action(content="   ", provider=provider)
        assert outcome.parser == "fallback"
        assert outcome.fallback_reason == "empty_content"
        assert provider.calls == []

    @pytest.mark.asyncio
    async def test_low_confidence_falls_back_but_keeps_the_decision_for_audit(self):
        outcome = await decide_agent_action(
            content="推荐重庆婚礼套餐",
            user_role="customer",
            provider=DecisionProvider(_search_decision(confidence=0.4)),
            min_confidence=0.72,
        )
        assert outcome.parser == "fallback"
        assert outcome.fallback_reason == "low_confidence: 0.4"
        assert outcome.decision is not None

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "raw, reason",
        [
            ("这不是 JSON", "invalid_json"),
            ("[1, 2, 3]", "not_a_dict"),
            ("", "empty_response"),
            ("```\n```", "empty_after_clean"),
        ],
    )
    async def test_malformed_output_falls_back(self, raw, reason):
        outcome = await decide_agent_action(
            content="推荐重庆婚礼套餐", user_role="customer", provider=DecisionProvider(raw)
        )
        assert outcome.parser == "fallback"
        assert outcome.fallback_reason == reason
        assert outcome.decision is None

    @pytest.mark.asyncio
    async def test_illegal_decision_shape_falls_back(self):
        outcome = await decide_agent_action(
            content="推荐重庆婚礼套餐",
            user_role="customer",
            provider=DecisionProvider({"mode": "tool_call", "confidence": 0.99}),
        )
        assert outcome.fallback_reason.startswith("schema_validation_error:")
        assert outcome.decision is None

    @pytest.mark.asyncio
    async def test_provider_failure_falls_back(self):
        outcome = await decide_agent_action(
            content="推荐重庆婚礼套餐", user_role="customer", provider=BrokenDecisionProvider()
        )
        assert outcome.fallback_reason == "provider_error: RuntimeError"
        assert outcome.decision is None

    @pytest.mark.asyncio
    async def test_tool_outside_the_role_catalog_falls_back(self):
        """顾客不该拿到 search_projects：目录里没有就不允许接管。"""
        outcome = await decide_agent_action(
            content="有什么企划可以接",
            user_role="customer",
            provider=DecisionProvider(_search_decision(tool="search_projects")),
        )
        assert outcome.parser == "fallback"
        assert outcome.fallback_reason == "tool_not_available: search_projects"

    @pytest.mark.asyncio
    async def test_model_supplied_exclusions_are_dropped(self):
        outcome = await decide_agent_action(
            content="换一个别的套餐",
            user_role="customer",
            provider=DecisionProvider(
                _search_decision(
                    arguments={"city": "重庆", "exclude_resource_ids": ["pkg-made-up"]}
                )
            ),
        )
        assert outcome.parser == "model"
        assert outcome.dropped_fields == ("exclude_resource_ids",)
        assert "exclude_resource_ids" not in outcome.decision.arguments
        assert outcome.as_trace()["dropped_fields"] == ["exclude_resource_ids"]

    @pytest.mark.asyncio
    async def test_decision_input_carries_no_resource_ids(self, db, customer_user):
        """§5.1/§5.5：模型输入只有条件性状态，不含平台资源 ID。"""
        provider = DecisionProvider(_search_decision())
        await decide_agent_action(
            content="换一个",
            user_role="customer",
            history=[{"role": "assistant", "content": "已经推荐了两个套餐"}],
            page_context={"page": "photographer_detail"},
            search_context={"slots": {"city": "重庆"}, "resource_names": ["婚宴全天跟拍"]},
            provider=provider,
        )
        user_prompt = provider.calls[0][1]["content"]
        assert "pkg-cq-wedding" not in user_prompt
        assert "重庆" in user_prompt


# ── §7.2 决策计划（执行前策略） ─────────────────────────────────────────────


def _model_outcome(**overrides) -> decision_service.AgentDecisionOutcome:
    return decision_service.AgentDecisionOutcome(
        decision=AgentDecision.model_validate(_search_decision(**overrides)),
        parser="model",
    )


class TestResolveDecisionPlan:
    def test_no_decision_stays_on_legacy(self):
        plan = resolve_decision_plan(None, legacy_intent_name="chat")
        assert plan.action == "legacy"
        assert plan.applied is False
        assert plan.not_applied_reason == "no_decision"

    def test_fallback_outcome_carries_its_reason_into_the_plan(self):
        outcome = decision_service.AgentDecisionOutcome(
            decision=None, parser="fallback", fallback_reason="invalid_json"
        )
        plan = resolve_decision_plan(outcome, legacy_intent_name="chat")
        assert plan.action == "legacy"
        assert plan.not_applied_reason == "invalid_json"

    def test_search_plan_is_authorized_and_normalized(self):
        plan = resolve_decision_plan(
            _model_outcome(), legacy_intent_name="resource_search", user_role="customer"
        )
        assert plan.action == "search"
        assert plan.applied is True
        assert plan.tool == "search_packages"
        assert plan.arguments["city"] == "重庆"
        assert plan.arguments["styles"] == ["婚礼"]
        assert plan.authorization.allowed is True

    def test_backend_injects_exclusions_the_model_never_sees(self):
        plan = resolve_decision_plan(
            _model_outcome(),
            legacy_intent_name="resource_search",
            user_role="customer",
            exclude_resource_ids=["pkg-cq-wedding-day", "", None],
        )
        assert plan.arguments["exclude_resource_ids"] == ["pkg-cq-wedding-day"]

    def test_chat_and_clarify_modes(self):
        chat_plan = resolve_decision_plan(
            _model_outcome(mode="chat", tool=None, arguments={}), legacy_intent_name="chat"
        )
        assert (chat_plan.action, chat_plan.applied) == ("chat", True)
        clarify_plan = resolve_decision_plan(
            _model_outcome(
                mode="clarify", tool=None, arguments={}, question="你想在哪个城市拍？"
            ),
            legacy_intent_name="chat",
        )
        assert clarify_plan.action == "clarify"
        assert clarify_plan.question == "你想在哪个城市拍？"

    @pytest.mark.parametrize(
        "legacy_intent", ["booking_flow", "project_flow", "package_publish_flow"]
    )
    def test_running_form_flows_keep_the_legacy_state_machine(self, legacy_intent):
        """§5.2：多轮表单流程进行中，决策层不接管。"""
        plan = resolve_decision_plan(
            _model_outcome(), legacy_intent_name=legacy_intent, user_role="customer"
        )
        assert plan.action == "legacy"
        assert plan.not_applied_reason == f"legacy_flow_active:{legacy_intent}"

    def test_write_tool_proposal_never_executes_here(self):
        plan = resolve_decision_plan(
            _model_outcome(mode="confirm", tool="follow_photographer", arguments={}),
            legacy_intent_name="chat",
            user_role="customer",
            allow_writes=True,
        )
        assert plan.action == "legacy"
        assert plan.applied is False
        assert plan.not_applied_reason == "proposal_only_tool:follow_photographer"

    def test_role_gate_blocks_project_search_for_customers(self):
        plan = resolve_decision_plan(
            _model_outcome(tool="search_projects", arguments={"city": "重庆"}),
            legacy_intent_name="resource_search",
            user_role="customer",
        )
        assert plan.action == "legacy"
        assert plan.not_applied_reason == "role_not_allowed:customer"

    def test_illegal_arguments_block_execution(self):
        plan = resolve_decision_plan(
            _model_outcome(arguments={"city": "重庆", "budget_min": 9000, "budget_max": 100}),
            legacy_intent_name="resource_search",
            user_role="customer",
        )
        assert plan.action == "legacy"
        assert plan.not_applied_reason.startswith("invalid_arguments:")

    def test_non_search_read_tool_is_not_taken_over(self):
        plan = resolve_decision_plan(
            _model_outcome(tool="get_available_slots", arguments={"photographer_id": 1}),
            legacy_intent_name="chat",
            user_role="customer",
        )
        assert plan.action == "legacy"
        assert plan.not_applied_reason == "tool_not_selectable:get_available_slots"


# ── §4.6 影子对比 ───────────────────────────────────────────────────────────


def _legacy_intent(intent: str, **slots) -> AgentIntent:
    return AgentIntent(intent=intent, route=intent, slots=slots, confidence=0.8)


class TestShadowDiff:
    def test_agreement_produces_no_slot_diff(self):
        diff = compare_decision_with_intent(
            _model_outcome(),
            _legacy_intent(
                "resource_search",
                resource_types=["packages"],
                city="重庆",
                style="婚庆",
                limit=3,
            ),
        )
        assert diff["legacy_tool"] == "search_packages"
        assert diff["decision_tool"] == "search_packages"
        assert diff["tool_agreement"] is True
        assert diff["intent_agreement"] is True
        # 老分类器的“婚庆”和决策器的“婚礼”归一后是同一个题材，不算分歧
        assert diff["slot_diff"] == {}

    def test_condition_disagreement_is_recorded_per_field(self):
        diff = compare_decision_with_intent(
            _model_outcome(arguments={"city": "成都", "styles": ["写真"], "limit": 1}),
            _legacy_intent(
                "resource_search", resource_types=["packages"], city="重庆", style="婚礼", limit=3
            ),
        )
        assert diff["tool_agreement"] is True
        assert diff["slot_diff"]["city"] == {"legacy": "重庆", "decision": "成都"}
        assert diff["slot_diff"]["styles"] == {"legacy": ["婚礼"], "decision": ["写真"]}
        assert diff["slot_diff"]["limit"] == {"legacy": 3, "decision": 1}

    def test_route_disagreement_between_chat_and_search(self):
        diff = compare_decision_with_intent(_model_outcome(), _legacy_intent("chat"))
        assert diff["legacy_tool"] is None
        assert diff["tool_agreement"] is False
        assert diff["intent_agreement"] is False

    def test_clarify_is_not_counted_as_a_route_disagreement(self):
        outcome = _model_outcome(
            mode="clarify", tool=None, arguments={}, question="你在哪个城市拍？"
        )
        for legacy in ("chat", "resource_search"):
            diff = compare_decision_with_intent(outcome, _legacy_intent(legacy))
            assert diff["intent_agreement"] is True

    def test_write_intent_maps_to_its_tool(self):
        diff = compare_decision_with_intent(
            _model_outcome(mode="confirm", tool="create_booking", arguments={}),
            _legacy_intent("booking_flow"),
        )
        assert diff["legacy_tool"] == "create_booking"
        assert diff["tool_agreement"] is True
        assert diff["intent_agreement"] is True

    def test_missing_decision_still_reports_the_legacy_side(self):
        diff = compare_decision_with_intent(
            None, _legacy_intent("resource_search", resource_types=["packages"])
        )
        assert diff["legacy_intent"] == "resource_search"
        assert diff["legacy_tool"] == "search_packages"
        assert diff["decision_mode"] is None
        assert diff["tool_agreement"] is False
        assert diff["intent_agreement"] is None


# ── §7.4 + §6.1~§6.5 会话回归 ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tool_loop_search_uses_real_candidates(
    db, customer_user, wedding_packages, monkeypatch
):
    """§6.1 + §4.5：决策层选工具 → 后端真实检索 → 最终 LLM 只负责话术。"""
    decision_provider = DecisionProvider(_search_decision())
    final_provider = RecordingProvider()
    _use_tool_loop(monkeypatch, decision_provider, final_provider)
    conversation = ai_service.create_conversation(db, customer_user.id)

    _, message = await ai_service.send_ai_message(
        db, customer_user.id, conversation.id, "我的婚礼在重庆，有什么拍摄方案推荐？"
    )
    metadata = message.message_metadata

    decision = metadata["agent_decision"]
    assert decision["routing_mode"] == "tool_loop"
    assert decision["parser"] == "model"
    assert decision["applied"] is True
    assert decision["plan"]["action"] == "search"
    assert decision["protocol_version"] == DECISION_SCHEMA_VERSION

    assert metadata["tool_call"]["tool"] == "search_packages"
    assert metadata["tool_call"]["status"] == "success"
    assert metadata["tool_call"]["resource_type"] == "packages"

    assert metadata["intent"]["intent"] == "resource_search"
    assert metadata["retrieval"]["criteria"]["resource_types"] == ["packages"]
    packages = metadata["references"]["packages"]
    assert packages and all(item["id"].startswith("pkg-cq-wedding") for item in packages)
    allowed = metadata["citation_policy"]["allowed_resource_ids"]["packages"]
    assert {item["id"] for item in packages} == set(allowed)
    # 下一轮还能继承条件
    assert metadata["search_context"]["slots"]["city"] == "重庆"


@pytest.mark.asyncio
async def test_tool_loop_clarify_asks_exactly_one_question(
    db, customer_user, wedding_packages, monkeypatch
):
    """§5.3：决策为 clarify 时不检索、不编造，只问一个问题。"""
    decision_provider = DecisionProvider({
        "mode": "clarify",
        "question": "你想在哪个城市拍？预算大概多少？",
        "confidence": 0.9,
    })
    final_provider = RecordingProvider()
    _use_tool_loop(monkeypatch, decision_provider, final_provider)
    conversation = ai_service.create_conversation(db, customer_user.id)

    _, message = await ai_service.send_ai_message(
        db, customer_user.id, conversation.id, "帮我推荐一下拍摄方案"
    )
    metadata = message.message_metadata
    assert message.content == "你想在哪个城市拍？"
    assert message.content.count("？") == 1
    assert metadata["agent_decision"]["plan"]["action"] == "clarify"
    assert metadata["model"]["model"] == "agent-decision-clarify"
    # 没有检索就不能出现任何引用
    assert metadata.get("references") in (None, {})
    assert metadata.get("tool_call") is None
    assert final_provider.messages_history == []


@pytest.mark.asyncio
async def test_tool_loop_chat_decision_skips_retrieval(
    db, customer_user, wedding_packages, monkeypatch
):
    """§6.4：模型判断是知识问答时，不进资源推荐。"""
    decision_provider = DecisionProvider({
        "mode": "chat",
        "confidence": 0.88,
        "reason": "常识问题",
    })
    final_provider = RecordingProvider("婚礼跟拍建议提前踩点并确认流程表。")
    _use_tool_loop(monkeypatch, decision_provider, final_provider)
    conversation = ai_service.create_conversation(db, customer_user.id)

    _, message = await ai_service.send_ai_message(
        db, customer_user.id, conversation.id, "重庆婚礼跟拍一般要注意什么？"
    )
    metadata = message.message_metadata
    assert metadata["intent"]["intent"] == "chat"
    assert metadata["agent_decision"]["plan"]["action"] == "chat"
    assert metadata.get("retrieval") is None
    assert metadata.get("references") in (None, {})
    assert metadata.get("search_context") in (None, {})


@pytest.mark.asyncio
async def test_tool_loop_refinement_excludes_previous_recommendations(
    db, customer_user, wedding_packages, monkeypatch
):
    """§6.2：“换一个”时排除列表由后端注入，模型不需要知道任何资源 ID。"""
    decision_provider = DecisionProvider(
        _search_decision(arguments={"city": "重庆", "styles": ["婚礼"], "limit": 1})
    )
    final_provider = RecordingProvider()
    _use_tool_loop(monkeypatch, decision_provider, final_provider)
    conversation = ai_service.create_conversation(db, customer_user.id)

    _, first = await ai_service.send_ai_message(
        db, customer_user.id, conversation.id, "推荐一个重庆婚礼套餐"
    )
    first_ids = [item["id"] for item in first.message_metadata["references"]["packages"]]
    assert len(first_ids) == 1

    _, second = await ai_service.send_ai_message(
        db, customer_user.id, conversation.id, "这个不太满意，换一个别的"
    )
    metadata = second.message_metadata
    assert metadata["tool_call"]["input"]["exclude_resource_ids"] == first_ids
    second_ids = [item["id"] for item in metadata["references"]["packages"]]
    assert second_ids and not set(second_ids) & set(first_ids)
    # 反馈原话不会变成下一轮的检索关键词
    assert "不太满意" not in metadata["retrieval"]["criteria"]["text"]
    assert "不太满意" not in (metadata["search_context"].get("query_text") or "")


@pytest.mark.asyncio
async def test_tool_loop_photographer_can_search_projects(
    db, photographer_user, wedding_packages, open_project, monkeypatch
):
    """摄影师专属资源：企划走独立工具，并用工具专属约束交给最终 LLM（§4.5）。"""
    decision_provider = DecisionProvider(
        _search_decision(tool="search_projects", arguments={"city": "重庆", "limit": 3})
    )
    final_provider = RecordingProvider("有一条重庆婚礼企划可以应邀。")
    _use_tool_loop(monkeypatch, decision_provider, final_provider)
    conversation = ai_service.create_conversation(db, photographer_user.id)

    _, message = await ai_service.send_ai_message(
        db, photographer_user.id, conversation.id, "最近有什么企划可以接？"
    )
    metadata = message.message_metadata
    assert metadata["agent_decision"]["applied"] is True
    assert metadata["tool_call"]["tool"] == "search_projects"
    assert metadata["tool_call"]["resource_type"] == "projects"
    assert metadata["intent"]["slots"]["resource_types"] == ["projects"]
    projects = metadata["references"]["projects"]
    assert [item["id"] for item in projects] == [open_project.id]
    assert metadata["citation_policy"]["allowed_resource_ids"]["projects"] == [open_project.id]
    # 最终 LLM 拿到的是工具真实结果 + 禁止编造的约束
    tool_prompts = [text for text in final_provider.system_prompts if "search_projects" in text]
    assert tool_prompts
    assert "不要编造" in tool_prompts[0]
    assert open_project.title in tool_prompts[0]


@pytest.mark.asyncio
async def test_tool_loop_write_proposal_still_requires_confirmation(
    db, customer_user, photographer_user, wedding_packages, monkeypatch
):
    """§5.2：即使模型直接给出 confirm create_booking，落单仍走既有确认流程。"""
    decision_provider = DecisionProvider(
        _search_decision(),
        {
            "mode": "confirm",
            "tool": "create_booking",
            "arguments": {"photographer_id": 999},
            "confidence": 0.97,
        },
    )
    final_provider = RecordingProvider()
    _use_tool_loop(monkeypatch, decision_provider, final_provider)
    conversation = ai_service.create_conversation(db, customer_user.id)

    _, first = await ai_service.send_ai_message(
        db, customer_user.id, conversation.id, "推荐重庆婚礼拍摄方案"
    )
    first_package_id = first.message_metadata["references"]["packages"][0]["id"]

    _, second = await ai_service.send_ai_message(
        db, customer_user.id, conversation.id, "帮我预约第一个，8月15日下午2点"
    )
    metadata = second.message_metadata
    # 决策层提出了写操作，但没有接管执行
    assert metadata["agent_decision"]["mode"] == "confirm"
    assert metadata["agent_decision"]["applied"] is False
    assert metadata["agent_decision"]["plan"]["not_applied_reason"] == (
        "legacy_flow_active:booking_flow"
    )
    # 参数来自后端的真实候选，不是模型编的 photographer_id=999
    pending = metadata["task_state"]["pending_action"]
    assert pending["tool"] == "create_booking"
    assert pending["input"]["package_id"] == first_package_id
    assert pending["input"]["photographer_id"] == photographer_user.id
    assert metadata["task_state"]["status"] == "awaiting_confirmation"
    assert db.query(Order).count() == 0


@pytest.mark.asyncio
async def test_tool_loop_falls_back_to_legacy_routing_on_bad_output(
    db, customer_user, wedding_packages, monkeypatch
):
    """§4.5：决策器输出非法时静默回退到既有路由，用户侧行为不退化。"""
    decision_provider = DecisionProvider("我觉得应该搜一下套餐")
    final_provider = RecordingProvider()
    _use_tool_loop(monkeypatch, decision_provider, final_provider)
    conversation = ai_service.create_conversation(db, customer_user.id)

    _, message = await ai_service.send_ai_message(
        db, customer_user.id, conversation.id, "推荐重庆婚礼拍摄方案"
    )
    metadata = message.message_metadata
    assert metadata["agent_decision"]["parser"] == "fallback"
    assert metadata["agent_decision"]["fallback_reason"] == "invalid_json"
    assert metadata["agent_decision"]["applied"] is False
    assert metadata["agent_decision"]["plan"]["not_applied_reason"] == "invalid_json"
    assert metadata.get("tool_call") is None
    # 既有规则路由照常给出真实候选
    assert metadata["intent"]["intent"] == "resource_search"
    assert metadata["references"]["packages"]


@pytest.mark.asyncio
async def test_tool_loop_provider_outage_does_not_break_the_turn(
    db, customer_user, wedding_packages, monkeypatch
):
    decision_provider = BrokenDecisionProvider()
    final_provider = RecordingProvider()
    _use_tool_loop(monkeypatch, decision_provider, final_provider)
    conversation = ai_service.create_conversation(db, customer_user.id)

    _, message = await ai_service.send_ai_message(
        db, customer_user.id, conversation.id, "推荐重庆婚礼拍摄方案"
    )
    metadata = message.message_metadata
    assert metadata["agent_decision"]["fallback_reason"] == "provider_error: RuntimeError"
    assert metadata["references"]["packages"]


@pytest.mark.asyncio
async def test_shadow_mode_records_the_diff_without_changing_behavior(
    db, customer_user, wedding_packages, monkeypatch
):
    """§4.6 + §8：shadow 只观测。决策器说 chat，行为仍按既有路由检索。"""
    decision_provider = DecisionProvider({"mode": "chat", "confidence": 0.99})
    final_provider = RecordingProvider()
    _use_tool_loop(monkeypatch, decision_provider, final_provider, mode="shadow")
    conversation = ai_service.create_conversation(db, customer_user.id)

    _, message = await ai_service.send_ai_message(
        db, customer_user.id, conversation.id, "推荐重庆婚礼拍摄方案"
    )
    metadata = message.message_metadata
    decision = metadata["agent_decision"]
    assert decision["routing_mode"] == "shadow"
    assert decision["parser"] == "model"
    assert decision["mode"] == "chat"
    assert decision["applied"] is False
    assert decision["plan"]["action"] == "chat"
    diff = decision["shadow_diff"]
    assert diff["legacy_intent"] == "resource_search"
    assert diff["legacy_tool"] == "search_packages"
    assert diff["decision_tool"] is None
    assert diff["tool_agreement"] is False
    assert diff["intent_agreement"] is False
    # 行为完全按 legacy：照常检索、照常引用
    assert metadata["intent"]["intent"] == "resource_search"
    assert metadata["references"]["packages"]
    assert metadata.get("tool_call") is None


@pytest.mark.asyncio
async def test_legacy_mode_never_calls_the_decider(
    db, customer_user, wedding_packages, monkeypatch
):
    decision_provider = DecisionProvider(_search_decision())
    final_provider = RecordingProvider()
    _use_tool_loop(monkeypatch, decision_provider, final_provider, mode="legacy")
    conversation = ai_service.create_conversation(db, customer_user.id)

    _, message = await ai_service.send_ai_message(
        db, customer_user.id, conversation.id, "推荐重庆婚礼拍摄方案"
    )
    assert decision_provider.calls == []
    assert message.message_metadata.get("agent_decision") is None
    assert message.message_metadata["references"]["packages"]


# ── §5.5 可观测性 ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_decision_trace_and_dashboard_expose_the_rollout_metrics(
    db, customer_user, wedding_packages, monkeypatch
):
    """灰度期要能按 routing_mode 统计接管率、回退原因和工具延迟。"""
    decision_provider = DecisionProvider(_search_decision())
    final_provider = RecordingProvider()
    _use_tool_loop(monkeypatch, decision_provider, final_provider)
    conversation = ai_service.create_conversation(db, customer_user.id)

    await ai_service.send_ai_message(
        db, customer_user.id, conversation.id, "推荐重庆婚礼拍摄方案"
    )
    trace = db.query(AgentTrace).order_by(AgentTrace.id.desc()).first()
    flags = trace.quality_flags
    assert flags["decision_routing_mode"] == "tool_loop"
    assert flags["decision_parser"] == "model"
    assert flags["decision_mode"] == "tool_call"
    assert flags["decision_tool"] == "search_packages"
    assert flags["decision_applied"] is True
    assert flags["decision_action"] == "search"
    assert flags["decision_fallback"] is False
    assert flags["decision_confidence"] == 0.93
    assert flags["tool_call_tool"] == "search_packages"
    assert flags["tool_call_status"] == "success"
    assert flags["tool_call_count"] >= 1
    assert flags["has_citations"] is True

    dashboard = agent_quality_dashboard(db)
    assert dashboard["decisions"]["total"] == 1
    assert dashboard["decisions"]["applied_rate"] == 1.0
    assert dashboard["decisions"]["fallback_rate"] == 0.0
    assert dashboard["decisions"]["fallback_reasons"] == {}


@pytest.mark.asyncio
async def test_dashboard_buckets_fallback_reasons_by_code(
    db, customer_user, wedding_packages, monkeypatch
):
    decision_provider = DecisionProvider(_search_decision(confidence=0.3))
    final_provider = RecordingProvider()
    _use_tool_loop(monkeypatch, decision_provider, final_provider)
    conversation = ai_service.create_conversation(db, customer_user.id)

    await ai_service.send_ai_message(
        db, customer_user.id, conversation.id, "推荐重庆婚礼拍摄方案"
    )
    dashboard = agent_quality_dashboard(db)
    decisions = dashboard["decisions"]
    assert decisions["applied_rate"] == 0.0
    assert decisions["fallback_rate"] == 1.0
    # 置信度尾巴被收敛成一个分桶，不会打散成上百个 key
    assert decisions["fallback_reasons"] == {"low_confidence": 1}
