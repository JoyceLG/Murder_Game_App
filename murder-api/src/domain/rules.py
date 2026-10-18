"""Pure game rules ported from legacy-js/src/game.js.

Each function mutates the `Game` aggregate in place and takes an injected `Picker` for any
randomness, so the rules are deterministic under test. No I/O, no framework imports.
"""

from __future__ import annotations

from src.domain.errors import (
    ClaimAlreadyResolved,
    ClaimNotFound,
    ClaimNotResolved,
    PlayerNotFound,
)
from src.domain.missions import MISSION_KEYS, is_catalogue_key
from src.domain.models import ClaimStatus, Game, MissionMode, Player
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
    # A custom text shaped like a catalogue key would be translated by clients instead of shown
    # as typed. New ones are refused at input; this also covers pools stored before that rule.
    pool = [m.text for m in game.mission_pool if not is_catalogue_key(m.text)]
    base = pool if (game.mission_mode is MissionMode.REPLACE and pool) else [*MISSION_KEYS, *pool]
    seen: set[str] = set()
    out: list[str] = []
    for mission in base:
        if mission not in seen:
            seen.add(mission)
            out.append(mission)
    return tuple(out)


def _shuffled(ids: list[str], picker: Picker) -> list[str]:
    """A random permutation of `ids`, drawn one pick at a time (the Picker only offers choice)."""
    remaining = list(ids)
    order: list[str] = []
    while remaining:
        pick = picker.choice(remaining)
        remaining.remove(pick)
        order.append(pick)
    return order


def _hunt_counts(game: Game, candidates: list[str], ignore: str) -> dict[str, int]:
    """How many players (other than `ignore`) currently hunt each candidate."""
    return {
        cid: sum(1 for p in game.players.values() if p.id != ignore and p.target_id == cid)
        for cid in candidates
    }


def _least_hunted(game: Game, candidates: list[str], hunter_id: str, picker: Picker) -> str:
    """Pick among `candidates` one that the fewest other players are already hunting."""
    counts = _hunt_counts(game, candidates, ignore=hunter_id)
    fewest = min(counts.values())
    return picker.choice([cid for cid in candidates if counts[cid] == fewest])


def assign_targets(game: Game, picker: Picker) -> None:
    """Give every player a target and a random mission, as one random cycle.

    Players are shuffled into a ring and each hunts the next one, so everybody hunts exactly one
    player and is hunted by exactly one (a derangement: never yourself). With two players this
    yields the only possibility (A->B, B->A). Assumes >= 2 players; StartGame enforces that.
    """
    order = _shuffled(list(game.players), picker)
    missions = effective_missions(game)
    for index, player_id in enumerate(order):
        player = game.players[player_id]
        player.target_id = order[(index + 1) % len(order)]
        player.mission = picker.choice(missions)


def _retarget_after_kill(game: Game, attacker: Player, picker: Picker) -> None:
    """Give a scoring attacker a new target while keeping "hunted exactly once" when possible.

    Preferred: swap targets with another hunter P (attacker takes P's target, P takes the victim).
    The ring stays a permutation, so nobody ends up hunted twice or not at all. P must not have a
    pending claim (its target would change under it) and the swap must not make anyone hunt
    themselves. When no such swap exists (e.g. three players), fall back to the least-hunted
    player other than the victim; with two players the victim is the only choice.
    """
    victim = attacker.target_id
    partners = [
        p
        for p in game.players.values()
        if p.id not in (attacker.id, victim)
        and p.target_id is not None
        and p.target_id not in (attacker.id, victim)
        and p.id not in game.claims
    ]
    if partners and victim is not None:
        partner = picker.choice(partners)
        attacker.target_id, partner.target_id = partner.target_id, victim
        return

    others = [i for i in game.players if i != attacker.id]
    if not others:
        return
    pool = [i for i in others if i != victim] or others
    attacker.target_id = _least_hunted(game, pool, attacker.id, picker)


def mark_resolved(game: Game, attacker_id: str, confirmed: bool) -> None:
    """The target's answer: the claim becomes OK (+1 point, right away) or NO.

    Nothing else changes yet — no new target, no new mission. The claim stays until the attacker
    acknowledges the result (`advance_after_resolution`), so they see what happened first.
    The score rises at confirmation time, so a score cap can end the game immediately.

    NB: in the JS version scoring ran in the *attacker's* browser ("client-side scoring trust").
    Here it is invoked by the ConfirmClaim use case, triggered by the target — server-side.
    """
    attacker = game.players.get(attacker_id)
    if attacker is None:
        raise PlayerNotFound(attacker_id)
    claim = game.claims.get(attacker_id)
    if claim is None:
        raise ClaimNotFound(attacker_id)
    if claim.status is not ClaimStatus.PENDING:
        raise ClaimAlreadyResolved(attacker_id)

    claim.status = ClaimStatus.OK if confirmed else ClaimStatus.NO
    if confirmed:
        attacker.score += 1


def advance_after_resolution(game: Game, attacker_id: str, picker: Picker) -> None:
    """The attacker acknowledged the result: deal what comes next and consume the claim.

    OK -> a new target (see `_retarget_after_kill`: != current when possible, keeping everyone
          hunted exactly once when possible) and a new mission.
    NO -> a new mission only; the target is unchanged.
    """
    attacker = game.players.get(attacker_id)
    if attacker is None:
        raise PlayerNotFound(attacker_id)
    claim = game.claims.get(attacker_id)
    if claim is None:
        raise ClaimNotFound(attacker_id)
    if claim.status is ClaimStatus.PENDING:
        raise ClaimNotResolved(attacker_id)

    if claim.status is ClaimStatus.OK:
        _retarget_after_kill(game, attacker, picker)
    attacker.mission = pick_mission_excluding(picker, attacker.mission, effective_missions(game))
    del game.claims[attacker_id]


def close_claims(game: Game) -> None:
    """The game is over: every claim is settled as is (scores already counted, nothing to deal).

    This is the automatic acknowledgement at the end, so no player is left waiting on a claim.
    """
    game.claims.clear()


def awaiting_ack(game: Game, player_id: str) -> bool:
    """True while the player has a resolved claim they have not acknowledged yet."""
    claim = game.claims.get(player_id)
    return claim is not None and claim.status is not ClaimStatus.PENDING


def reassign_targets_away_from(
    game: Game, removed_id: str, picker: Picker, inherited_target: str | None = None
) -> None:
    """After a player leaves mid-game, give a fresh target to anyone who was hunting them.

    Without this, a hunter keeps a `target_id` pointing at a player who is gone — they could
    never get a valid confirmation again. The leaver's own target (`inherited_target`) goes to
    their hunter, which closes the ring around the gap. Any other hunter (or one for whom that
    would mean hunting themselves) gets the least-hunted remaining player. If the leaver was the
    only other player (one remains), that lone player's target is cleared.
    """
    heir = inherited_target if inherited_target in game.players else None
    for player in game.players.values():
        if player.target_id != removed_id:
            continue
        if heir is not None and heir != player.id:
            player.target_id, heir = heir, None
            continue
        candidates = [i for i in game.players if i != player.id]
        player.target_id = (
            _least_hunted(game, candidates, player.id, picker) if candidates else None
        )


def swap_mission(game: Game, player_id: str, picker: Picker) -> None:
    """Reroll the mission for a -1 score penalty (JS: swapMission). Score may go negative."""
    player = game.players.get(player_id)
    if player is None:
        raise PlayerNotFound(player_id)
    player.mission = pick_mission_excluding(picker, player.mission, effective_missions(game))
    player.score -= 1
