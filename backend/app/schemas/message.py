"""
站内消息相关 Schema 定义

包含消息发送、查看对话的请求/响应模型。
"""

from pydantic import BaseModel, Field
from typing import Literal, Optional, Union
from datetime import datetime


class MessageReference(BaseModel):
    """A lightweight content reference attached to a chat message."""

    type: Literal["package", "work", "item"] = Field(
        ...,
        description="Referenced content type",
        json_schema_extra={"example": "work"},
    )
    title: str = Field(
        ...,
        max_length=200,
        description="Referenced content title",
        json_schema_extra={"example": "Spring Portrait"},
    )
    url: Optional[str] = Field(
        None,
        max_length=500,
        description="Frontend route to the referenced content",
        json_schema_extra={"example": "/work/123"},
    )
    cover_url: Optional[str] = Field(
        None,
        max_length=500,
        description="Cover image URL for the referenced content",
        json_schema_extra={"example": "/static/work-cover.jpg"},
    )


class MessageCreateRequest(BaseModel):
    """发送消息请求"""
    receiver_id: int = Field(
        ...,
        description="接收方用户 ID",
        example=2,
    )
    content: str = Field(
        ...,
        description="消息正文内容",
        example="您好，我想咨询一下关于婚礼拍摄的档期",
    )
    order_id: Optional[int] = Field(
        None,
        description="关联的订单 ID（可选，沟通特定订单时使用）",
        example=1001,
    )
    reference: Optional[MessageReference] = Field(
        None,
        description="Referenced work or package shown with the message",
        json_schema_extra={
            "example": {
                "type": "work",
                "title": "Spring Portrait",
                "url": "/work/123",
                "cover_url": "/static/work-cover.jpg",
            }
        },
    )


class MessageResponse(BaseModel):
    """消息响应"""
    id: int = Field(..., description="消息唯一 ID", example=5001)
    sender_id: int = Field(..., description="发送方用户 ID", example=1)
    receiver_id: int = Field(..., description="接收方用户 ID", example=2)
    content: str = Field(
        ...,
        description="消息正文内容",
        example="您好，我想咨询一下关于婚礼拍摄的档期",
    )
    order_id: Optional[int] = Field(
        None,
        description="关联的订单 ID",
        example=1001,
    )
    reference: Optional[MessageReference] = Field(
        None,
        description="Referenced work or package shown with the message",
    )
    is_read: bool = Field(..., description="是否已读", example=False)
    created_at: datetime = Field(
        ...,
        description="消息发送时间",
        example="2026-06-09T11:30:00",
    )

    class Config:
        from_attributes = True


class ChatTimelineItem(BaseModel):
    """Unified chat timeline item for user messages and order status cards."""

    item_type: Literal["message", "order_event"] = Field(
        ...,
        description="Timeline item type",
        example="order_event",
    )
    id: Union[int, str] = Field(..., description="Frontend-stable item ID", example="order-event-1001")
    message_id: Optional[int] = Field(None, description="Message ID when item_type is message")
    order_event_id: Optional[int] = Field(None, description="Order history event ID when item_type is order_event")
    sender_id: Optional[int] = Field(None, description="Message sender user ID")
    receiver_id: Optional[int] = Field(None, description="Message receiver user ID")
    content: Optional[str] = Field(None, description="Message text")
    order_id: Optional[int] = Field(None, description="Related order ID")
    reference: Optional[MessageReference] = Field(None, description="Referenced work or package")
    is_read: Optional[bool] = Field(None, description="Message read state")
    event_type: Optional[str] = Field(None, description="Order event type")
    status: Optional[str] = Field(None, description="Order status after the event")
    actor_id: Optional[int] = Field(None, description="User ID that triggered the event")
    actor_role: Optional[str] = Field(None, description="Role that triggered the event")
    actor_name: Optional[str] = Field(None, description="Display name of the actor")
    note: Optional[str] = Field(None, description="Order event note")
    customer_id: Optional[int] = Field(None, description="Order customer user ID")
    photographer_id: Optional[int] = Field(None, description="Order photographer user ID")
    package_snapshot: Optional[str] = Field(None, description="Order package snapshot")
    created_at: datetime = Field(..., description="Timeline item creation time")

    class Config:
        from_attributes = True
