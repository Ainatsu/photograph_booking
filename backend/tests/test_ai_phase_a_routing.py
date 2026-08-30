"""阶段A（结构化条件 + 多轮上下文 + 同义词归一化）测试。

覆盖 codex-agent-llm-tool-routing-refactor-guide.md 的：
- §7.1 单元测试：同义词归一化、控制词清理、slots 合并、资源排除；
- §7.3 检索测试：城市/风格/预算/套餐类型组合与无结果诊断；
- §7.4 会话回归：首轮搜索 → 不满意 → 换一个；首轮搜索 → 修改城市；
- §6.1 / §6.3 / §6.4 验收场景。
"""

import pytest

from backend.app.models.order import Order
from backend.app.models.photographer import PhotographerProfile
from backend.app.models.user import User
from backend.app.services import ai_service
from backend.app.services.ai_domain_synonyms import (
    canonical_term,
    detect_style_terms,
    matches_term,
    normalize_terms,
    term_variants,
)
from backend.app.services.ai_orchestrator_service import recognize_intent_by_rules
from backend.app.services.ai_resource_index_service import rebuild_ai_resource_documents
from backend.app.services.ai_retrieval_service import (
    _extract_budget,
    build_empty_retrieval_prompt,
    describe_criteria,
    describe_resource_types,
    retrieve_references,
    strip_conversation_control_terms,
)
from backend.app.services.ai_search_context_service import (
    apply_refinement_to_slots,
    criteria_from_slots,
    is_search_refinement,
    resolve_refinement,
    retrieval_overrides,
    slot_styles,
)


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


