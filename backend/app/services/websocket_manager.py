"""WebSocket connection manager for real-time review updates."""
import json
import logging
from typing import Dict, Set
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manages WebSocket connections per session."""

    def __init__(self):
        self.connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, session_id: str, websocket: WebSocket):
        await websocket.accept()
        if session_id not in self.connections:
            self.connections[session_id] = set()
        self.connections[session_id].add(websocket)
        logger.info(f"WebSocket connected: session={session_id}, total={len(self.connections[session_id])}")

    def disconnect(self, session_id: str, websocket: WebSocket):
        if session_id in self.connections:
            self.connections[session_id].discard(websocket)
            if not self.connections[session_id]:
                del self.connections[session_id]
        logger.info(f"WebSocket disconnected: session={session_id}")

    async def send_message(self, session_id: str, message_type: str, payload: dict):
        """Send a message to all connected clients for a session."""
        if session_id not in self.connections:
            return
        message = {
            "type": message_type,
            "payload": payload,
            "timestamp": __import__("datetime").datetime.now().isoformat(),
        }
        dead = set()
        for ws in self.connections[session_id]:
            try:
                await ws.send_text(json.dumps(message))
            except Exception:
                dead.add(ws)
        for ws in dead:
            self.disconnect(session_id, ws)

    async def broadcast_issue(self, session_id: str, issue: dict):
        await self.send_message(session_id, "ISSUE_CREATED", issue)

    async def broadcast_agent_status(self, session_id: str, agent: str, status: str, issue_count: int):
        await self.send_message(session_id, "AGENT_STATUS_CHANGED", {
            "agent": agent, "status": status, "issue_count": issue_count,
        })

    async def broadcast_follow_up(self, session_id: str, follow_up: dict):
        await self.send_message(session_id, "FOLLOW_UP_CREATED", follow_up)

    async def broadcast_session_completed(self, session_id: str, issue_count: dict):
        await self.send_message(session_id, "SESSION_COMPLETED", {
            "session_id": session_id, "issue_count": issue_count,
        })

    async def broadcast_session_timeout(self, session_id: str, partial_issue_count: int):
        await self.send_message(session_id, "SESSION_TIMEOUT", {
            "session_id": session_id, "partial_issue_count": partial_issue_count,
        })

    async def broadcast_progress(self, session_id: str, agent: str, progress: float):
        await self.send_message(session_id, "PROGRESS_UPDATE", {
            "agent": agent, "progress": progress,
        })

    async def handle_follow_up_answer(self, session_id: str, follow_up_id: str, action: str, answer: str = None):
        """Handle a follow-up answer from the client via WebSocket."""
        return {
            "follow_up_id": follow_up_id,
            "status": "ANSWERED" if action == "ANSWER" else "SKIPPED",
            "agent_continuing": action == "ANSWER",
            "remaining_follow_ups": 0,
        }


ws_manager = WebSocketManager()
