"""WebSocket endpoint: push the full game state on connect and on every change (server-driven)."""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


@router.websocket("/games/{code}/live")
async def live(websocket: WebSocket, code: str) -> None:
    notifier = websocket.app.state.notifier
    await notifier.connect(code, websocket)
    try:
        while True:
            await websocket.receive_text()  # keepalive; the channel is server-push only
    except WebSocketDisconnect:
        notifier.disconnect(code, websocket)