@pytest.fixture
def wedding_packages(db, photographer_user):
    """重庆摄影师，套餐用“婚礼跟拍”这类变体写法标注。"""
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
def chengdu_budget_package(db):
    """成都的低价婚礼套餐，用于验证“换成成都 + 预算2000以内”。"""
    user = User(
        email="cd-wedding@test.com",
        hashed_password="$2b$12$dummyhash",
        display_name="成都婚礼摄影师",
        role="photographer",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    profile = PhotographerProfile(
        user_id=user.id,
        location="成都",
        styles=["婚礼"],
        packages=[
            {
                "id": "pkg-cd-wedding-1680",
                "name": "成都婚礼跟拍",
                "price": 1680,
                "duration": 240,
                "description": "成都本地婚礼跟拍",
                "includes": ["精修50张"],
                "styles": ["婚礼"],
                "image_count": 50,
            }
        ],
    )
    db.add(profile)
    db.commit()
    rebuild_ai_resource_documents(db)
    return profile


# ── §7.1 单元：同义词归一化 ─────────────────────────────────────────────────


class TestDomainSynonyms:
    @pytest.mark.parametrize(
        "variant,expected",
        [
            ("婚庆", "婚礼"),
            ("婚宴", "婚礼"),
            ("婚礼跟拍", "婚礼"),
            ("结婚", "婚礼"),
            ("人像", "写真"),
            ("肖像", "写真"),
            ("婚纱照", "婚纱"),
            ("方案", "套餐"),
            ("服务包", "套餐"),
        ],
    )
    def test_canonical_term(self, variant, expected):
        assert canonical_term(variant) == expected

    def test_unknown_term_passes_through(self):
        assert canonical_term("赛博朋克") == "赛博朋克"
        assert term_variants("赛博朋克") == ("赛博朋克",)

    def test_wedding_not_merged_into_bridal(self):
        """婚礼和婚纱是两类拍摄，不能互相归一化。"""
        assert canonical_term("婚纱") == "婚纱"
        assert "婚纱" not in term_variants("婚礼")

    def test_matches_term_accepts_any_variant(self):
        assert matches_term("婚宴全天跟拍套餐", "婚礼") is True
        assert matches_term("成都婚礼跟拍", "婚庆") is True
        assert matches_term("毕业照写真", "人像") is True
        assert matches_term("毕业照写真", "婚礼") is False

    def test_normalize_terms_dedupes_same_group(self):
        assert normalize_terms(["婚庆", "婚礼跟拍", "婚宴"]) == ["婚礼"]
        assert normalize_terms(["婚礼", "婚纱", "日系"]) == ["婚礼", "婚纱", "日系"]
        assert normalize_terms(None) == []

    def test_detect_style_terms_from_raw_text(self):
        assert detect_style_terms("我的婚礼即将在重庆举办，有没有推荐的婚庆拍摄方案") == ["婚礼"]
        assert detect_style_terms("想拍一组人像") == ["写真"]
        assert detect_style_terms("帮我找个摄影师") == []


# ── §7.1 单元：控制词清理 ───────────────────────────────────────────────────


class TestControlTermStripping:
    @pytest.mark.parametrize(
        "content,controls",
        [
            ("这个我不太满意，换一个", ("这个", "不太满意", "换一个")),
            ("刚才那个不喜欢，还有其他的吗", ("刚才", "那个", "不喜欢", "还有其他")),
            ("这个不合适，再推荐一个", ("这个", "不合适", "再推荐", "一个")),
        ],
    )
    def test_control_words_are_removed(self, content, controls):
        cleaned = strip_conversation_control_terms(content)
        for phrase in controls:
            assert phrase not in cleaned
        # 反馈型原文清理后不应留下任何城市、风格或资源类型特征
        assert not detect_style_terms(cleaned)
        assert "套餐" not in cleaned
        assert "摄影师" not in cleaned

    def test_real_conditions_survive(self):
        cleaned = strip_conversation_control_terms("这个不太满意，换一个成都的婚礼套餐")
        assert "成都" in cleaned
        assert "婚礼" in cleaned
        assert "不太满意" not in cleaned
        assert "换一个" not in cleaned

    def test_city_name_is_not_shaved(self):
        """“换成都的”不能被“换成”切成“都的”。"""
        assert "成都" in strip_conversation_control_terms("换成都的")


# ── §7.1 单元：slots → criteria 与合并 ──────────────────────────────────────


class TestSlotsToCriteria:
    def test_maps_city_styles_budget_makeup(self):
        overrides = criteria_from_slots(
            {"city": "重庆", "styles": ["婚庆"], "budget_max": 2000, "requires_makeup": True}
        )
        assert overrides == {
            "location": "重庆",
            "style_terms": ["婚礼"],
            "budget_max": 2000.0,
            "requires_makeup": True,
        }

    def test_accepts_rule_style_string(self):
        assert slot_styles({"style": "婚宴"}) == ["婚礼"]
        assert criteria_from_slots({"style": ["人像"]}) == {"style_terms": ["写真"]}

    def test_returns_none_without_usable_slots(self):
        assert criteria_from_slots({}) is None
        assert criteria_from_slots({"date": "08-15"}) is None

    def test_ignores_invalid_budget(self):
        assert criteria_from_slots({"budget_max": "很便宜"}) is None


class TestRefinementSlotMerge:
    previous = {
        "slots": {
            "resource_types": ["packages"],
            "city": "重庆",
            "styles": ["婚礼"],
            "budget_max": None,
            "limit": 1,
        },
        "recommended_resource_ids": ["pkg-a"],
        "seen_resource_ids": ["pkg-a"],
        "turn": 1,
    }

    def test_detects_refinement_phrases(self):
        assert is_search_refinement("这个我不太满意，换一个") is True
        assert is_search_refinement("再推荐一个") is True
        assert is_search_refinement("帮我推荐一个重庆婚礼套餐") is False

    def test_no_refinement_without_previous_context(self):
        assert resolve_refinement("换一个", None) is None

    def test_inherits_slots_and_collects_exclusions(self):
        refinement = resolve_refinement("这个我不太满意，换一个", self.previous)
        assert refinement is not None
        assert refinement["exclude_resource_ids"] == ["pkg-a"]
        assert retrieval_overrides(refinement) == {"location": "重庆", "style_terms": ["婚礼"]}

        merged = apply_refinement_to_slots({}, refinement, "这个我不太满意，换一个")
        assert merged["resource_types"] == ["packages"]
        assert merged["city"] == "重庆"
        assert merged["styles"] == ["婚礼"]
        assert merged["limit"] == 1

    def test_current_turn_values_win(self):
        refinement = resolve_refinement("换成都的，预算2000以内", self.previous)
        merged = apply_refinement_to_slots(
            {"city": "成都", "budget_max": 2000}, refinement, "换成都的，预算2000以内"
        )
        assert merged["city"] == "成都"
        assert merged["budget_max"] == 2000
        # 未被修改的条件继续继承
        assert merged["resource_types"] == ["packages"]
        assert merged["styles"] == ["婚礼"]

    def test_explicit_resource_type_replaces_inherited(self):
        refinement = resolve_refinement("换个摄影师吧", self.previous)
        merged = apply_refinement_to_slots({}, refinement, "换个摄影师吧")
        assert merged["resource_types"] == ["photographers"]


# ── §7.3 检索：结构化条件与排除 ─────────────────────────────────────────────


class TestRetrievalWithStructuredCriteria:
    def test_city_style_recalls_variant_tagged_package(self, db, wedding_packages):
        """§6.1：重庆 + 婚庆 应召回标注为“婚礼跟拍/婚宴”的套餐。"""
        retrieval = retrieve_references(
            db,
            "我的婚礼即将在重庆举办，你有没有推荐的婚庆拍摄方案？",
            limit=3,
            criteria_overrides={"location": "重庆", "style_terms": ["婚庆"]},
        )
        assert retrieval is not None
        criteria = retrieval["criteria"]
        assert criteria["city"] == "重庆"
        assert criteria["style_terms"] == ["婚礼"]
        assert criteria["resource_types"] == ["packages"]
        assert retrieval["diagnostics"]["excluded_resource_ids"] == []
        ids = [item["id"] for item in retrieval["references"]["packages"]]
        assert "pkg-cq-wedding-day" in ids

    def test_intent_criteria_override_beats_text_extraction(self, db, wedding_packages):
        """意图确认的城市优先于检索器从原文的抽取，并记入 explicit_fields。"""
        retrieval = retrieve_references(
            db,
            "推荐一个重庆婚礼套餐",
            limit=3,
            criteria_overrides={"location": "成都"},
        )
        assert retrieval["criteria"]["city"] == "成都"
        assert "location" in retrieval["diagnostics"]["explicit_fields"]
        assert retrieval["references"]["packages"] == []

    def test_budget_filters_out_expensive_package(self, db, wedding_packages):
        retrieval = retrieve_references(
            db,
            "重庆婚礼套餐",
            limit=3,
            criteria_overrides={"location": "重庆", "style_terms": ["婚礼"], "budget_max": 2000},
        )
        ids = [item["id"] for item in retrieval["references"]["packages"]]
        assert ids == ["pkg-cq-wedding-half"]

    def test_exclude_resource_ids_removes_recommended(self, db, wedding_packages):
        retrieval = retrieve_references(
            db,
            "这个我不太满意，换一个",
            limit=3,
            resource_types=["packages"],
            inherited_criteria={"location": "重庆", "style_terms": ["婚礼"]},
            exclude_resource_ids=["pkg-cq-wedding-day"],
        )
        ids = [item["id"] for item in retrieval["references"]["packages"]]
        assert "pkg-cq-wedding-day" not in ids
        assert ids == ["pkg-cq-wedding-half"]
        diagnostics = retrieval["diagnostics"]
        assert diagnostics["excluded_resource_ids"] == ["pkg-cq-wedding-day"]
        assert "location" in diagnostics["inherited_fields"]

    def test_feedback_text_does_not_become_keyword(self, db, wedding_packages):
        retrieval = retrieve_references(
            db,
            "这个我不太满意，换一个",
            limit=3,
            resource_types=["packages"],
            inherited_criteria={"location": "重庆", "style_terms": ["婚礼"]},
        )
        terms = retrieval["criteria"]["terms"]
        assert not any(
            fragment in term
            for term in terms
            for fragment in ("不太满意", "换一个", "这个")
        )

    def test_city_without_resources_returns_no_results(self, db, wedding_packages):
        retrieval = retrieve_references(
            db,
            "推荐一个婚礼套餐",
            limit=3,
            criteria_overrides={"location": "拉萨", "style_terms": ["婚礼"]},
        )
        assert retrieval["references"]["packages"] == []

    def test_empty_result_prompt_is_structured(self, db, wedding_packages):
        retrieval = retrieve_references(
            db,
            "推荐一个婚礼套餐",
            limit=3,
            criteria_overrides={"location": "拉萨", "style_terms": ["婚礼"], "budget_max": 800},
            exclude_resource_ids=["pkg-cq-wedding-day"],
        )
        prompt = build_empty_retrieval_prompt(retrieval, refinement={"matched_phrases": ["换一个"]})
        assert "matched_resources" in prompt
        assert "拉萨" in prompt
        assert "pkg-cq-wedding-day" in prompt
        assert "不要编造" in prompt
        # 结构化诊断里不复述用户原话
        assert "推荐一个婚礼套餐" not in prompt


class TestBudgetExtraction:
    """预算只在有金额语境时才成立，日期和张数不能被读成预算。"""

    @pytest.mark.parametrize(
        "content,expected",
        [
            ("帮我找北京 1000 内日系带妆造套餐", 1000),
            ("预算800", 800),
            ("500到1000元", 1000),
            ("不超过1500的婚礼套餐", 1500),
            ("预算1.5k", 1500),
            ("帮我预约第一个，8月15日下午2点", None),
            ("要精修30张的套餐", None),
            ("拍摄时长120分钟", None),
            ("推荐重庆婚礼拍摄方案", None),
        ],
    )
    def test_extract_budget(self, content, expected):
        assert _extract_budget(content) == expected


class TestCriteriaDescription:
    def test_describes_structured_conditions_only(self):
        criteria = {
            "city": "重庆",
            "style_terms": ["婚礼"],
            "budget_max": 2000,
            "resource_types": ["packages"],
            "terms": ["个我不太", "换一个"],
        }
        assert describe_criteria(criteria) == "重庆、婚礼、预算2000元内、套餐"
        assert describe_criteria(criteria, include_resource_types=False) == "重庆、婚礼、预算2000元内"
        assert describe_resource_types(criteria) == "套餐"

    def test_empty_criteria(self):
        assert describe_criteria(None) == ""
        assert describe_resource_types({"resource_types": ["projects"]}) == ""


# ── §7.2 分类：聊天 vs 搜索 ─────────────────────────────────────────────────


class TestIntentBoundaries:
    def test_wedding_package_search_is_resource_search(self):
        intent = recognize_intent_by_rules(
            "我的婚礼即将在重庆举办，你有没有推荐的婚庆拍摄方案？"
        )
        assert intent.intent == "resource_search"
        assert intent.slots.get("resource_types") == ["packages"]
        assert intent.slots.get("city") == "重庆"
        assert slot_styles(intent.slots) == ["婚礼"]

    def test_knowledge_question_is_chat(self):
        """§6.4：婚礼跟拍一般需要注意什么 → 聊天，不是资源搜索。"""
        intent = recognize_intent_by_rules("婚礼跟拍一般需要注意什么？")
        assert intent.intent == "chat"


# ── §7.4 会话回归 ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_conversation_first_search_recalls_synonym_tagged_package(
    db, customer_user, wedding_packages, monkeypatch
):
    """§6.1 端到端：首轮就应识别为套餐搜索并召回“婚宴/婚礼跟拍”套餐。"""
    provider = RecordingProvider()
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: provider)
    conversation = ai_service.create_conversation(db, customer_user.id)

    _, message = await ai_service.send_ai_message(
        db,
        customer_user.id,
        conversation.id,
        "我的婚礼即将在重庆举办，你有没有推荐的婚庆拍摄方案？",
    )
    metadata = message.message_metadata
    assert metadata["intent"]["intent"] == "resource_search"
    criteria = metadata["retrieval"]["criteria"]
    assert criteria["resource_types"] == ["packages"]
    assert criteria["city"] == "重庆"
    assert "婚礼" in criteria["style_terms"]
    packages = metadata["references"]["packages"]
    assert packages
    assert all(item["id"].startswith("pkg-cq-wedding") for item in packages)
    # 引用白名单只包含真实候选
    allowed = metadata["citation_policy"]["allowed_resource_ids"]["packages"]
    assert {item["id"] for item in packages} == set(allowed)


