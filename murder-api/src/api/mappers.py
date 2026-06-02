"""Domain -> DTO mapping. The single anti-corruption boundary; reused by REST and WebSocket."""

from __future__ import annotations

from src.api.schemas import ClaimOut, GameOut, PlayerOut
from src.domain.models import Claim, Game, Player


def player_out(player: Player) -> PlayerOut:
    return PlayerOut(
        id=player.id,
        name=player.name,
        score=player.score,
        mission=player.mission,
        target_id=player.target_id,
    )


def claim_out(claim: Claim) -> ClaimOut:
    return ClaimOut(
        atk=claim.atk,
        atk_name=claim.atk_name,
        target=claim.target,
        mission=claim.mission,
        status=claim.status,
    )


def to_game_out(game: Game, now_ms: int) -> GameOut:
    remaining = max(0, (game.end_at - now_ms) // 1000) if game.end_at else 0
    return GameOut(
        code=game.code,
        host_id=game.host_id,
        status=game.status,
        duration_sec=game.duration_sec,
        start_at=game.start_at,
        end_at=game.end_at,
        remaining_sec=remaining,
        players=[player_out(p) for p in game.players.values()],
        claims=[claim_out(c) for c in game.claims.values()],
        ranking=[player_out(p) for p in game.ranking()],
    )
