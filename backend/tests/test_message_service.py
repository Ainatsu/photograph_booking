"""
test_message_service.py — 消息服务层单元测试
测试：发送消息、对话历史、联系人列表、未读计数、标记已读
"""
import pytest
from datetime import datetime, timedelta
from fastapi import HTTPException
from backend.app.models.order import OrderStatus
from backend.app.models.order_event import OrderEvent
from backend.app.schemas.order import OrderCreateRequest
from backend.app.services.message_service import (
    send_message,
    get_conversation,
    get_my_contacts,
    get_contact_by_id,
    get_unread_count,
    mark_as_read,
)
from backend.app.services.order_service import create_order, update_order_status
from backend.app.models.user import User
from backend.app.services.user_service import create_user


class TestSendMessage:
    """发送消息测试"""

    @pytest.mark.asyncio
    async def test_send_message_success(self, db, customer_user, photographer_user):
        """正常场景：发送消息成功"""
        message = await send_message(
            db,
            sender_id=customer_user.id,
            receiver_id=photographer_user.id,
            content="您好，想预约拍摄",
        )
        assert message.id is not None
        assert message.content == "您好，想预约拍摄"
        assert message.sender_id == customer_user.id
        assert message.receiver_id == photographer_user.id
        assert message.is_read is False

    @pytest.mark.asyncio
    async def test_send_message_with_order(self, db, customer_user, photographer_user, pending_order):
        """正常场景：关联订单发送消息"""
        message = await send_message(
            db,
            sender_id=customer_user.id,
            receiver_id=photographer_user.id,
            content="关于订单的沟通",
            order_id=pending_order.id,
        )
        assert message.order_id == pending_order.id

    @pytest.mark.asyncio
    async def test_cannot_send_to_self(self, db, customer_user):
        """异常场景：不能给自己发消息"""
        with pytest.raises(HTTPException) as exc:
            await send_message(
                db,
                sender_id=customer_user.id,
                receiver_id=customer_user.id,
                content="给自己发消息",
            )
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_send_empty_content(self, db, customer_user, photographer_user):
        """边界条件：空消息内容"""
        message = await send_message(
            db,
            sender_id=customer_user.id,
            receiver_id=photographer_user.id,
            content="",
        )
        assert message.content == ""

    @pytest.mark.asyncio
    async def test_send_long_content(self, db, customer_user, photographer_user):
        """边界条件：长消息（1000字符）"""
        long_content = "A" * 1000
        message = await send_message(
            db,
            sender_id=customer_user.id,
            receiver_id=photographer_user.id,
            content=long_content,
        )
        assert len(message.content) == 1000


