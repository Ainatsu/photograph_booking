"""
AI 摄影助手 API 路由

提供 AI 对话的创建、消息收发和图片上传等功能。
"""

from fastapi import APIRouter, Depends, File, Query, UploadFile, status, Header, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_active_user
from backend.app.core.database import get_db
from backend.app.core.config import settings
from backend.app.models.ai_conversation import AIMessage
from backend.app.models.user import User
from backend.app.schemas.ai import (
    AIChatResponse,
    AIConversationCreate,
    AIConversationResponse,
    AIConversationUpdate,
    AIConversationForkRequest, AIConversationFolderCreate, AIConversationFolderResponse,
    AIMessageAttachment,
    AIMessageCreate,
    AIMessageResponse,
    AgentTaskFormRevisionResponse,
    AgentTaskCommit,
    AgentTaskComplete,
    AgentTaskPatch,
    PublishPolishRequest,
    PublishPolishResponse,
)
from backend.app.services.ai_publish_polish_service import polish_publish_fields
from backend.app.services.ai_service import (
    create_conversation,
    get_conversation_or_404,
    list_conversations,
    list_messages,
    send_ai_message,
    update_conversation,
)
from backend.app.services.agent_task_service import (
    cancel_task,
    commit_task,
    complete_task,
    get_active_task,
    open_task,
    patch_task,
    serialize_task,
)
from backend.app.services.agent_form_revision_service import list_form_revisions
from backend.app.services.ai_event_service import append_event, event_stream, list_events
from backend.app.services.ai_thread_service import create_folder, list_folders, assign_folder, fork_conversation, search_conversations
from backend.app.services.agent_history_compression_service import get_retained_context
from backend.app.models.ai_conversation import AIConversationEvent
from backend.app.services.image_generation_job_service import (
    cancel_image_generation_job,
    get_image_generation_job,
    regenerate_image_generation_job,
    retry_image_generation_job,
)
from backend.app.utils.file_upload import save_ai_image_upload

router = APIRouter(prefix="/ai", tags=["AI 摄影助手"])


@router.post("/publish/polish", response_model=PublishPolishResponse)
async def polish_publish_form(
    data: PublishPolishRequest,
    current_user: User = Depends(get_current_active_user),
):
    """Polish allow-listed publishing text fields without accepting media."""
    del current_user
    return await polish_publish_fields(data.content_type, data.fields)


