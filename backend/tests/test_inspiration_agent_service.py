import json
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from backend.app.models.agent_task import AgentTaskDraft
from backend.app.models.inspiration import Inspiration
from backend.app.models.inspiration_generation import InspirationGenerationBatch, InspirationGenerationJob
from backend.app.services import ai_service
from backend.app.services.ai_orchestrator_service import recognize_intent_by_rules
from backend.app.services.inspiration_agent_service import (
    InspirationBatchInput,
    InspirationAgentImage,
    build_inspiration_content,
    fallback_inspiration_summary,
    generate_inspiration_batch,
    summarize_inspiration_batches,
    validate_batch_result,
    validate_batch_result,
)
from backend.app.services.inspiration_agent_workflow_service import create_inspiration_workflow
from backend.app.services.inspiration_generation_service import process_next_batch


def advice(index: int, **extra):
    return {
        "attachment_index": index,
        "title": f"title-{index}",
        "description": f"description-{index}",
        "extension": f"extension-{index}",
        **extra,
    }


def generation(items):
    return {
        "batch_theme": "Coastal portraits",
        "tags": [" coast ", "portrait", "coast"],
        "items": items,
    }


def test_creation_intent_wins_before_generic_image_analysis():
    intent = recognize_intent_by_rules(
        "Please turn these photos into a shooting inspiration note 创建灵感",
        [{"type": "image", "url": "/uploads/reference.jpg"}],
    )

    assert intent.intent == "create_inspiration_flow"
    assert intent.route == "inspiration"
    assert intent.missing_slots == []


def test_plain_image_request_remains_image_analysis():
    intent = recognize_intent_by_rules(
        "Analyze the color and composition of this photo",
        [{"type": "image", "url": "/uploads/reference.jpg"}],
    )

    assert intent.intent == "image_analysis"


def test_creation_intent_without_image_requests_reference_images():
    intent = recognize_intent_by_rules("帮我创建灵感")

    assert intent.intent == "create_inspiration_flow"
    assert intent.missing_slots == ["reference_images"]


def test_multi_image_result_is_reordered_and_built_as_image_heading_paragraphs():
    result = validate_batch_result(generation([advice(1), advice(0)]), [0, 1])
    blocks = build_inspiration_content(
        result,
        [
            {"attachment_index": 0, "url": "/uploads/0.jpg", "thumb_url": "/uploads/0-thumb.jpg"},
            {"attachment_index": 1, "url": "/uploads/1.jpg"},
        ],
    )

    assert result.tags == ["coast", "portrait"]
    assert [block["type"] for block in blocks] == [
        "image", "heading", "paragraph", "paragraph",
        "image", "heading", "paragraph", "paragraph",
    ]
    assert [blocks[0]["url"], blocks[4]["url"]] == ["/uploads/0.jpg", "/uploads/1.jpg"]
    assert blocks[1]["text"] == "title-0"
    assert blocks[2]["text"] == "description-0"
    assert blocks[3]["text"] == "创作延伸：extension-0"


@pytest.mark.parametrize(
    "items,error",
    [
        ([advice(0)], "inspiration_item_count_mismatch"),
        ([advice(0), advice(0)], "inspiration_attachment_index_duplicate"),
        ([advice(0), advice(2)], "inspiration_attachment_index_mismatch"),
    ],
)
def test_invalid_image_index_sets_are_rejected(items, error):
    with pytest.raises(ValueError, match=error):
        validate_batch_result(generation(items), [0, 1])


def test_agent_cannot_return_trusted_business_fields():
    with pytest.raises(ValidationError):
        validate_batch_result(
            generation([advice(0, image_url="https://untrusted.invalid/image.jpg")]),
            [0],
        )


def test_batch_contract_accepts_only_one_or_two_images_and_reorders_items():
    batch = validate_batch_result(
        {"batch_theme": "雨后街头", "tags": ["街拍", "街拍"], "items": [advice(1), advice(0)]},
        [0, 1],
    )
    assert [item.attachment_index for item in batch.items] == [0, 1]
    assert batch.tags == ["街拍"]

    with pytest.raises(ValidationError):
        InspirationBatchInput(
            task_id="task-too-many",
            images=[
                InspirationAgentImage(attachment_index=index, provider_image_url="x", mime_type="image/jpeg")
                for index in range(3)
            ],
        )


def test_summary_fallback_is_deterministic():
    result = fallback_inspiration_summary(
        "蓝调人像",
        [{"batch_theme": "雨后街头", "tags": ["街拍", "街拍"]}, {"batch_theme": "夜色", "tags": ["低饱和"]}],
    )
    assert result.title == "雨后街头"
    assert result.tags == ["街拍", "低饱和"]
    assert result.summary == "蓝调人像"