class TestGetConversation:
    """对话历史测试"""

    @pytest.mark.asyncio
    async def test_get_conversation(self, db, customer_user, photographer_user):
        """正常场景：获取两人对话"""
        await send_message(db, customer_user.id, photographer_user.id, "消息1")
        await send_message(db, photographer_user.id, customer_user.id, "回复1")
        await send_message(db, customer_user.id, photographer_user.id, "消息2")

        messages = get_conversation(db, customer_user.id, photographer_user.id)
        assert len(messages) == 3
        assert messages[0]["content"] == "消息1"
        # 按时间正序
        assert messages[-1]["content"] == "消息2"

    @pytest.mark.asyncio
    async def test_conversation_includes_message_reference(self, db, customer_user, photographer_user):
        reference = {
            "type": "work",
            "title": "Spring Portrait",
            "url": "/work/42",
            "cover_url": "/static/work-42.jpg",
        }
        message = await send_message(
            db,
            customer_user.id,
            photographer_user.id,
            "I saw this work and want to ask about booking.",
            reference=reference,
        )

        assert message.reference == reference

        messages = get_conversation(db, customer_user.id, photographer_user.id)
        assert messages[0]["reference"] == reference

    def test_empty_conversation(self, db, customer_user, photographer_user):
        """边界条件：无消息的对话"""
        messages = get_conversation(db, customer_user.id, photographer_user.id)
        assert messages == []

    def test_conversation_pagination(self, db, customer_user, photographer_user):
        """边界条件：分页"""
        messages = get_conversation(
            db, customer_user.id, photographer_user.id, skip=0, limit=10
        )
        assert isinstance(messages, list)

    @pytest.mark.asyncio
    async def test_conversation_includes_order_status_cards(self, db, customer_user, photographer_user):
        data = OrderCreateRequest(
            photographer_id=photographer_user.id,
            package_description="test package",
            appointment_time=datetime(2026, 7, 1, 14, 0, 0),
            duration_minutes=60,
        )
        order = create_order(db, customer_user.id, data)
        created_event = db.query(OrderEvent).filter(
            OrderEvent.order_id == order.id,
            OrderEvent.event_type == "created",
        ).first()

        base_time = datetime(2026, 6, 15, 10, 0, 0)
        created_event.created_at = base_time
        message = await send_message(db, customer_user.id, photographer_user.id, "想确认一下拍摄时间")
        message.created_at = base_time + timedelta(minutes=1)
        db.commit()

        order = update_order_status(db, order, OrderStatus.CONFIRMED, photographer_user.id)
        confirmed_event = db.query(OrderEvent).filter(
            OrderEvent.order_id == order.id,
            OrderEvent.event_type == "confirmed",
        ).first()
        confirmed_event.created_at = base_time + timedelta(minutes=2)
        db.commit()

        timeline = get_conversation(db, customer_user.id, photographer_user.id)

        assert [item["item_type"] for item in timeline] == ["order_event", "message", "order_event"]
        assert timeline[0]["event_type"] == "created"
        assert timeline[0]["order_id"] == order.id
        assert timeline[0]["package_snapshot"] == "test package"
        assert timeline[1]["content"] == "想确认一下拍摄时间"
        assert timeline[2]["event_type"] == "confirmed"
        assert timeline[2]["status"] == OrderStatus.CONFIRMED.value
        assert timeline[2]["actor_id"] == photographer_user.id


class TestMessageAPI:
    def test_create_message_with_reference(self, client, customer_headers, photographer_user):
        reference = {
            "type": "package",
            "title": "Portrait Package",
            "url": "/package/pkg-1",
            "cover_url": "/static/package-pkg-1.jpg",
        }

        response = client.post(
            "/api/v1/messages/",
            json={
                "receiver_id": photographer_user.id,
                "content": "I want to ask about this package.",
                "reference": reference,
            },
            headers=customer_headers,
        )

        assert response.status_code == 201
        assert response.json()["reference"] == reference
        assert response.json()["created_at"].endswith("Z")

        timeline_response = client.get(
            f"/api/v1/messages/conversation/{photographer_user.id}",
            headers=customer_headers,
        )
        assert timeline_response.status_code == 200
        assert timeline_response.json()[0]["reference"] == reference
        assert timeline_response.json()[0]["created_at"].endswith("Z")


class TestGetMyContacts:
    """联系人列表测试"""

    @pytest.mark.asyncio
    async def test_contacts_from_messages(self, db, customer_user, photographer_user):
        """正常场景：从消息获取联系人"""
        await send_message(db, customer_user.id, photographer_user.id, "你好")
        contacts = get_my_contacts(db, customer_user.id)
        assert len(contacts) >= 1
        assert any(c["id"] == photographer_user.id for c in contacts)

    @pytest.mark.asyncio
    async def test_contacts_include_unread_count_per_contact(self, db, customer_user, photographer_user):
        await send_message(db, photographer_user.id, customer_user.id, "unread 1")
        await send_message(db, photographer_user.id, customer_user.id, "unread 2")
        await send_message(db, customer_user.id, photographer_user.id, "outgoing")

        contacts = get_my_contacts(db, customer_user.id)
        contact = next(c for c in contacts if c["id"] == photographer_user.id)
        assert contact["unread_count"] == 2

        mark_as_read(db, customer_user.id, photographer_user.id)
        contacts = get_my_contacts(db, customer_user.id)
        contact = next(c for c in contacts if c["id"] == photographer_user.id)
        assert contact["unread_count"] == 0

    def test_empty_contacts(self, db, customer_user):
        """边界条件：无联系人的用户"""
        contacts = get_my_contacts(db, customer_user.id)
        assert contacts == []

    @pytest.mark.asyncio
    async def test_contacts_from_orders(self, db, customer_user, photographer_user, pending_order):
        """正常场景：从订单获取联系人"""
        contacts = get_my_contacts(db, customer_user.id)
        # customer 的订单关联了 photographer
        assert len(contacts) >= 1
        assert any(c["id"] == photographer_user.id for c in contacts)