@pytest.mark.asyncio
async def test_conversation_change_city_and_budget_keeps_inherited_conditions(
    db, customer_user, wedding_packages, chengdu_budget_package, monkeypatch
):
    """§6.3：换成成都、预算2000以内、继续推荐一个。"""
    provider = RecordingProvider()
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: provider)
    conversation = ai_service.create_conversation(db, customer_user.id)

    _, first = await ai_service.send_ai_message(
        db, customer_user.id, conversation.id, "推荐重庆婚礼拍摄方案"
    )
    first_ids = [item["id"] for item in first.message_metadata["references"]["packages"]]
    assert first_ids

    _, second = await ai_service.send_ai_message(
        db, customer_user.id, conversation.id, "换成成都，预算2000元以内，继续推荐一个"
    )
    criteria = second.message_metadata["retrieval"]["criteria"]
    assert criteria["city"] == "成都"
    assert criteria["budget_max"] == 2000
    # 资源类型和风格继承上一轮
    assert criteria["resource_types"] == ["packages"]
    assert "婚礼" in criteria["style_terms"]
    packages = second.message_metadata["references"]["packages"]
    assert [item["id"] for item in packages] == ["pkg-cd-wedding-1680"]
    # 历史排除逻辑保留：重庆的旧推荐不会再出现
    assert not set(first_ids) & {item["id"] for item in packages}


