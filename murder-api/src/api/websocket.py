"""WebSocket endpoint: push the caller's view on connect and on every change (server-driven).

Protocol:
  1. the client connects to /games/{code}/live and sends {"player_id": ..., "token": ...}
     as its first message (browsers cannot set headers on a WebSocket, and a token in the URL
     would end up in proxy access logs);
  2. the server answers with the current view, then pushes a new view after every change;
  3. the client may send "ping" at any time; the server answers "pong" (keeps proxies from
     closing an idle connection).
Failures close the socket with an application code (see ws_notifier): 4401 bad credentials,
4404 unknown game, 4429 rate limited. The client must not reconnect after those.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from src.api.dependencies import authenticate_uc, get_game_uc
from src.api.rate_limit import client_key
from src.api.ws_notifier import (
    CLOSE_GAME_NOT_FOUND,
    CLOSE_NOT_AUTHENTICATED,
    CLOSE_RATE_LIMITED,
)
from src.application.authenticate_player import AuthenticatePlayer
from src.application.get_game import GetGame
from src.domain.errors import GameNotFound, NotAuthenticated

router = APIRouter()

AUTH_TIMEOUT_SEC = 10.0


@router.websocket("/games/{code}/live")
async def live(
    websocket: WebSocket,
    code: str,
    auth: AuthenticatePlayer = Depends(authenticate_uc),
    get_game: GetGame = Depends(get_game_uc),
) -> None:
    state = websocket.app.state
    notifier = state.notifier
    key = client_key(websocket)
    await websocket.accept()

    if (state.rate_limiter is not None and not state.rate_limiter.allow(key)) or (
        state.miss_limiter is not None and state.miss_limiter.exhausted(key)
    ):
        await websocket.close(code=CLOSE_RATE_LIMITED)
        return

    try:
        hello = await asyncio.wait_for(websocket.receive_json(), AUTH_TIMEOUT_SEC)
        viewer = await auth.execute(code, str(hello["player_id"]), str(hello["token"]))
    except WebSocketDisconnect:
        return
    except GameNotFound:
        if state.miss_limiter is not None:
            state.miss_limiter.hit(key)
        await websocket.close(code=CLOSE_GAME_NOT_FOUND)
        return
    except (NotAuthenticated, TimeoutError, ValueError, KeyError, TypeError):
        await websocket.close(code=CLOSE_NOT_AUTHENTICATED)
        return

    # Subscribe before taking the snapshot: a change racing with the handshake is then pushed
    # after (or before) the snapshot, and the client keeps whichever has the higher version.
    notifier.subscribe(code, websocket, viewer)
    try:
        try:
            async with state.locks.hold(code):
                game = await get_game.execute(code)  # settles (and broadcasts) a timed-out game
        except GameNotFound:
            await websocket.close(code=CLOSE_GAME_NOT_FOUND)
            return
        await notifier.send_view(websocket, game, viewer)
        while True:
            if await websocket.receive_text() == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        notifier.unsubscribe(code, websocket)
