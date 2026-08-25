"""WebSocket 连接管理器：维护在线用户连接并推送消息。"""

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Dict

from fastapi import WebSocket

from backend.app.core.timezone import isoformat_utc


class DecimalEncoder(json.JSONEncoder):
    """JSON 编码器：支持 Decimal、datetime 与 date 类型。"""

    def default(self, o):
        """将 Decimal 与日期时间对象序列化为可 JSON 表示的值。"""
        if isinstance(o, Decimal):
            return float(o)
        if isinstance(o, datetime):
            return isoformat_utc(o)
        if isinstance(o, date):
            return o.isoformat()
        return super().default(o)


class ConnectionManager:
    """WebSocket 连接管理器"""

    def __init__(self):
        """初始化连接管理器。"""
        # 存储在线用户：{ user_id: WebSocket }
        self.active_connections: Dict[int, WebSocket] = {}

    async def connect(self, user_id: int, websocket: WebSocket):
        """接受连接并注册"""
        await websocket.accept()
        self.active_connections[user_id] = websocket

    def disconnect(self, user_id: int):
        """移除连接"""
        self.active_connections.pop(user_id, None)

    async def send_personal_message(self, message: dict, user_id: int):
        """向指定用户推送消息"""
        websocket = self.active_connections.get(user_id)
        if websocket:
            text = json.dumps(message, separators=(",", ":"), ensure_ascii=False, cls=DecimalEncoder)
            await websocket.send_text(text)

    def is_online(self, user_id: int) -> bool:
        """判断用户是否在线。"""
        return user_id in self.active_connections


# 全局实例
manager = ConnectionManager()
