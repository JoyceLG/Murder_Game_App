"""Shared helpers for use cases: aggregate loading and lazy end-of-game settlement."""

from __future__ import annotations

from src.domain.errors import GameNotFound
from src.domain.models import Game, GameStatus
from src.ports.clock import Clock
from src.ports.repository import GameRepository


async def get_game_or_404(repo: GameRepository, code: str) -> Game:
    game = await repo.get(code)
    if game is None:
        raise GameNotFound(code)
    return game


def settle_end(game: Game, clock: Clock) -> bool:
    """Flip a running-but-expired game to ENDED. Returns True if the status changed.

    This is the lazy auto-end that replaces the JS per-second client tick: the truth is
    computed whenever the game is read or mutated, not by a background scheduler.
    """
    if game.status is GameStatus.RUNNING and game.is_time_up(clock.now_ms()):
        game.status = GameStatus.ENDED
        return True
    return False
