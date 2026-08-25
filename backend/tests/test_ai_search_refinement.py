"""多轮资源推荐负反馈场景端到端测试。

验证文档 agentfix260731.txt 中描述的核心问题：
用户先推荐一个套餐，满意后说"这个我不太满意，换一个"，
系统应该继承上一轮的城市和风格，排除已推荐的套餐，给出新的备选。
"""

import pytest

from backend.app.models.photographer import PhotographerProfile
from backend.app.models.user import User
from backend.app.services import ai_service
from backend.app.services.ai_resource_index_service import rebuild_ai_resource_documents


class MultiTurnProvider:
    """模拟多轮对话的 LLM provider。"""

    def __init__(self):
        self.turn = 0
        self.messages_history = []

    async def chat(self, messages, *, temperature=None, response_format=None):
        self.messages_history.append(messages)
        self.turn += 1
        if self.turn == 1:
            return {
                "content": "我找到了重庆婚礼套餐「婚礼精修」，包含精修30张，适合你的需求。",
                "metadata": {"model": {"provider": "test", "model": "test-turn-1"}},
            }
        if self.turn == 2:
            return {
                "content": "另外还有重庆「婚庆写真」套餐，包含精修20张，预算更友好。",
                "metadata": {"model": {"provider": "test", "model": "test-turn-2"}},
            }
        return {
            "content": "根据你的条件，暂时没有其他备选了。",
            "metadata": {"model": {"provider": "test", "model": "test-turn-n"}},
        }


@pytest.fixture
def two_chongqing_packages(db, photographer_user):
    """创建两个重庆婚礼风格套餐，确保第二轮能换一个。"""
    profile = PhotographerProfile(
        user_id=photographer_user.id,
        location="重庆",
        styles=["婚礼", "婚纱"],
        packages=[
            {
                "id": "pkg-wedding-deluxe",
                "name": "婚礼精修",
                "price": 1999,
                "duration": 180,
                "description": "婚礼全程跟拍",
                "includes": ["精修30张", "底片全送"],
                "styles": ["婚礼"],
                "image_count": 30,
            },
            {
                "id": "pkg-wedding-basic",
                "name": "婚庆写真",
                "price": 1299,
                "duration": 120,
                "description": "婚礼仪式拍摄",
                "includes": ["精修20张"],
                "styles": ["婚礼"],
                "image_count": 20,
            },
        ],
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    rebuild_ai_resource_documents(db)
    return profile


@pytest.mark.asyncio
async def test_search_refinement_inherits_previous_conditions_and_excludes_recommended(
    db, customer_user, two_chongqing_packages, monkeypatch
):
    """用户要求换一个时，应继承城市和风格，排除上一个推荐的套餐。"""
    provider = MultiTurnProvider()
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: provider)
    conversation = ai_service.create_conversation(db, customer_user.id)

    # 第一轮：只推荐一个重庆婚礼套餐（对应文档中的真实场景）
    _, msg1 = await ai_service.send_ai_message(
        db, customer_user.id, conversation.id, "帮我推荐一个重庆婚礼套餐"
    )
    metadata1 = msg1.message_metadata
    first_ids = [item["id"] for item in metadata1["references"]["packages"]]
    assert len(first_ids) == 1
    first_id = first_ids[0]
    assert metadata1["search_context"]["schema_version"] == "resource_search_context_v2"
    assert metadata1["search_context"]["status"] == "presenting_options"
    assert metadata1["search_context"]["last_action"] == "search"
    assert metadata1["search_context"]["recommended_resource_ids"] == [first_id]
    assert metadata1["search_context"]["slots"]["city"] == "重庆"
    assert "婚礼" in metadata1["search_context"]["slots"]["styles"]

    # 第二轮：用户说"这个我不太满意，换一个"
    _, msg2 = await ai_service.send_ai_message(
        db, customer_user.id, conversation.id, "这个我不太满意，换一个"
    )
    metadata2 = msg2.message_metadata

    # 验证第二轮检索条件继承了第一轮的城市和风格
    criteria2 = metadata2["retrieval"]["criteria"]
    assert criteria2["city"] == "重庆"
    assert "婚礼" in criteria2["style_terms"]
    assert criteria2["resource_types"] == ["packages"]

    # 验证第二轮排除了第一轮推荐的套餐
    assert metadata2["retrieval"]["diagnostics"]["excluded_resource_ids"] == [first_id]

    # 验证第二轮返回的是另一个套餐
    packages2 = metadata2["references"]["packages"]
    assert len(packages2) == 1
    assert packages2[0]["id"] != first_id


@pytest.mark.asyncio
async def test_search_refinement_empty_result_lets_model_explain_with_diagnosis(
    db, customer_user, two_chongqing_packages, monkeypatch
):
    """换一个之后无结果时，交给最终 LLM 解释，并把结构化诊断喂给它。"""
    provider = MultiTurnProvider()
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: provider)
    conversation = ai_service.create_conversation(db, customer_user.id)

    _, msg1 = await ai_service.send_ai_message(
        db, customer_user.id, conversation.id, "帮我推荐一个重庆婚礼套餐"
    )
    recommended_id = msg1.message_metadata["search_context"]["recommended_resource_ids"][0]

    # 手动排除所有其他套餐，模拟第二轮无备选的场景
    profile = two_chongqing_packages
    profile.packages = [pkg for pkg in profile.packages if pkg["id"] == recommended_id]
    db.commit()
    rebuild_ai_resource_documents(db)

    _, msg2 = await ai_service.send_ai_message(
        db, customer_user.id, conversation.id, "换一个吧"
    )

    # 回答来自最终 LLM，而不是固定兜底话术
    assert msg2.message_metadata["model"]["provider"] == "test"
    assert "暂时没找到完全匹配" not in msg2.content

    # 模型拿到的是结构化诊断：命中数为 0、已排除上一轮推荐、继承的城市条件
    system_prompts = [
        message["content"]
        for message in provider.messages_history[-1]
        if message["role"] == "system"
    ]
    diagnosis = next(prompt for prompt in system_prompts if "matched_resources" in prompt)
    assert recommended_id in diagnosis
    assert "重庆" in diagnosis
    assert "不要编造" in diagnosis