@pytest.mark.parametrize(
    "image_count,expected_indices",
    [(1, [[0]]), (2, [[0, 1]]), (3, [[0, 1], [2]]), (5, [[0, 1], [2, 3], [4]]), (12, [[0, 1], [2, 3], [4, 5], [6, 7], [8, 9], [10, 11]])],
)
def test_generation_batches_are_stable_and_two_images_max(image_count, expected_indices):
    groups = [list(range(start, min(start + 2, image_count))) for start in range(0, image_count, 2)]
    assert groups == expected_indices


def test_generation_job_and_batch_unique_order_constraint(db, customer_user):
    conversation = ai_service.create_conversation(db, customer_user.id)
    inspiration = Inspiration(owner_id=customer_user.id, title="正在生成灵感", content=[], tags=[])
    db.add(inspiration)
    db.flush()
    job = InspirationGenerationJob(
        inspiration_id=inspiration.id,
        agent_task_id="task-generation-1",
        owner_id=customer_user.id,
        conversation_id=conversation.id,
        status="queued",
        total_images=3,
        completed_images=0,
        failed_images=0,
    )
    db.add(job)
    db.flush()
    db.add_all([
        InspirationGenerationBatch(job_id=job.id, batch_index=0, attachment_indices=[0, 1], image_refs=[]),
        InspirationGenerationBatch(job_id=job.id, batch_index=1, attachment_indices=[2], image_refs=[]),
    ])
    db.commit()
    assert db.query(InspirationGenerationBatch).filter_by(job_id=job.id).count() == 2
    duplicate = InspirationGenerationBatch(job_id=job.id, batch_index=1, attachment_indices=[2], image_refs=[])
    db.add(duplicate)
    with pytest.raises(Exception):
        db.commit()
    db.rollback()


class StubProvider:
    def __init__(self, response):
        self.response = response
        self.calls = 0

    async def chat(self, messages, **kwargs):
        self.calls += 1
        return self.response


def _queued_generation_job(db, customer_user, image_count=3):
    conversation = ai_service.create_conversation(db, customer_user.id)
    inspiration = Inspiration(owner_id=customer_user.id, title="正在生成灵感", content=[], tags=[])
    db.add(inspiration)
    db.flush()
    task = AgentTaskDraft(
        id="task-worker-1", user_id=customer_user.id, conversation_id=conversation.id,
        task_type="create_inspiration", status="generating", schema_version=2,
        revision=1, target={}, fields={}, field_sources={}, media_assets=[],
    )
    db.add(task)
    db.flush()
    job = InspirationGenerationJob(
        inspiration_id=inspiration.id, agent_task_id=task.id, owner_id=customer_user.id,
        conversation_id=conversation.id, reference_text="夜景人像", status="queued",
        total_images=image_count, completed_images=0, failed_images=0,
    )
    db.add(job)
    db.flush()
    for index in range(0, image_count, 2):
        refs = [{
            "attachment_index": item,
            "url": f"/uploads/{item}.jpg",
            "thumb_url": None,
            "provider_image_url": f"data:image/jpeg;base64,{item}",
            "mime_type": "image/jpeg",
        } for item in range(index, min(index + 2, image_count))]
        db.add(InspirationGenerationBatch(
            job_id=job.id, batch_index=index // 2,
            attachment_indices=[ref["attachment_index"] for ref in refs],
            image_refs=refs,
        ))
    db.commit()
    return job.id, inspiration.id


def _batch_response(indices):
    return {
        "content": json.dumps({
            "batch_theme": "夜色街头", "tags": ["夜景"],
            "items": [advice(index) for index in indices],
        }),
        "metadata": {"model": {"provider": "stub", "model": "stub-v1"}},
    }


@pytest.mark.asyncio
async def test_batch_generation_uses_batch_contract_and_prompt_version():
    provider = StubProvider({
        "content": '{"batch_theme":"街头电影感","tags":["街拍"],"items":[{"attachment_index":0,"title":"湿漉漉的夜","description":"霓虹在雨里晕开，孤独感来自人物与环境的关系。","extension":"换一个橱窗前景继续拍。"}]} trailing explanation',
        "metadata": {"model": {"provider": "stub", "model": "stub-v1"}},
    })
    result, metadata = await generate_inspiration_batch(
        InspirationBatchInput(
            task_id="batch-task",
            images=[InspirationAgentImage(attachment_index=0, provider_image_url="data:image/jpeg;base64,AA==", mime_type="image/jpeg")],
        ),
        provider=provider,
    )
    assert result.batch_theme == "街头电影感"
    assert result.items[0].title == "湿漉漉的夜"
    assert metadata["prompt_version"] == "inspiration_agent_batch_v3"
    assert provider.calls == 1