class TestGetContactById:
    """按 ID 获取联系人测试"""

    def test_get_contact_by_id_without_existing_conversation(self, db, customer_user, photographer_user):
        """正常场景：无历史消息也能获取联系人信息"""
        contact = get_contact_by_id(db, customer_user.id, photographer_user.id)
        assert contact["id"] == photographer_user.id
        assert contact["display_name"] == photographer_user.display_name
        assert contact["role"] == "photographer"

    def test_get_contact_by_id_rejects_self(self, db, customer_user):
        """异常场景：不能选择自己发消息"""
        with pytest.raises(HTTPException) as exc:
            get_contact_by_id(db, customer_user.id, customer_user.id)
        assert exc.value.status_code == 400

    def test_get_contact_by_id_missing_user(self, db, customer_user):
        """异常场景：联系人不存在"""
        with pytest.raises(HTTPException) as exc:
            get_contact_by_id(db, customer_user.id, 99999)
        assert exc.value.status_code == 404


class TestGetUnreadCount:
    """未读消息计数测试"""

    @pytest.mark.asyncio
    async def test_unread_count(self, db, customer_user, photographer_user):
        """正常场景：计算未读消息数"""
        await send_message(db, photographer_user.id, customer_user.id, "未读1")
        await send_message(db, photographer_user.id, customer_user.id, "未读2")

        count = get_unread_count(db, customer_user.id)
        assert count == 2

    def test_zero_unread(self, db, customer_user):
        """边界条件：无未读消息"""
        count = get_unread_count(db, customer_user.id)
        assert count == 0

    def test_order_events_count_as_unread_for_other_party(self, db, customer_user, photographer_user):
        data = OrderCreateRequest(
            photographer_id=photographer_user.id,
            package_description="test package",
            appointment_time=datetime(2026, 7, 1, 14, 0, 0),
            duration_minutes=60,
        )

        create_order(db, customer_user.id, data)

        assert get_unread_count(db, customer_user.id) == 0
        assert get_unread_count(db, photographer_user.id) == 1

        contacts = get_my_contacts(db, photographer_user.id)
        contact = next(c for c in contacts if c["id"] == customer_user.id)
        assert contact["unread_count"] == 1

    def test_mark_as_read_clears_order_event_unread(self, db, customer_user, photographer_user):
        data = OrderCreateRequest(
            photographer_id=photographer_user.id,
            package_description="test package",
            appointment_time=datetime(2026, 7, 1, 14, 0, 0),
            duration_minutes=60,
        )
        create_order(db, customer_user.id, data)

        assert get_unread_count(db, photographer_user.id) == 1
        mark_as_read(db, photographer_user.id, customer_user.id)

        assert get_unread_count(db, photographer_user.id) == 0
        contacts = get_my_contacts(db, photographer_user.id)
        contact = next(c for c in contacts if c["id"] == customer_user.id)
        assert contact["unread_count"] == 0


class TestMarkAsRead:
    """标记已读测试"""

    @pytest.mark.asyncio
    async def test_mark_as_read(self, db, customer_user, photographer_user):
        """正常场景：标记消息已读"""
        await send_message(db, photographer_user.id, customer_user.id, "未读消息")

        updated = mark_as_read(db, customer_user.id, photographer_user.id)
        assert updated == 1

        # 再次查询未读
        count = get_unread_count(db, customer_user.id)
        assert count == 0

    def test_mark_no_messages(self, db, customer_user, photographer_user):
        """边界条件：标记时无消息"""
        updated = mark_as_read(db, customer_user.id, photographer_user.id)
        assert updated == 0

    @pytest.mark.asyncio
    async def test_mark_only_one_direction(self, db, customer_user, photographer_user):
        """正常场景：只标记特定方向的消息"""
        await send_message(db, photographer_user.id, customer_user.id, "给客户的")
        # 另一个摄影师发的消息
        other = create_user(db, "other_photo@test.com", None, "pass", "其他摄影师", "photographer")
        await send_message(db, other.id, customer_user.id, "另一条")

        updated = mark_as_read(db, customer_user.id, photographer_user.id)
        assert updated == 1
        # 另一条还是未读
        count = get_unread_count(db, customer_user.id)
        assert count == 1
