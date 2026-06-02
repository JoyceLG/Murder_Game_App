"""WebSocket implementation of the RealtimeNotifier port (replaces Firestore watchDoc/Collection).

Lives in the api ring because it speaks FastAPI's WebSocket and the API DTO; the application only
ever sees the inward `RealtimeNotifier` port. Connections are in-process: the app runs a
single uvicorn worker. A multi-worker deployment would need a pub/sub backplane (e.g. Redis).
"""

from __future__ import annotations

from collections import defaultdict

from fastapi import WebSocket

from src.api.mappers import to_game_out
from src.domain.models import Game
from src.ports.clock import Clock
from src.ports.repository import GameRepository


class WebSocketNotifier:
    def __init__(self, repo: GameRepository, clock: Clock) -> None:
        self._rooms: dict[str, set[WebSocket]] = defaultdict(set)
        self._repo = repo
        self._clock = clock

    async def connect(self, code: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._rooms[code].add(websocket)
        game = await self._repo.get(code)
        if game is not None:
            await websocket.send_json(to_game_out(game, self._clock.now_ms()).model_dump())

    def disconnect(self, code: str, websocket: WebSocket) -> None:
        self._rooms[code].discard(websocket)

    async def publish(self, game: Game) -> None:
        payload = to_game_out(game, self._clock.now_ms()).model_dump()
        for websocket in list(self._rooms.get(game.code, set())):
            try:
                await websocket.send_json(payload)
            except Exception:  # noqa: BLE001 - drop a socket that failed mid-broadcast
                self._rooms[game.code].discard(websocket)