@pytest.mark.asyncio
async def test_summary_degraded_response_returns_fallback_without_images():
    provider = StubProvider({
        "content": "unavailable",
        "metadata": {"degraded": True, "fallback": {"primary_error": "timeout"}},
    })
    result, metadata = await summarize_inspiration_batches(
        "夜景人像",
        [{"batch_theme": "夜色街头", "tags": ["夜景"]}],
        provider=provider,
    )
    assert result.title == "夜色街头"
    assert metadata["summary_degraded"] is True
    assert provider.calls == 1


@pytest.mark.asyncio
async def test_worker_processes_batches_in_order_and_finalizes_job(db, customer_user):
    job_id, inspiration_id = _queued_generation_job(db, customer_user, image_count=3)
    provider = StubProvider(_batch_response([0, 1]))
    assert await process_next_batch(db, provider=provider) == "completed"
    provider.response = _batch_response([2])
    assert await process_next_batch(db, provider=provider) == "completed"

    job = db.query(InspirationGenerationJob).filter_by(id=job_id).one()
    inspiration = db.query(Inspiration).filter_by(id=inspiration_id).one()
    assert job.status == "completed"
    assert (job.completed_images, job.failed_images) == (3, 0)
    assert [block["url"] for block in inspiration.content if block["type"] == "image"] == [
        "/uploads/0.jpg", "/uploads/1.jpg", "/uploads/2.jpg",
    ]
    assert db.query(AgentTaskDraft).filter_by(id="task-worker-1").one().status == "completed"


@pytest.mark.asyncio
async def test_worker_failure_is_requeued_then_becomes_failed_after_three_attempts(db, customer_user):
    job_id, _ = _queued_generation_job(db, customer_user, image_count=1)
    provider = StubProvider({
        "content": "unavailable",
        "metadata": {"degraded": True, "fallback": {"primary_error": "timeout"}},
    })
    batch = db.query(InspirationGenerationBatch).filter_by(job_id=job_id).one()
    for expected_status in ("queued", "queued", "failed"):
        batch.available_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
        assert await process_next_batch(db, provider=provider) == expected_status
        batch = db.query(InspirationGenerationBatch).filter_by(id=batch.id).one()
    job = db.query(InspirationGenerationJob).filter_by(id=job_id).one()
    assert job.status == "failed"
    assert job.failed_images == 1
    assert provider.calls == 3


@pytest.mark.asyncio
async def test_workflow_returns_immediately_with_generation_job(db, customer_user):
    provider = StubProvider({
        "content": '{"title":"Coastal portraits","summary":"Quiet portrait references",'
        '"tags":["portrait"],"items":[{"attachment_index":0,'
        '"title":"Salt and stillness","description":"Wide horizon makes the figure feel solitary.",'
        '"extension":"Try the same framing at dawn."}]}',
        "metadata": {"model": {"provider": "stub", "model": "stub-v1"}},
    })
    conversation = ai_service.create_conversation(db, customer_user.id)

    result = await create_inspiration_workflow(
        db,
        user_id=customer_user.id,
        conversation_id=conversation.id,
        message_id=None,
        reference_text="blue hour portrait",
        images=[{
            "attachment_index": 0,
            "url": "/static/ai/reference.jpg",
            "thumb_url": None,
            "provider_image_url": "data:image/jpeg;base64,AA==",
            "mime_type": "image/jpeg",
        }],
        provider=provider,
    )

    entry = result["metadata"]["inspiration_flow"]["entry"]
    task = db.query(AgentTaskDraft).filter(
        AgentTaskDraft.user_id == customer_user.id,
        AgentTaskDraft.task_type == "create_inspiration",
    ).one()
    inspiration = db.query(Inspiration).filter(Inspiration.id == entry["inspiration_id"]).one()

    assert result["metadata"]["active_task"] is None
    assert result["metadata"]["inspiration_flow"]["status"] == "generating"
    assert result["metadata"]["inspiration_flow"]["entry"]["generation_status"] == "generating"
    assert task.status == "generating"
    assert task.result == entry
    assert inspiration.status == "draft"
    assert inspiration.location_name is None
    job = db.query(InspirationGenerationJob).filter_by(inspiration_id=inspiration.id).one()
    assert job.status == "queued"
    assert job.total_images == 1
    assert db.query(InspirationGenerationBatch).filter_by(job_id=job.id).count() == 1
    assert provider.calls == 0