@pytest.mark.asyncio
async def test_conversation_select_first_then_book_requires_confirmation(
    db, customer_user, photographer_user, wedding_packages, monkeypatch
):
    """§6.5 / §7.4：搜索 → 选第一个 → 预约，必须引用真实候选并先确认。"""
    provider = RecordingProvider()
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: provider)
    conversation = ai_service.create_conversation(db, customer_user.id)

    _, first = await ai_service.send_ai_message(
        db, customer_user.id, conversation.id, "推荐重庆婚礼拍摄方案"
    )
    first_package_id = first.message_metadata["references"]["packages"][0]["id"]

    _, second = await ai_service.send_ai_message(
        db, customer_user.id, conversation.id, "帮我预约第一个，8月15日下午2点"
    )
    metadata = second.message_metadata
    assert metadata["intent"]["intent"] == "booking_flow"

    # 预约对象来自上一轮的真实候选，不是模型编造的 ID
    task_state = metadata["task_state"]
    assert task_state["status"] == "awaiting_confirmation"
    pending = task_state["pending_action"]
    assert pending["tool"] == "create_booking"
    assert pending["input"]["package_id"] == first_package_id
    assert pending["input"]["photographer_id"] == photographer_user.id
    assert pending["input"]["appointment_time"].endswith("T14:00:00")

    # 只给出确认动作，不直接落单
    actions = metadata["suggested_actions"]
    assert [action["type"] for action in actions] == ["confirm_create_booking"]
    assert actions[0]["requires_confirmation"] is True
    assert db.query(Order).count() == 0

    # 日期不再被当成预算：8月15日不应生成 budget_max=15
    assert metadata["retrieval"]["criteria"]["budget_max"] is None


