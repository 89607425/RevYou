"""WebSocket endpoints for real-time review updates."""
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import decode_token
from app.services.websocket_manager import ws_manager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/sessions/{session_id}")
async def session_websocket(
    websocket: WebSocket,
    session_id: str,
    token: str = Query(...),
):
    """WebSocket endpoint for real-time session updates."""
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
    except Exception:
        await websocket.close(code=4001, reason="Invalid token")
        return

    await ws_manager.connect(session_id, websocket)

    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                if message.get("type") == "FOLLOW_UP_ANSWER":
                    payload = message.get("payload", {})
                    result = await ws_manager.handle_follow_up_answer(
                        session_id=session_id,
                        follow_up_id=payload.get("follow_up_id", ""),
                        action=payload.get("action", "SKIP"),
                        answer=payload.get("answer"),
                    )
                    await websocket.send_text(json.dumps({
                        "type": "FOLLOW_UP_ANSWERED",
                        "payload": result,
                    }))
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "type": "ERROR",
                    "payload": {"message": "Invalid JSON"},
                }))
    except WebSocketDisconnect:
        ws_manager.disconnect(session_id, websocket)