@router.post(
    "/conversations",
    response_model=AIConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_ai_conversation(
    data: AIConversationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """创建新的 AI 对话"""
    return create_conversation(db, current_user.id, data.title,
        approval_policy=data.approval_policy,
        tool_permission_profile=data.tool_permission_profile,
        confirmation_mode=data.confirmation_mode)


@router.get("/conversations", response_model=list[AIConversationResponse])
def get_ai_conversations(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    include_archived: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """分页获取当前用户的 AI 对话列表"""
    return list_conversations(
        db,
        current_user.id,
        skip,
        limit,
        include_archived=include_archived,
    )


@router.get("/conversations/search", response_model=list[AIConversationResponse])
def search_ai_conversations(q: str = Query(min_length=1, max_length=200), include_archived: bool = False, limit: int = Query(default=50, ge=1, le=100), db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    return search_conversations(db, current_user.id, q, include_archived=include_archived, limit=limit)


@router.post("/conversation-folders", response_model=AIConversationFolderResponse, status_code=status.HTTP_201_CREATED)
def create_ai_conversation_folder(data: AIConversationFolderCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    return create_folder(db, current_user.id, data.name, data.sort_order)


@router.get("/conversation-folders", response_model=list[AIConversationFolderResponse])
def get_ai_conversation_folders(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    return list_folders(db, current_user.id)


@router.get("/conversations/{conversation_id}", response_model=AIConversationResponse)
def get_ai_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get one user-owned conversation container."""
    return get_conversation_or_404(db, current_user.id, conversation_id)


@router.get("/conversations/{conversation_id}/tool-policy")
def get_ai_tool_policy(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Return the effective approval policy for confirmation-capable clients."""
    conversation = get_conversation_or_404(db, current_user.id, conversation_id)
    return {
        "conversation_id": conversation.id,
        "approval_policy": conversation.approval_policy or "confirm_write",
        "tool_permission_profile": conversation.tool_permission_profile or "normal",
        "confirmation_mode": conversation.confirmation_mode or "inline",
    }


@router.patch("/conversations/{conversation_id}", response_model=AIConversationResponse)
def patch_ai_conversation(
    conversation_id: int,
    data: AIConversationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Rename, archive, or restore one AI conversation."""
    return update_conversation(
        db,
        current_user.id,
        conversation_id,
        title=data.title,
        update_title="title" in data.model_fields_set,
        archived=data.archived,
        status_value=data.status,
        summary=data.summary,
        source=data.source,
        approval_policy=data.approval_policy,
        tool_permission_profile=data.tool_permission_profile,
        confirmation_mode=data.confirmation_mode,
    )


@router.post("/conversations/{conversation_id}/folder", response_model=AIConversationResponse)
def set_ai_conversation_folder(conversation_id: int, folder_id: int | None = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    return assign_folder(db, current_user.id, conversation_id, folder_id)


@router.post("/conversations/{conversation_id}/fork", response_model=AIConversationResponse, status_code=status.HTTP_201_CREATED)
def fork_ai_conversation(conversation_id: int, data: AIConversationForkRequest | None = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    if not settings.AI_THREAD_FORK_ENABLED:
        raise HTTPException(status_code=404, detail="thread fork is disabled")
    data = data or AIConversationForkRequest()
    return fork_conversation(db, current_user.id, conversation_id, task_id=data.task_id, turn_id=data.turn_id)


@router.get("/conversations/{conversation_id}/messages", response_model=list[AIMessageResponse])
def get_ai_messages(
    conversation_id: int,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """分页获取指定 AI 对话的消息记录"""
    return list_messages(db, current_user.id, conversation_id, skip, limit)


@router.post("/conversations/{conversation_id}/messages", response_model=AIChatResponse)
async def create_ai_message(
    conversation_id: int,
    data: AIMessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """发送用户消息并返回 AI 助手回复"""
    attachments_data = None
    if data.attachments:
        attachments_data = [att.model_dump() for att in data.attachments]
    task_submission = (
        data.task_submission.model_dump(mode="json")
        if data.task_submission
        else None
    )
    user_message, assistant_message = await send_ai_message(
        db,
        current_user.id,
        conversation_id,
        data.content,
        attachments_data,
        data.page_context,
        task_submission,
        (
            data.shoot_context_selection.model_dump(mode="json")
            if data.shoot_context_selection
            else None
        ),
        data.generation_request,
    )
    # Events are appended after messages have committed, so consumers never see
    # an event pointing at an uncommitted message.
    append_event(
        db, user_id=current_user.id, conversation_id=conversation_id,
        event_type="message.created", turn_id=str(user_message.id),
        payload={"message_id": user_message.id, "role": "user"},
    )
    append_event(
        db, user_id=current_user.id, conversation_id=conversation_id,
        event_type="message.completed", turn_id=str(assistant_message.id),
        payload={"message_id": assistant_message.id, "role": "assistant"},
    )
    return {
        "user_message": user_message,
        "assistant_message": assistant_message,
        "active_task": serialize_task(get_active_task(db, current_user.id, conversation_id)),
    }


@router.get("/conversations/{conversation_id}/events")
def get_ai_events(
    conversation_id: int,
    after_sequence: int = Query(default=0, ge=0),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Read durable conversation events for catch-up and reconnects."""
    get_conversation_or_404(db, current_user.id, conversation_id)
    return [
        {
            "event_id": event.event_id,
            "conversation_id": event.conversation_id,
            "task_id": event.task_id,
            "turn_id": event.turn_id,
            "sequence": event.sequence,
            "type": event.type,
            "payload": event.payload or {},
            "created_at": event.created_at,
        }
        for event in list_events(db, user_id=current_user.id, conversation_id=conversation_id, after_sequence=after_sequence, limit=limit)
    ]


@router.get("/conversations/{conversation_id}/events/stream")
async def stream_ai_events(
    conversation_id: int,
    after_sequence: int = Query(default=0, ge=0),
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """SSE stream with durable catch-up, monotonic ordering and heartbeats."""
    get_conversation_or_404(db, current_user.id, conversation_id)
    # Browsers send Last-Event-ID on reconnect; sequence remains the canonical cursor.
    if last_event_id:
        event = db.query(AIConversationEvent).filter_by(
            event_id=last_event_id, conversation_id=conversation_id, user_id=current_user.id
        ).first()
        if event:
            after_sequence = max(after_sequence, event.sequence)
    return StreamingResponse(
        event_stream(user_id=current_user.id, conversation_id=conversation_id, after_sequence=after_sequence),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.get("/conversations/{conversation_id}/retained-context")
def get_ai_retained_context(
    conversation_id: int,
    max_chars: int = Query(default=6000, ge=500, le=20000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Return the latest bounded history summary for diagnostics and clients."""
    get_conversation_or_404(db, current_user.id, conversation_id)
    return get_retained_context(db, conversation_id=conversation_id, max_chars=max_chars)


@router.get("/conversations/{conversation_id}/active-task")
def get_active_agent_task(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    get_conversation_or_404(db, current_user.id, conversation_id)
    return serialize_task(get_active_task(db, current_user.id, conversation_id))


@router.get("/conversations/{conversation_id}/tasks/{task_id}")
def get_agent_task(
    conversation_id: int,
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    from backend.app.services.agent_task_service import _owned
    return serialize_task(_owned(db, current_user.id, conversation_id, task_id))


@router.patch("/conversations/{conversation_id}/tasks/{task_id}")
def patch_agent_task(
    conversation_id: int,
    task_id: str,
    data: AgentTaskPatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    task = patch_task(
        db, user_id=current_user.id, conversation_id=conversation_id, task_id=task_id,
        revision=data.revision, operations=[item.model_dump() for item in data.operations],
        idempotency_key=str(data.idempotency_key) if data.idempotency_key else None,
        source=data.source,
    )
    db.commit()
    db.refresh(task)
    append_event(db, user_id=current_user.id, conversation_id=conversation_id, task_id=task_id,
                 event_type="task.form_updated", payload={"revision": task.revision})
    return serialize_task(task)


@router.get("/conversations/{conversation_id}/tasks/{task_id}/form-revisions", response_model=list[AgentTaskFormRevisionResponse])
def get_agent_task_form_revisions(
    conversation_id: int,
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    from backend.app.services.agent_task_service import _owned
    _owned(db, current_user.id, conversation_id, task_id)
    return list_form_revisions(
        db,
        task_id=task_id,
        user_id=current_user.id,
        conversation_id=conversation_id,
    )


@router.post("/conversations/{conversation_id}/tasks/{task_id}/open")
def open_agent_task(
    conversation_id: int,
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    task = open_task(db, user_id=current_user.id, conversation_id=conversation_id, task_id=task_id)
    db.commit()
    db.refresh(task)
    append_event(db, user_id=current_user.id, conversation_id=conversation_id, task_id=task_id,
                 event_type="task.started", payload={"status": task.status})
    return serialize_task(task)


@router.post("/conversations/{conversation_id}/tasks/{task_id}/cancel")
def cancel_agent_task(
    conversation_id: int,
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    task = cancel_task(db, user_id=current_user.id, conversation_id=conversation_id, task_id=task_id)
    db.commit()
    db.refresh(task)
    append_event(db, user_id=current_user.id, conversation_id=conversation_id, task_id=task_id,
                 event_type="task.cancelled", payload={"status": task.status})
    return serialize_task(task)


@router.post("/conversations/{conversation_id}/tasks/{task_id}/complete")
def complete_agent_task(
    conversation_id: int,
    task_id: str,
    data: AgentTaskComplete | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    task = complete_task(
        db, user_id=current_user.id, conversation_id=conversation_id, task_id=task_id,
        result=data.result if data else None,
    )
    db.commit()
    db.refresh(task)
    append_event(db, user_id=current_user.id, conversation_id=conversation_id, task_id=task_id,
                 event_type="task.completed", payload={"status": task.status})
    return serialize_task(task)


@router.post("/conversations/{conversation_id}/tasks/{task_id}/commit")
def commit_agent_task(
    conversation_id: int,
    task_id: str,
    data: AgentTaskCommit,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    task, receipt = commit_task(
        db,
        user_id=current_user.id,
        conversation_id=conversation_id,
        task_id=task_id,
        revision=data.revision,
        idempotency_key=str(data.idempotency_key),
    )
    assistant_message = AIMessage(
        conversation_id=conversation_id,
        role="assistant",
        content=receipt["content"],
        message_metadata={
            "model": {"provider": "platform_task", "model": "agent-task-commit"},
            "agent_task_receipt": receipt,
            "task_state": {
                "task_type": task.task_type,
                "status": "completed" if receipt["status"] == "success" else "failed",
                "task_id": task.id,
                "pending_action": None,
            },
        },
    )
    db.add(assistant_message)
    db.commit()
    db.refresh(task)
    db.refresh(assistant_message)
    append_event(db, user_id=current_user.id, conversation_id=conversation_id, task_id=task_id,
                 event_type="task.completed" if receipt["status"] == "success" else "task.failed",
                 payload={"status": receipt["status"], "revision": data.revision})
    return {
        "task": serialize_task(task),
        "assistant_message": AIMessageResponse.model_validate(assistant_message).model_dump(mode="json", by_alias=True),
        "receipt": receipt,
    }


@router.post("/uploads")
async def upload_ai_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
):
    """上传 AI 对话中使用的图片，返回图片 URL"""
    return await save_ai_image_upload(file, sub_dir=f"ai/{current_user.id}")


@router.get("/image-generations/{job_id}")
def get_ai_image_generation(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    return get_image_generation_job(db, owner_id=current_user.id, job_id=job_id)


@router.post("/image-generations/{job_id}/retry")
def retry_ai_image_generation(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    return retry_image_generation_job(db, owner_id=current_user.id, job_id=job_id)


@router.post("/image-generations/{job_id}/regenerate")
def regenerate_ai_image_generation(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    return regenerate_image_generation_job(db, owner_id=current_user.id, job_id=job_id)


@router.post("/image-generations/{job_id}/cancel")
def cancel_ai_image_generation(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    return cancel_image_generation_job(db, owner_id=current_user.id, job_id=job_id)