@pytest.mark.asyncio
async def test_search_refinement_empty_result_falls_back_when_model_unavailable(
    db, customer_user, two_chongqing_packages, monkeypatch
):
    """模型不可用时才使用固定兜底：说明已排除上一项并引导放宽条件。"""
    provider = MultiTurnProvider()
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: provider)
    conversation = ai_service.create_conversation(db, customer_user.id)

    _, msg1 = await ai_service.send_ai_message(
        db, customer_user.id, conversation.id, "帮我推荐一个重庆婚礼套餐"
    )
    recommended_id = msg1.message_metadata["search_context"]["recommended_resource_ids"][0]
    profile = two_chongqing_packages
    profile.packages = [pkg for pkg in profile.packages if pkg["id"] == recommended_id]
    db.commit()
    rebuild_ai_resource_documents(db)

    class BrokenProvider:
        async def chat(self, messages, *, temperature=None, response_format=None):
            raise RuntimeError("provider down")

    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: BrokenProvider())
    _, msg2 = await ai_service.send_ai_message(
        db, customer_user.id, conversation.id, "换一个吧"
    )

    assert msg2.message_metadata["model"]["model"] == "search-refinement-empty-fallback"
    assert "除了刚才推荐的那个" in msg2.content
    assert "放宽" in msg2.content
    # 不应该出现"暂时没找到完全匹配"这种复述关键词的话术
    assert "暂时没找到完全匹配" not in msg2.content


@pytest.mark.asyncio
async def test_refinement_phrases_trigger_context_inheritance(
    db, customer_user, two_chongqing_packages, monkeypatch
):
    """验证多种 refinement 表述都能触发继承逻辑。"""
    provider = MultiTurnProvider()
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: provider)

    test_phrases = [
        "换一个",
        "再推荐一个",
        "不太满意，有别的吗",
        "这个不喜欢，还有其他的吗",
    ]

    # 每个短语使用独立会话，避免串行追问耗尽备选资源而干扰断言
    for phrase in test_phrases:
        conversation = ai_service.create_conversation(db, customer_user.id)
        _, first = await ai_service.send_ai_message(
            db, customer_user.id, conversation.id, "帮我推荐一个重庆婚礼套餐"
        )
        first_id = first.message_metadata["references"]["packages"][0]["id"]
        _, msg = await ai_service.send_ai_message(
            db, customer_user.id, conversation.id, phrase
        )
        criteria = msg.message_metadata["retrieval"]["criteria"]
        # 所有 refinement 表述都应继承城市
        assert criteria["city"] == "重庆", f"phrase '{phrase}' should inherit city"
        # 所有 refinement 表述都应排除上一轮推荐
        excluded = msg.message_metadata["retrieval"]["diagnostics"]["excluded_resource_ids"]
        assert excluded == [first_id], f"phrase '{phrase}' should exclude previous recommendation"


@pytest.mark.asyncio
async def test_explicit_new_condition_overrides_inherited(
    db, customer_user, two_chongqing_packages, monkeypatch
):
    """用户在第二轮显式给出新条件时，新条件优先级更高。"""
    provider = MultiTurnProvider()
    monkeypatch.setattr(ai_service, "get_ai_provider", lambda: provider)

    # 创建成都套餐用于对比
    other_user = User(
        email="cd-photographer@test.com",
        hashed_password="$2b$12$dummyhash",
        display_name="成都摄影师",
        role="photographer",
    )
    db.add(other_user)
    db.commit()
    db.refresh(other_user)
    cd_profile = PhotographerProfile(
        user_id=other_user.id,
        location="成都",
        styles=["婚礼"],
        packages=[
            {
                "id": "pkg-cd-wedding",
                "name": "成都婚礼套餐",
                "price": 1599,
                "duration": 150,
                "description": "成都本地婚礼拍摄",
                "includes": ["精修25张"],
                "styles": ["婚礼"],
                "image_count": 25,
            }
        ],
    )
    db.add(cd_profile)
    db.commit()
    rebuild_ai_resource_documents(db)

    conversation = ai_service.create_conversation(db, customer_user.id)

    # 第一轮：推荐重庆婚礼套餐
    await ai_service.send_ai_message(
        db, customer_user.id, conversation.id, "帮我推荐一个重庆婚礼套餐"
    )

    # 第二轮：用户显式说"换成都的"
    _, msg2 = await ai_service.send_ai_message(
        db, customer_user.id, conversation.id, "换一个成都的"
    )
    criteria2 = msg2.message_metadata["retrieval"]["criteria"]

    # 虽然是 refinement 场景，但用户显式给出了"成都"，应覆盖继承的"重庆"
    assert criteria2["city"] == "成都"
    packages2 = msg2.message_metadata["references"]["packages"]
    assert len(packages2) == 1
    assert packages2[0]["package_name"] == "成都婚礼套餐"
