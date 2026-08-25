"""
站内消息 API 路由

提供用户之间发送消息、查看对话历史、联系人列表和未读消息统计等功能。
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.api.deps import get_current_active_user
from backend.app.models.user import User
from backend.app.schemas.message import ChatTimelineItem, MessageCreateRequest, MessageResponse
from backend.app.services.message_service import (
    send_message,
    get_conversation,
    get_my_contacts,
    get_contact_by_id,
    get_unread_count,
    mark_as_read,
)

router = APIRouter(prefix="/messages", tags=["站内消息"])


@router.post(
    "/",
    response_model=MessageResponse,
    status_code=201,
    summary="发送消息",
    description="向指定用户发送站内消息。支持关联订单，关联后可围绕特定订单进行沟通。发送成功后通过 WebSocket 实时推送给接收方。",
    response_description="发送成功的消息信息",
)
async def create_message(
    data: MessageCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """向指定用户发送站内消息"""
    reference = data.reference.model_dump(exclude_none=True) if data.reference else None
    message = await send_message(db, current_user.id, data.receiver_id, data.content, data.order_id, reference)
    return message


@router.get(
    "/conversation/{other_user_id}",
    response_model=list[ChatTimelineItem],
    summary="查看对话历史",
    description="查看当前用户与指定用户之间的历史消息记录，按时间倒序排列，支持分页。",
    response_description="历史消息列表",
)
def view_conversation(
    other_user_id: int,
    skip: int = 0,
    limit: int = 50,
    order_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """查看与指定用户之间的对话历史，支持分页和按订单筛选"""
    return get_conversation(db, current_user.id, other_user_id, skip, limit, order_id)


@router.get(
    "/contacts",
    response_model=list[dict],
    summary="获取联系人列表",
    description="获取与当前用户有过对话记录的所有联系人，按最近联系时间排序。",
    response_description="联系人列表",
)
def list_contacts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """获取与当前用户有过对话记录的联系人列表"""
    return get_my_contacts(db, current_user.id)


@router.get(
    "/contact/{user_id}",
    response_model=dict,
    summary="获取指定联系人信息",
    description="按用户 ID 获取可用于发起新对话的联系人展示信息。",
    response_description="联系人信息",
)
def get_contact(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """按用户 ID 获取可发起新对话的联系人信息"""
    return get_contact_by_id(db, current_user.id, user_id)


@router.get(
    "/unread-count",
    summary="获取未读消息数",
    description="获取当前用户的未读消息总数，用于前端显示未读角标。",
    response_description="未读消息数量",
)
def unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """获取当前用户的未读消息总数"""
    count = get_unread_count(db, current_user.id)
    return {"count": count}


@router.put(
    "/read/{other_user_id}",
    summary="标记消息已读",
    description="将当前用户与指定用户的对话中所有未读消息标记为已读。",
    response_description="操作结果",
)
def mark_read(
    other_user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """将与指定用户的对话中所有未读消息标记为已读"""
    mark_as_read(db, current_user.id, other_user_id)
    return {"ok": True}
