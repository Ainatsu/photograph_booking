"""
AI 摄影助手 API 路由

提供 AI 对话的创建、消息收发和图片上传等功能。
"""

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_active_user
from backend.app.core.database import get_db
from backend.app.models.ai_conversation import AIMessage
from backend.app.models.user import User
from backend.app.schemas.ai import (
    AIChatResponse,
    AIConversationCreate,
    AIConversationResponse,
    AIMessageAttachment,
    AIMessageCreate,
    AIMessageResponse,
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
from backend.app.utils.file_upload import save_upload_file

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
    return create_conversation(db, current_user.id, data.title)


@router.get("/conversations", response_model=list[AIConversationResponse])
def get_ai_conversations(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """分页获取当前用户的 AI 对话列表"""
    return list_conversations(db, current_user.id, skip, limit)


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
    )
    return {
        "user_message": user_message,
        "assistant_message": assistant_message,
        "active_task": serialize_task(get_active_task(db, current_user.id, conversation_id)),
    }


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
    )
    db.commit()
    db.refresh(task)
    return serialize_task(task)


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
    url = await save_upload_file(file, sub_dir="ai")
    return {"url": url, "mime_type": file.content_type or "image/jpeg"}
