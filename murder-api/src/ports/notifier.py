"""Driven port: real-time broadcast of game state. The WebSocket adapter implements it.

Async because the production adapter sends over the network. The domain/application speak only
to this port and never import FastAPI/WebSocket.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.domain.models import Game


@runtime_checkable
class RealtimeNotifier(Protocol):
    async def publish(self, game: Game) -> None:
        """Push the full current state to everyone watching `game.code`."""
        ...