@pytest.mark.asyncio
async def test_generic_booking_continues_single_recommendation(
    db, customer_user, chengdu_budget_package, monkeypatch
):
    """单个真实套餐后说“帮我预约”必须沿用该套餐，不得重新选同摄影师的其他套餐。"""
    provider = RecordingProvider()
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: provider)
    conversation = ai_service.create_conversation(db, customer_user.id)

    _, first = await ai_service.send_ai_message(
        db, customer_user.id, conversation.id, "推荐成都预算2000以内的婚礼拍摄方案"
    )
    first_package = first.message_metadata["references"]["packages"][0]

    _, second = await ai_service.send_ai_message(
        db, customer_user.id, conversation.id, "帮我预约"
    )
    task_state = second.message_metadata["task_state"]

    assert task_state["status"] == "awaiting_date"
    assert task_state["slots"]["package_id"] == first_package["id"]
    assert task_state["slots"]["selected_package"]["id"] == first_package["id"]
    assert task_state["slots"]["photographer_id"] == first_package["photographer_id"]


@pytest.mark.asyncio
async def test_conversation_chat_question_does_not_recommend_resources(
    db, customer_user, wedding_packages, monkeypatch
):
    """§6.4：知识问答不进入资源推荐，也不产生 search_context。"""
    provider = RecordingProvider("婚礼跟拍要提前踩点、确认流程表、准备备用机身。")
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: provider)
    conversation = ai_service.create_conversation(db, customer_user.id)

    _, message = await ai_service.send_ai_message(
        db, customer_user.id, conversation.id, "婚礼跟拍一般需要注意什么？"
    )
    metadata = message.message_metadata
    assert metadata["intent"]["intent"] == "chat"
    # 聊天不触发资源检索：既没有 retrieval 诊断，也没有引用
    assert metadata.get("retrieval") is None
    assert metadata.get("references") in (None, {})
    assert metadata.get("search_context") in (None, {})
