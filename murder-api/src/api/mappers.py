"""Domain -> DTO mapping. The single anti-corruption boundary; reused by REST and WebSocket."""

from __future__ import annotations

from src.api.schemas import ClaimOut, GameOut, PlayerOut, PooledMissionOut
from src.domain.models import Claim, Game, Player, PooledMission


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


def pooled_mission_out(mission: PooledMission) -> PooledMissionOut:
    return PooledMissionOut(id=mission.id, text=mission.text, by=mission.by)


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
        max_players=game.max_players,
        max_score=game.max_score,
        mission_mode=str(game.mission_mode),
        players=[player_out(p) for p in game.players.values()],
        claims=[claim_out(c) for c in game.claims.values()],
        mission_pool=[pooled_mission_out(m) for m in game.mission_pool],
        ranking=[player_out(p) for p in game.ranking()],
    )
