"""Phase 7 thread organization services: fork, folders and deterministic search."""
from __future__ import annotations

import copy
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.models.ai_conversation import (
    AIConversation, AIConversationFolder, AIConversationTaskLink, AIMessage,
)
from backend.app.models.agent_task import AgentTaskDraft
from backend.app.services.ai_service import get_conversation_or_404


def create_folder(db: Session, user_id: int, name: str, sort_order: int = 0) -> AIConversationFolder:
    value = " ".join(name.split())
    if not value:
        raise HTTPException(status_code=422, detail="folder name is required")
    folder = AIConversationFolder(user_id=user_id, name=value, sort_order=sort_order)
    db.add(folder)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=409, detail="folder already exists") from None
    db.refresh(folder)
    return folder


def list_folders(db: Session, user_id: int) -> list[AIConversationFolder]:
    return db.query(AIConversationFolder).filter_by(user_id=user_id).order_by(AIConversationFolder.sort_order, AIConversationFolder.id).all()


def assign_folder(db: Session, user_id: int, conversation_id: int, folder_id: int | None):
    conversation = get_conversation_or_404(db, user_id, conversation_id)
    if folder_id is not None and not db.query(AIConversationFolder).filter_by(id=folder_id, user_id=user_id).first():
        raise HTTPException(status_code=404, detail="folder not found")
    conversation.folder_id = folder_id
    db.commit()
    db.refresh(conversation)
    return conversation


def fork_conversation(db: Session, user_id: int, conversation_id: int, *, task_id: str | None = None, turn_id: int | None = None) -> AIConversation:
    source = get_conversation_or_404(db, user_id, conversation_id)
    if turn_id is not None and not db.query(AIMessage).filter_by(id=turn_id, conversation_id=source.id).first():
        raise HTTPException(status_code=404, detail="turn not found")
    root_id = source.root_conversation_id or source.id
    child = AIConversation(
        user_id=user_id, title=f"{source.title or '新对话'}（分支）", status="active", source=source.source,
        approval_policy=source.approval_policy,
        tool_permission_profile=source.tool_permission_profile,
        confirmation_mode=source.confirmation_mode,
        summary=source.summary, root_conversation_id=root_id,
        forked_from_conversation_id=source.id,
        fork_boundary=(f"task:{task_id}" if task_id else f"turn:{turn_id}" if turn_id else "conversation"),
    )
    db.add(child)
    db.flush()
    query = db.query(AIMessage).filter(AIMessage.conversation_id == source.id)
    if turn_id is not None:
        query = query.filter(AIMessage.id <= turn_id)
    for message in query.order_by(AIMessage.id).all():
        db.add(AIMessage(conversation_id=child.id, role=message.role, content=message.content, message_metadata=copy.deepcopy(message.message_metadata)))
    if task_id:
        task = db.query(AgentTaskDraft).filter_by(id=str(task_id), user_id=user_id, conversation_id=source.id).first()
        if not task:
            raise HTTPException(status_code=404, detail="task not found")
        new_task_id = str(uuid4())
        db.add(AgentTaskDraft(
            id=new_task_id, user_id=user_id, conversation_id=child.id, task_type=task.task_type,
            status="collecting", schema_version=task.schema_version, revision=task.revision,
            target=copy.deepcopy(task.target or {}), fields=copy.deepcopy(task.fields or {}),
            field_sources=copy.deepcopy(task.field_sources or {}), media_assets=copy.deepcopy(task.media_assets or []),
        ))
        db.add(AIConversationTaskLink(source_task_id=task.id, target_task_id=new_task_id,
            source_conversation_id=source.id, target_conversation_id=child.id, user_id=user_id, relation_type="derived_from"))
        child.active_task_id = new_task_id
    db.commit()
    db.refresh(child)
    return child


def search_conversations(db: Session, user_id: int, query: str, *, include_archived: bool = False, limit: int = 50) -> list[AIConversation]:
    needle = " ".join((query or "").lower().split())
    if not needle:
        return []
    conversations = db.query(AIConversation).filter(AIConversation.user_id == user_id).order_by(AIConversation.updated_at.desc(), AIConversation.id.desc()).all()
    results = []
    for conversation in conversations:
        if not include_archived and (conversation.archived_at is not None or conversation.status == "deleted"):
            continue
        tasks = db.query(AgentTaskDraft).filter_by(user_id=user_id, conversation_id=conversation.id).all()
        parts = [conversation.title, conversation.last_message_preview, conversation.summary]
        parts += [task.task_type for task in tasks]
        for message in db.query(AIMessage).filter_by(conversation_id=conversation.id).all():
            parts.extend([message.content, str(message.message_metadata or {})])
        if needle in " ".join(str(value or "") for value in parts).lower():
            results.append(conversation)
            if len(results) >= limit:
                break
    return results
