"""
WebSocket 实时通信路由

提供基于 WebSocket 的即时消息推送服务，支持 token 鉴权和心跳保活。
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from jose import JWTError, jwt

from backend.app.core.config import settings
from backend.app.services.ws_manager import manager

router = APIRouter(tags=["实时通信"])


async def get_user_id_from_token(websocket: WebSocket) -> int | None:
    """从 WebSocket 的 query 参数中解析 token，返回 user_id"""
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="缺少 token")
        return None
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = int(payload.get("sub"))
        return user_id
    except (JWTError, ValueError, TypeError):
        await websocket.close(code=4002, reason="无效 token")
        return None


@router.websocket(
    "/ws",
)
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 连接端点

    连接时需携带 token 参数进行身份认证：
        ws://host/ws?token=<JWT_TOKEN>

    支持心跳检测 - 客户端发送 {"type": "ping"}，服务端回复 {"type": "pong"}。
    """
    user_id = await get_user_id_from_token(websocket)
    if user_id is None:
        return

    await manager.connect(user_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        manager.disconnect(user_id)
