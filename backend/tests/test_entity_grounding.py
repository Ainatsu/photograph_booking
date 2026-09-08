"""ai_entity_grounding_service 的单元测试。"""

import pytest

from backend.app.services import ai_entity_grounding_service as grounding


@pytest.fixture(autouse=True)
def fresh_entity_cache():
    """实体名缓存跨用例隔离：每个用例都重新从自己的 db 里收集。"""
    grounding._entity_cache["ts"] = 0.0
    grounding._entity_cache["names"] = frozenset()
    yield
    grounding._entity_cache["ts"] = 0.0
    grounding._entity_cache["names"] = frozenset()


def test_extracts_label_names_with_decorations():
    content = (
        "我为你找到了几组可以参考的摄影师。\n"
        "1.  **摄影师：林小夏**\n"
        "2.  **摄影师：陈一帆**"
    )
    mentions = grounding.extract_entity_mentions(content)
    assert "林小夏" in mentions
    assert "陈一帆" in mentions


def test_label_name_trims_trailing_description():
    # 冒号后的名称粘着描述词时，截断到名称本身，避免漏判或误判。
    mentions = grounding.extract_entity_mentions("摄影师：林小夏 擅长清新自然的户外人像。")
    assert "林小夏" in mentions
    assert all("擅长" not in name for name in mentions)


def test_extracts_titles_and_anchored_quoted_names():
    content = "推荐作品《海边的夏日午后》，也可以看看摄影师「张小雅」和「云间漫步」的作品。"
    mentions = grounding.extract_entity_mentions(content)
    assert "海边的夏日午后" in mentions
    assert "张小雅" in mentions
    assert "云间漫步" in mentions


def test_quoted_style_word_not_extracted():
    # 推荐语境里的风格词不带实体锚点，不应被当成实体名。
    assert "日系" not in grounding.extract_entity_mentions("这种「日系」风格很适合你，推荐尝试。")


def test_generic_label_content_not_extracted():
    mentions = grounding.extract_entity_mentions("套餐：建议选择基础款，适合新手。")
    assert mentions == []


def test_detect_fabricated_entities_flags_unknown_only(db, photographer_profile):
    content = "摄影师：测试摄影师 的套餐：个人写真 都不错，另外 摄影师：林小夏 也可以。"
    assert grounding.detect_fabricated_entities(db, content) == ["林小夏"]


def test_detect_allows_names_from_dialogue(db, photographer_profile):
    # 用户自己提过的名字不算编造。
    assert (
        grounding.detect_fabricated_entities(
            db, "摄影师：林小夏", dialogue_text="我想找林小夏拍照"
        )
        == []
    )


def test_strip_entity_lines_keeps_other_content(db):
    content = (
        "我为你找到了几组摄影师。\n"
        "1. **摄影师：林小夏** 擅长日系。\n"
        "需要更多信息可以告诉我。"
    )
    stripped = grounding.strip_entity_lines(content, ["林小夏"])
    assert "林小夏" not in stripped
    assert "我为你找到了几组摄影师" in stripped
    assert "需要更多信息" in stripped


@pytest.mark.asyncio
async def test_enforce_retries_once_and_uses_clean_reply(db, photographer_profile):
    calls = []

    class FakeProvider:
        # 初始编造结果由调用方传入（未经 provider），enforce 里的第一次 provider 调用就是重答。
        async def chat(self, messages):
            calls.append(messages)
            return {"content": "便携直出可以考虑理光GR3或富士X100VI。", "metadata": {}}

    result = await grounding.enforce_chat_entity_grounding(
        db,
        provider=FakeProvider(),
        provider_messages=[
            {"role": "system", "content": "system"},
            {"role": "user", "content": "推荐一台便携相机"},
        ],
        result={"content": "**摄影师：林小夏** 擅长日系。", "metadata": {}},
    )
    assert len(calls) == 1
    assert "林小夏" not in result["content"]
    assert result["content"] == "便携直出可以考虑理光GR3或富士X100VI。"
    assert result["metadata"]["grounding_corrections"][0]["action"] == "retry"


@pytest.mark.asyncio
async def test_enforce_strips_lines_when_retry_still_fabricates(db, photographer_profile):
    class StubbornProvider:
        async def chat(self, messages):
            return {
                "content": "我为你找到了几组摄影师。\n1. **摄影师：林小夏** 擅长日系。",
                "metadata": {},
            }

    result = await grounding.enforce_chat_entity_grounding(
        db,
        provider=StubbornProvider(),
        provider_messages=[
            {"role": "system", "content": "system"},
            {"role": "user", "content": "推荐一台便携相机"},
        ],
        result={
            "content": "我为你找到了几组摄影师。\n1. **摄影师：林小夏** 擅长日系。",
            "metadata": {},
        },
    )
    assert "林小夏" not in result["content"]
    assert "我为你找到了几组摄影师" in result["content"]
    actions = [c["action"] for c in result["metadata"]["grounding_corrections"]]
    assert actions == ["retry", "strip_lines"]


@pytest.mark.asyncio
async def test_enforce_passes_through_clean_reply(db, photographer_profile):
    class CleanProvider:
        async def chat(self, messages):
            raise AssertionError("clean reply should not trigger a second call")

    result = await grounding.enforce_chat_entity_grounding(
        db,
        provider=CleanProvider(),
        provider_messages=[
            {"role": "system", "content": "system"},
            {"role": "user", "content": "推荐一台便携相机"},
        ],
        result={"content": "便携直出可以考虑理光GR3。", "metadata": {}},
    )
    assert result["content"] == "便携直出可以考虑理光GR3。"
    assert "grounding_corrections" not in (result.get("metadata") or {})
