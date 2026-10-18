"""Domain -> DTO mapping. The single anti-corruption boundary; reused by REST and WebSocket.

A game is never serialized as a whole: each player gets their own view. Everybody sees the
roster, the scores and the rules; only the viewer sees their own mission and target, and only
the claims they made or must answer. Broadcasting everyone's target would hand the game away.
"""

from __future__ import annotations

from src.api.schemas import ClaimOut, GameOut, MeOut, PlayerOut, PooledMissionOut
from src.domain.models import Claim, Game, Player, PooledMission


def player_out(player: Player) -> PlayerOut:
    return PlayerOut(id=player.id, name=player.name, score=player.score)


def me_out(player: Player) -> MeOut:
    return MeOut(
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


def to_player_view(game: Game, viewer_id: str | None, now_ms: int) -> GameOut:
    """`game` as seen by `viewer_id` (None or a non-member = anonymous: public data only)."""
    viewer = game.players.get(viewer_id) if viewer_id else None
    remaining = max(0, (game.end_at - now_ms) // 1000) if game.end_at else 0
    claims = [c for c in game.claims.values() if viewer.id in (c.atk, c.target)] if viewer else []
    return GameOut(
        code=game.code,
        host_id=game.host_id,
        status=game.status,
        duration_sec=game.duration_sec,
        start_at=game.start_at,
        end_at=game.end_at,
        remaining_sec=remaining,
        server_now=now_ms,
        version=game.version,
        max_players=game.max_players,
        max_score=game.max_score,
        mission_mode=str(game.mission_mode),
        players=[player_out(p) for p in game.players.values()],
        me=me_out(viewer) if viewer else None,
        claims=[claim_out(c) for c in claims],
        mission_pool=[pooled_mission_out(m) for m in game.mission_pool],
        ranking=[player_out(p) for p in game.ranking()],
    )
