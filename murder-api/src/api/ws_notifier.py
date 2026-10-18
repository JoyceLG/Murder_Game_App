"""WebSocket implementation of the RealtimeNotifier port (replaces Firestore watchDoc/Collection).

Lives in the api ring because it speaks FastAPI's WebSocket and the API DTO; the application only
ever sees the inward `RealtimeNotifier` port. Connections are in-process: the app runs a
single uvicorn worker. A multi-worker deployment would need a pub/sub backplane (e.g. Redis).

Each socket belongs to an authenticated player and receives that player's own view of the game
(see mappers.to_player_view), never the whole game.
"""

from __future__ import annotations

import asyncio
import contextlib

from fastapi import WebSocket

from src.api.mappers import to_player_view
from src.domain.models import Game
from src.ports.clock import Clock

# Application close codes (4000-4999), understood by the front's Realtime service.
CLOSE_NOT_AUTHENTICATED = 4401
CLOSE_NOT_A_PLAYER = 4403  # the viewer left / was removed from the game
CLOSE_GAME_NOT_FOUND = 4404
CLOSE_RATE_LIMITED = 4429

SEND_TIMEOUT_SEC = 5.0  # a client that cannot take a message in time is dropped


class WebSocketNotifier:
    def __init__(self, clock: Clock) -> None:
        self._rooms: dict[str, dict[WebSocket, str]] = {}  # code -> {socket: viewer id}
        self._clock = clock

    def subscribe(self, code: str, websocket: WebSocket, viewer_id: str) -> None:
        self._rooms.setdefault(code, {})[websocket] = viewer_id

    def unsubscribe(self, code: str, websocket: WebSocket) -> None:
        room = self._rooms.get(code)
        if room is None:
            return
        room.pop(websocket, None)
        if not room:
            del self._rooms[code]

    async def send_view(self, websocket: WebSocket, game: Game, viewer_id: str) -> None:
        view = to_player_view(game, viewer_id, self._clock.now_ms())
        await asyncio.wait_for(websocket.send_json(view.model_dump()), SEND_TIMEOUT_SEC)

    async def publish(self, game: Game) -> None:
        room = dict(self._rooms.get(game.code, {}))
        # Concurrently, so one slow client does not hold up everyone else.
        await asyncio.gather(*(self._deliver(game, ws, viewer) for ws, viewer in room.items()))

    async def _deliver(self, game: Game, websocket: WebSocket, viewer_id: str) -> None:
        if viewer_id not in game.players:
            await self._close_quietly(websocket, CLOSE_NOT_A_PLAYER)
            self.unsubscribe(game.code, websocket)
            return
        try:
            await self.send_view(websocket, game, viewer_id)
        except Exception:  # noqa: BLE001 - drop a socket that failed or stalled mid-broadcast
            self.unsubscribe(game.code, websocket)

    async def close(self, code: str) -> None:
        room = self._rooms.pop(code, {})
        await asyncio.gather(*(self._close_quietly(ws, CLOSE_GAME_NOT_FOUND) for ws in room))

    @staticmethod
    async def _close_quietly(websocket: WebSocket, code: int) -> None:
        with contextlib.suppress(Exception):  # already closed by the peer
            await websocket.close(code=code)

    def watched_codes(self) -> list[str]:
        return list(self._rooms)
