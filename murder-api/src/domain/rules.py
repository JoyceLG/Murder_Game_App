"""Pure game rules ported from legacy-js/src/game.js.

Each function mutates the `Game` aggregate in place and takes an injected `Picker` for any
randomness, so the rules are deterministic under test. No I/O, no framework imports.
"""

from __future__ import annotations

from src.domain.errors import (
    ClaimAlreadyResolved,
    ClaimAwaitingAck,
    ClaimNotFound,
    ClaimNotResolved,
    InvalidGameConfig,
    MustAnswerClaimFirst,
    NoTargetAssigned,
    PlayerNotFound,
    SwapNotAllowed,
)
from src.domain.missions import MISSION_KEYS, is_catalogue_key
from src.domain.models import Claim, ClaimStatus, Game, GameStatus, MissionMode, Player
from src.domain.randomness import Picker, pick_mission_excluding


def configure_game(
    game: Game, max_players: int, max_score: int | None, mission_mode: MissionMode
) -> None:
    """The host's lobby settings. The player cap cannot go below the players already in the
    lobby; a score goal, when set, is at least 1 point (0 or fewer would end the game at once)."""
    if max_score is not None and max_score < 1:
        raise InvalidGameConfig()
    if max_players < len(game.players):
        raise InvalidGameConfig()
    game.max_players = max_players
    game.max_score = max_score
    game.mission_mode = mission_mode


def _too_few_players(game: Game) -> bool:
    return len(game.players) < 2  # nobody left to hunt


def should_end(game: Game, now_ms: int) -> bool:
    """A running game is over when its clock ran out, a player reached the score goal, or
    fewer than two players are left (nobody to hunt)."""
    return game.status is GameStatus.RUNNING and (
        game.is_time_up(now_ms) or game.score_cap_reached() or _too_few_players(game)
    )


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


def _has_pending_claim(game: Game, player_id: str) -> bool:
    claim = game.claims.get(player_id)
    return claim is not None and claim.status is ClaimStatus.PENDING


def _retarget_after_kill(game: Game, attacker: Player, picker: Picker) -> None:
    """Give a scoring attacker a new target while keeping "hunted exactly once" when possible.

    Preferred: swap targets with another hunter P (attacker takes P's target, P takes the victim).
    The ring stays a permutation, so nobody ends up hunted twice or not at all. P must not have a
    *pending* claim (its target would change under the claim; a resolved claim waiting for P's
    ack is fine, see `advance_after_resolution`) and the swap must not make anyone hunt
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
        and not _has_pending_claim(game, p.id)
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


def open_claim(game: Game, attacker_id: str, ts: int) -> Claim:
    """The attacker says they completed their mission on their target; the target must answer.

    One active claim per attacker (a new one replaces a pending one). Not allowed while the
    attacker still has a result to acknowledge, nor while a claim *on* them awaits their answer
    (that request has priority) — those checks come first, whatever else holds.
    """
    attacker = game.players.get(attacker_id)
    if attacker is None:
        raise PlayerNotFound(attacker_id)
    if awaiting_ack(game, attacker_id):  # see the last result first
        raise ClaimAwaitingAck()
    if has_incoming_claim(game, attacker_id):  # a claim on them is answered first
        raise MustAnswerClaimFirst()
    if not attacker.target_id:
        raise NoTargetAssigned()
    claim = Claim(
        atk=attacker_id,
        atk_name=attacker.name,
        target=attacker.target_id,
        mission=attacker.mission,
        status=ClaimStatus.PENDING,
        ts=ts,
    )
    game.claims[attacker_id] = claim
    return claim


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

    # If the victim left meanwhile, the attacker was already given someone else to hunt
    # (`remove_player`): that player is not the one eliminated, so keep them.
    if claim.status is ClaimStatus.OK and attacker.target_id == claim.target:
        _retarget_after_kill(game, attacker, picker)
    attacker.mission = pick_mission_excluding(picker, attacker.mission, effective_missions(game))
    del game.claims[attacker_id]


def finish(game: Game) -> None:
    """End the game. Every claim is settled as is (scores already counted, nothing to deal):
    the automatic acknowledgement, so no player is left waiting on a result. Every way a game
    ends (clock, score cap, host) goes through here."""
    game.status = GameStatus.ENDED
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


def has_incoming_claim(game: Game, player_id: str) -> bool:
    """True while someone's claim on this player waits for their answer."""
    return any(
        c.target == player_id and c.status is ClaimStatus.PENDING for c in game.claims.values()
    )


def swap_cost(player: Player) -> int | None:
    """Points a mission swap costs this player now: 1 if they have points, 0 for their one free
    swap at 0 points, None when they cannot swap (no point and free swap used). Scores never
    go below 0."""
    if player.score > 0:
        return 1
    return None if player.free_swap_used else 0


def swap_mission(game: Game, player_id: str, picker: Picker) -> None:
    """Reroll the player's mission (JS: swapMission) for its cost (see `swap_cost`)."""
    player = game.players.get(player_id)
    if player is None:
        raise PlayerNotFound(player_id)
    if awaiting_ack(game, player_id):  # acknowledging deals the next mission anyway
        raise ClaimAwaitingAck()
    if has_incoming_claim(game, player_id):  # answering comes first
        raise MustAnswerClaimFirst()
    cost = swap_cost(player)
    if cost is None:
        raise SwapNotAllowed()
    player.mission = pick_mission_excluding(picker, player.mission, effective_missions(game))
    if cost:
        player.score -= cost
    else:
        player.free_swap_used = True


def remove_player(game: Game, player_id: str, picker: Picker) -> None:
    """A player leaves a game that is not over.

    Their own claim goes. A *pending* claim on them can never be answered, so it goes too; a
    *resolved* one is the attacker's result to acknowledge and stays. Their hunters get a new
    target (`reassign_targets_away_from`), and the host role passes on if they had it. A running
    game left with a single player ends right away.
    """
    leaver = game.players.pop(player_id, None)
    game.claims.pop(player_id, None)
    for attacker_id, claim in list(game.claims.items()):
        if claim.target == player_id and claim.status is ClaimStatus.PENDING:
            del game.claims[attacker_id]
    if not game.players:
        return
    reassign_targets_away_from(game, player_id, picker, leaver.target_id if leaver else None)
    if game.host_id == player_id:
        game.host_id = next(iter(game.players))
    if game.status is GameStatus.RUNNING and _too_few_players(game):
        finish(game)  # the last player standing ends it (same rule as `should_end`)
