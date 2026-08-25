"""
test_ws_manager.py — WebSocket 连接管理器单元测试
测试：连接管理、消息推送、在线状态
"""
import json
from datetime import date, datetime
from decimal import Decimal

import pytest
from unittest.mock import AsyncMock
from backend.app.services.ws_manager import ConnectionManager


class TestConnectionManager:
    """WebSocket 连接管理器测试"""

    @pytest.fixture
    def manager(self):
        """每个测试用新的 manager 实例"""
        return ConnectionManager()

    @pytest.fixture
    def mock_websocket(self):
        """模拟 WebSocket"""
        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_text = AsyncMock()
        return ws

    @pytest.mark.asyncio
    async def test_connect_adds_user(self, manager, mock_websocket):
        """正常场景：连接注册用户"""
        await manager.connect(user_id=1, websocket=mock_websocket)
        assert manager.is_online(1) is True
        mock_websocket.accept.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_disconnect_removes_user(self, manager, mock_websocket):
        """正常场景：断开移除用户"""
        await manager.connect(user_id=1, websocket=mock_websocket)
        manager.disconnect(user_id=1)
        assert manager.is_online(1) is False

    @pytest.mark.asyncio
    async def test_disconnect_nonexistent_user(self, manager):
        """边界条件：断开不存在用户不报错"""
        manager.disconnect(user_id=999)
        assert manager.is_online(999) is False

    @pytest.mark.asyncio
    async def test_is_online_returns_false_for_unknown(self, manager):
        """边界条件：未知用户不在线"""
        assert manager.is_online(123) is False

    @pytest.mark.asyncio
    async def test_send_personal_message_to_online_user(self, manager, mock_websocket):
        """正常场景：推送给在线用户"""
        await manager.connect(user_id=1, websocket=mock_websocket)
        message = {"type": "notification", "content": "Hello"}

        await manager.send_personal_message(message, user_id=1)
        mock_websocket.send_text.assert_awaited_once_with(
            '{"type":"notification","content":"Hello"}'
        )

    @pytest.mark.asyncio
    async def test_send_personal_message_serializes_order_event_values(self, manager, mock_websocket):
        await manager.connect(user_id=1, websocket=mock_websocket)
        message = {
            "type": "order_event",
            "event": {
                "delivery_due_at": datetime(2026, 8, 8, 10, 0),
                "shoot_date": date(2026, 8, 1),
                "final_price": Decimal("1288.50"),
            },
        }

        await manager.send_personal_message(message, user_id=1)

        sent = json.loads(mock_websocket.send_text.await_args.args[0])
        assert sent["event"] == {
            "delivery_due_at": "2026-08-08T10:00:00Z",
            "shoot_date": "2026-08-01",
            "final_price": 1288.5,
        }

    @pytest.mark.asyncio
    async def test_send_personal_message_to_offline_user(self, manager):
        """异常场景：推送给离线用户不报错"""
        message = {"type": "notification", "content": "Hello"}
        await manager.send_personal_message(message, user_id=999)

    @pytest.mark.asyncio
    async def test_multiple_users_connect(self, manager, mock_websocket):
        """正常场景：多用户同时在线"""
        ws1 = AsyncMock()
        ws1.accept = AsyncMock()
        ws2 = AsyncMock()
        ws2.accept = AsyncMock()

        await manager.connect(user_id=1, websocket=ws1)
        await manager.connect(user_id=2, websocket=ws2)

        assert manager.is_online(1) is True
        assert manager.is_online(2) is True

        manager.disconnect(user_id=1)
        assert manager.is_online(1) is False
        assert manager.is_online(2) is True

    @pytest.mark.asyncio
    async def test_reconnect_overwrites(self, manager, mock_websocket):
        """边界条件：重复连接覆盖旧连接"""
        ws_old = AsyncMock()
        ws_old.accept = AsyncMock()
        ws_new = AsyncMock()
        ws_new.accept = AsyncMock()

        await manager.connect(user_id=1, websocket=ws_old)
        await manager.connect(user_id=1, websocket=ws_new)

        msg = {"type": "test"}
        await manager.send_personal_message(msg, user_id=1)
        ws_new.send_text.assert_awaited_once()
        ws_old.send_text.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_active_connections_initial_empty(self, manager):
        """边界条件：初始化时无连接"""
        assert len(manager.active_connections) == 0

    @pytest.mark.asyncio
    async def test_disconnect_clears_all(self, manager, mock_websocket):
        """正常场景：全部断开后列表为空"""
        await manager.connect(user_id=1, websocket=mock_websocket)
        manager.disconnect(user_id=1)
        assert len(manager.active_connections) == 0
