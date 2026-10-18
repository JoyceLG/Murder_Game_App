"""Shared helpers for use cases: aggregate loading, lazy end-of-game settlement, secret digests."""

from __future__ import annotations

import hashlib

from src.domain.errors import GameNotFound
from src.domain.models import Game, GameStatus
from src.domain.rules import finish
from src.ports.clock import Clock
from src.ports.repository import GameRepository


async def get_game_or_404(repo: GameRepository, code: str) -> Game:
    game = await repo.get(code)
    if game is None:
        raise GameNotFound(code)
    return game


def settle_end(game: Game, clock: Clock) -> bool:
    """Flip a finished running game to ENDED. Returns True if the status changed.

    A running game ends when its clock reaches end_at **or** a player reaches the score cap.
    This is the lazy auto-end that replaces the JS per-second client tick: the truth is
    computed whenever the game is read or mutated, not by a background scheduler.
    Ending also settles every claim (automatic acknowledgement: nobody is left waiting).
    """
    if game.status is GameStatus.RUNNING and (
        game.is_time_up(clock.now_ms()) or game.score_cap_reached()
    ):
        finish(game)
        return True
    return False


def digest_secret(secret: str) -> str:
    """One-way digest of a session secret; only this is stored, never the secret itself."""
    return hashlib.sha256(secret.encode()).hexdigest()
