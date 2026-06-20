"""Pure game rules ported from legacy-js/src/game.js.

Each function mutates the `Game` aggregate in place and takes an injected `Picker` for any
randomness, so the rules are deterministic under test. No I/O, no framework imports.
"""

from __future__ import annotations

from src.domain.errors import PlayerNotFound
from src.domain.missions import MISSIONS
from src.domain.models import Game, MissionMode
from src.domain.randomness import Picker, pick_mission_excluding


def clamp_duration_min(minutes: int) -> int:
    """Clamp a requested duration to [1, 240] minutes (JS: max(1, min(240, durationMin | 0)))."""
    return max(1, min(240, int(minutes)))


def effective_missions(game: Game) -> tuple[str, ...]:
    """The mission texts a game actually draws from, honouring its mission_mode.

    REPLACE (with a non-empty pool) -> the custom pool only.
    AUGMENT (default)               -> the default catalogue plus the custom pool.
    Duplicates are removed, order preserved (catalogue first).
    """
    pool = [m.text for m in game.mission_pool]
    base = pool if (game.mission_mode is MissionMode.REPLACE and pool) else [*MISSIONS, *pool]
    seen: set[str] = set()
    out: list[str] = []
    for mission in base:
        if mission not in seen:
            seen.add(mission)
            out.append(mission)
    return tuple(out)


def assign_targets(game: Game, picker: Picker) -> None:
    """Give every player a target (never themselves) and a random mission.

    Mirrors game.js start(): an independent per-player pick, not a derangement cycle.
    With two players this yields the only possibility (A->B, B->A). Assumes >= 2 players;
    the StartGame use case enforces that guard.
    """
    ids = list(game.players)
    missions = effective_missions(game)
    for player in game.players.values():
        candidates = [i for i in ids if i != player.id]
        player.target_id = picker.choice(candidates)
        player.mission = picker.choice(missions)


def resolve_claim(game: Game, attacker_id: str, confirmed: bool, picker: Picker) -> None:
    """Authoritatively resolve an attacker's elimination claim.

    confirmed -> +1 score, a new target (preferring one != current, fallback any != self),
                 and a new mission.
    refused   -> a new mission only; the target is unchanged.
    The claim is consumed (removed) in both cases.

    NB: in the JS version this ran in the *attacker's* browser ("client-side scoring trust").
    Here it is invoked by the ConfirmClaim use case, triggered by the target — server-side.
    """
    attacker = game.players.get(attacker_id)
    if attacker is None:
        raise PlayerNotFound(attacker_id)

    missions = effective_missions(game)
    if confirmed:
        attacker.score += 1
        others = [i for i in game.players if i != attacker_id]
        pool = [i for i in others if i != attacker.target_id] or others
        if pool:
            attacker.target_id = picker.choice(pool)
        attacker.mission = pick_mission_excluding(picker, attacker.mission, missions)
    else:
        attacker.mission = pick_mission_excluding(picker, attacker.mission, missions)

    game.claims.pop(attacker_id, None)


def reassign_targets_away_from(game: Game, removed_id: str, picker: Picker) -> None:
    """After a player leaves mid-game, give a fresh target to anyone who was hunting them.

    Without this, a hunter keeps a `target_id` pointing at a player who is gone — they could
    never get a valid confirmation again. If the leaver was the only other player (one remains),
    that lone player's target is cleared.
    """
    for player in game.players.values():
        if player.target_id == removed_id:
            candidates = [i for i in game.players if i != player.id]
            player.target_id = picker.choice(candidates) if candidates else None


def swap_mission(game: Game, player_id: str, picker: Picker) -> None:
    """Reroll the mission for a -1 score penalty (JS: swapMission). Score may go negative."""
    player = game.players.get(player_id)
    if player is None:
        raise PlayerNotFound(player_id)
    player.mission = pick_mission_excluding(picker, player.mission, effective_missions(game))
    player.score -= 1
