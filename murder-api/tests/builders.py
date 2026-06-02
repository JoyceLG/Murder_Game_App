"""Helpers to build domain aggregates in tests."""

from __future__ import annotations

from collections.abc import Sequence

from src.domain.models import Claim, Game, GameStatus, Player
from src.domain.randomness import Picker
from src.domain.rules import assign_targets


def make_game(
    player_ids: Sequence[str],
    *,
    code: str = "ABCD",
    host: str | None = None,
    status: GameStatus = GameStatus.LOBBY,
) -> Game:
    host_id = host if host is not None else (player_ids[0] if player_ids else "host")
    game = Game(code=code, host_id=host_id, status=status)
    for pid in player_ids:
        game.players[pid] = Player(id=pid, name=pid.capitalize())
    return game


def running_game(player_ids: Sequence[str], picker: Picker, *, code: str = "ABCD") -> Game:
    game = make_game(player_ids, code=code)
    assign_targets(game, picker)
    game.status = GameStatus.RUNNING
    return game


def add_claim(game: Game, attacker_id: str) -> Claim:
    atk = game.players[attacker_id]
    claim = Claim(
        atk=attacker_id, atk_name=atk.name, target=atk.target_id or "", mission=atk.mission
    )
    game.claims[attacker_id] = claim
    return claim
