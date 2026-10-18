import random
from collections import Counter

import pytest

from src.domain.errors import (
    ClaimAlreadyResolved,
    ClaimAwaitingAck,
    ClaimNotFound,
    ClaimNotResolved,
    MustAnswerClaimFirst,
    NoTargetAssigned,
    PlayerNotFound,
    SwapNotAllowed,
)
from src.domain.missions import MISSION_KEYS
from src.domain.models import ClaimStatus, GameStatus
from src.domain.randomness import RandomPicker
from src.domain.rules import (
    advance_after_resolution,
    assign_targets,
    awaiting_ack,
    clamp_duration_min,
    finish,
    has_incoming_claim,
    mark_resolved,
    open_claim,
    reassign_targets_away_from,
    remove_player,
    swap_cost,
    swap_mission,
)
from tests.builders import add_claim, make_game, running_game
from tests.doubles import FirstPicker, SequencePicker


def resolve_claim(game, attacker_id, confirmed, picker):
    """The full cycle: the target answers, then the attacker acknowledges."""
    mark_resolved(game, attacker_id, confirmed)
    advance_after_resolution(game, attacker_id, picker)


def _hunt_counts(game):
    return Counter(p.target_id for p in game.players.values())


# --- assign_targets --------------------------------------------------------------------


def test_assign_targets_gives_each_player_a_target_different_from_self():
    game = make_game(["alice", "bob", "carol"])
    assign_targets(game, FirstPicker())
    for player in game.players.values():
        assert player.target_id is not None
        assert player.target_id != player.id


def test_assign_targets_assigns_a_mission_from_catalogue_to_everyone():
    game = make_game(["alice", "bob", "carol"])
    assign_targets(game, FirstPicker())
    for player in game.players.values():
        assert player.mission in MISSION_KEYS


def test_assign_targets_two_players_target_each_other():
    game = make_game(["alice", "bob"])
    assign_targets(game, FirstPicker())
    assert game.players["alice"].target_id == "bob"
    assert game.players["bob"].target_id == "alice"


def test_assign_targets_is_deterministic_with_injected_picker():
    game = make_game(["alice", "bob", "carol"])
    # scripted as the shuffled ring order (one pick per remaining player), then the missions
    picker = SequencePicker(
        "carol", "alice", "bob", MISSION_KEYS[0], MISSION_KEYS[1], MISSION_KEYS[2]
    )
    assign_targets(game, picker)
    # ring carol -> alice -> bob -> carol
    assert (game.players["carol"].target_id, game.players["carol"].mission) == (
        "alice",
        MISSION_KEYS[0],
    )
    assert (game.players["alice"].target_id, game.players["alice"].mission) == (
        "bob",
        MISSION_KEYS[1],
    )
    assert (game.players["bob"].target_id, game.players["bob"].mission) == (
        "carol",
        MISSION_KEYS[2],
    )


@pytest.mark.parametrize("seed", range(20))
def test_assign_targets_forms_a_single_cycle_everyone_hunted_exactly_once(seed):
    game = make_game([f"p{i}" for i in range(7)])
    assign_targets(game, RandomPicker(random.Random(seed)))

    hunted = Counter(p.target_id for p in game.players.values())
    assert set(hunted) == set(game.players)
    assert set(hunted.values()) == {1}
    # following targets from anyone visits all players before coming back: one ring, no sub-loops
    seen, current = [], "p0"
    while current not in seen:
        seen.append(current)
        current = game.players[current].target_id
    assert len(seen) == len(game.players)


# --- resolve_claim (confirmed) ---------------------------------------------------------


def test_resolve_claim_confirmed_increments_score():
    game = running_game(["alice", "bob", "carol"], FirstPicker())
    add_claim(game, "alice")
    resolve_claim(game, "alice", confirmed=True, picker=FirstPicker())
    assert game.players["alice"].score == 1


def test_resolve_claim_confirmed_assigns_new_target_preferring_not_current():
    game = running_game(["alice", "bob", "carol"], FirstPicker())
    old_target = game.players["alice"].target_id
    add_claim(game, "alice")
    resolve_claim(game, "alice", confirmed=True, picker=FirstPicker())
    new_target = game.players["alice"].target_id
    assert new_target != old_target
    assert new_target != "alice"


def test_resolve_claim_confirmed_assigns_new_mission_and_deletes_claim():
    game = running_game(["alice", "bob", "carol"], FirstPicker())
    old_mission = game.players["alice"].mission
    add_claim(game, "alice")
    resolve_claim(game, "alice", confirmed=True, picker=FirstPicker())
    assert game.players["alice"].mission != old_mission
    assert "alice" not in game.claims


def test_resolve_claim_confirmed_falls_back_when_only_current_target_remains():
    # two players: the only possible target is the current one -> stays, must not crash
    game = running_game(["alice", "bob"], FirstPicker())
    assert game.players["alice"].target_id == "bob"
    add_claim(game, "alice")
    resolve_claim(game, "alice", confirmed=True, picker=FirstPicker())
    assert game.players["alice"].target_id == "bob"
    assert game.players["alice"].score == 1


# --- resolve_claim (refused) -----------------------------------------------------------


def test_confirmed_kill_swaps_targets_so_everyone_stays_hunted_exactly_once():
    # ring a -> b -> c -> d -> a; a scores on b
    game = running_game(["a", "b", "c", "d"], FirstPicker())
    add_claim(game, "a")

    resolve_claim(game, "a", confirmed=True, picker=FirstPicker())

    # the only valid partner is c: a takes c's target (d), c takes the victim (b)
    assert game.players["a"].target_id == "d"
    assert game.players["c"].target_id == "b"
    assert set(_hunt_counts(game).values()) == {1}
    assert all(p.target_id != p.id for p in game.players.values())


def test_confirmed_kill_never_swaps_with_a_hunter_who_has_a_pending_claim():
    game = running_game(["a", "b", "c", "d"], FirstPicker())  # a -> b -> c -> d -> a
    add_claim(game, "a")
    add_claim(game, "c")  # c is waiting for d to confirm: c's target must not change

    resolve_claim(game, "a", confirmed=True, picker=FirstPicker())

    assert game.players["c"].target_id == "d"
    assert game.players["a"].target_id != "b"


def test_confirmed_kill_with_three_players_falls_back_to_the_other_player():
    # a -> b -> c -> a: no swap keeps the ring valid, so a simply moves on to c
    game = running_game(["a", "b", "c"], FirstPicker())
    add_claim(game, "a")
    resolve_claim(game, "a", confirmed=True, picker=FirstPicker())
    assert game.players["a"].target_id == "c"


def test_fallback_prefers_the_least_hunted_player():
    game = make_game(["a", "b", "c", "d"])
    # not a ring (e.g. after departures): c is hunted by b and d, nobody hunts a's other options
    game.players["a"].target_id = "b"
    game.players["b"].target_id = "c"
    game.players["c"].target_id = "a"
    game.players["d"].target_id = "c"
    game.claims.clear()
    add_claim(game, "a")
    add_claim(game, "c")
    add_claim(game, "d")  # every potential partner is busy -> fallback

    resolve_claim(game, "a", confirmed=True, picker=FirstPicker())

    assert game.players["a"].target_id == "d"  # hunted by nobody, unlike c (hunted twice)


def test_confirmed_kill_when_the_attacker_is_alone_keeps_things_unchanged():
    game = running_game(["a", "b"], FirstPicker())
    add_claim(game, "a")
    game.players.pop("b")
    resolve_claim(game, "a", confirmed=True, picker=FirstPicker())
    assert game.players["a"].score == 1


# --- reassign_targets_away_from --------------------------------------------------------


def test_leaver_hunter_inherits_the_leavers_target():
    game = running_game(["a", "b", "c", "d"], FirstPicker())  # a -> b -> c -> d -> a
    leaver = game.players.pop("b")
    reassign_targets_away_from(game, "b", FirstPicker(), leaver.target_id)
    assert game.players["a"].target_id == "c"
    assert set(_hunt_counts(game).values()) == {1}


def test_leaver_hunter_never_inherits_themselves():
    game = running_game(["a", "b", "c"], FirstPicker())  # a -> b -> c -> a
    game.players["c"].target_id = "b"  # b <-> c and a -> b
    game.players["b"].target_id = "c"
    leaver = game.players.pop("b")
    reassign_targets_away_from(game, "b", FirstPicker(), leaver.target_id)
    # a inherits c; c (who hunted b) cannot inherit itself -> least hunted other player (a)
    assert game.players["a"].target_id == "c"
    assert game.players["c"].target_id == "a"


def test_last_remaining_player_has_no_target():
    game = running_game(["a", "b"], FirstPicker())
    leaver = game.players.pop("b")
    reassign_targets_away_from(game, "b", FirstPicker(), leaver.target_id)
    assert game.players["a"].target_id is None


def test_resolve_claim_refused_changes_mission_only_keeps_target_and_score():
    game = running_game(["alice", "bob", "carol"], FirstPicker())
    old_target = game.players["alice"].target_id
    old_mission = game.players["alice"].mission
    add_claim(game, "alice")
    resolve_claim(game, "alice", confirmed=False, picker=FirstPicker())
    assert game.players["alice"].target_id == old_target
    assert game.players["alice"].mission != old_mission
    assert game.players["alice"].score == 0
    assert "alice" not in game.claims


def test_resolve_claim_unknown_attacker_raises_player_not_found():
    game = running_game(["alice", "bob"], FirstPicker())
    with pytest.raises(PlayerNotFound):
        resolve_claim(game, "ghost", confirmed=True, picker=FirstPicker())


# --- swap_mission ----------------------------------------------------------------------


def test_swap_mission_changes_mission_and_decrements_score():
    game = running_game(["alice", "bob"], FirstPicker())
    old_mission = game.players["alice"].mission
    game.players["alice"].score = 2
    swap_mission(game, "alice", FirstPicker())
    assert game.players["alice"].mission != old_mission
    assert game.players["alice"].score == 1


def test_first_swap_at_zero_points_is_free_and_only_once():
    game = running_game(["alice", "bob"], FirstPicker())
    alice = game.players["alice"]
    old_mission = alice.mission
    assert swap_cost(alice) == 0

    swap_mission(game, "alice", FirstPicker())

    assert alice.mission != old_mission
    assert alice.score == 0  # never negative
    assert alice.free_swap_used
    assert swap_cost(alice) is None
    with pytest.raises(SwapNotAllowed):
        swap_mission(game, "alice", FirstPicker())
    assert alice.score == 0


def test_swap_costs_a_point_when_the_player_has_some():
    game = running_game(["alice", "bob"], FirstPicker())
    alice = game.players["alice"]
    alice.score = 1
    assert swap_cost(alice) == 1
    swap_mission(game, "alice", FirstPicker())
    assert alice.score == 0
    assert not alice.free_swap_used  # the free swap is kept for later
    assert swap_cost(alice) == 0


def test_score_never_goes_below_zero_through_swaps():
    game = running_game(["alice", "bob"], FirstPicker())
    alice = game.players["alice"]
    alice.score = 2
    for _ in range(3):  # 2 paid swaps + the free one
        swap_mission(game, "alice", FirstPicker())
    assert alice.score == 0
    with pytest.raises(SwapNotAllowed):
        swap_mission(game, "alice", FirstPicker())


# --- #20: an incoming claim must be answered first -------------------------------------


def test_incoming_claim_blocks_claiming_and_swapping():
    game = running_game(["a", "b", "c"], FirstPicker())  # a -> b -> c -> a
    add_claim(game, "a")  # b must answer a's claim
    assert has_incoming_claim(game, "b")
    with pytest.raises(MustAnswerClaimFirst):
        open_claim(game, "b", ts=1)
    with pytest.raises(MustAnswerClaimFirst):
        swap_mission(game, "b", FirstPicker())
    assert game.players["b"].score == 0 and not game.players["b"].free_swap_used

    mark_resolved(game, "a", confirmed=False)  # once answered, b is free again
    assert not has_incoming_claim(game, "b")
    open_claim(game, "b", ts=2)


def test_two_players_cannot_claim_each_other_at_the_same_time():
    game = running_game(["a", "b"], FirstPicker())  # a <-> b
    open_claim(game, "a", ts=1)
    with pytest.raises(MustAnswerClaimFirst):
        open_claim(game, "b", ts=2)


# --- #20: the last player standing ends the game ---------------------------------------


def test_running_game_ends_when_one_player_remains():
    game = running_game(["a", "b"], FirstPicker())
    add_claim(game, "a")
    remove_player(game, "b", FirstPicker())
    assert game.status is GameStatus.ENDED
    assert game.claims == {}


def test_running_game_with_players_left_keeps_going():
    game = running_game(["a", "b", "c"], FirstPicker())
    remove_player(game, "c", FirstPicker())
    assert game.status is GameStatus.RUNNING


def test_lobby_with_one_player_is_not_ended():
    game = make_game(["host", "guest"])
    remove_player(game, "guest", FirstPicker())
    assert game.status is GameStatus.LOBBY


def test_swap_mission_unknown_player_raises():
    game = running_game(["alice", "bob"], FirstPicker())
    with pytest.raises(PlayerNotFound):
        swap_mission(game, "ghost", FirstPicker())


# --- clamp_duration_min ----------------------------------------------------------------


def test_clamp_duration_below_one_becomes_one():
    assert clamp_duration_min(0) == 1
    assert clamp_duration_min(-5) == 1


def test_clamp_duration_above_240_becomes_240():
    assert clamp_duration_min(999) == 240


def test_clamp_duration_within_range_is_unchanged():
    assert clamp_duration_min(15) == 15


def test_clamp_duration_truncates_float():
    assert clamp_duration_min(15.9) == 15


# --- mark_resolved / advance_after_resolution (attacker acknowledgement) ---------------


def test_confirmation_scores_right_away_but_deals_nothing_yet():
    game = running_game(["alice", "bob", "carol"], FirstPicker())
    target, mission = game.players["alice"].target_id, game.players["alice"].mission
    add_claim(game, "alice")

    mark_resolved(game, "alice", confirmed=True)

    assert game.players["alice"].score == 1
    assert (game.players["alice"].target_id, game.players["alice"].mission) == (target, mission)
    assert game.claims["alice"].status is ClaimStatus.OK
    assert awaiting_ack(game, "alice")


def test_refusal_keeps_score_target_and_mission_until_acknowledged():
    game = running_game(["alice", "bob"], FirstPicker())
    mission = game.players["alice"].mission
    add_claim(game, "alice")

    mark_resolved(game, "alice", confirmed=False)

    assert game.players["alice"].score == 0
    assert game.players["alice"].mission == mission
    assert game.claims["alice"].status is ClaimStatus.NO


def test_a_claim_is_answered_only_once():
    game = running_game(["alice", "bob"], FirstPicker())
    add_claim(game, "alice")
    mark_resolved(game, "alice", confirmed=True)
    with pytest.raises(ClaimAlreadyResolved):
        mark_resolved(game, "alice", confirmed=True)
    assert game.players["alice"].score == 1


def test_answering_a_missing_claim_raises():
    game = running_game(["alice", "bob"], FirstPicker())
    with pytest.raises(ClaimNotFound):
        mark_resolved(game, "alice", confirmed=True)


def test_acknowledging_a_confirmation_deals_target_and_mission_and_consumes_the_claim():
    game = running_game(["a", "b", "c", "d"], FirstPicker())  # a -> b -> c -> d -> a
    old_mission = game.players["a"].mission
    add_claim(game, "a")
    mark_resolved(game, "a", confirmed=True)

    advance_after_resolution(game, "a", FirstPicker())

    assert game.players["a"].target_id == "d"  # ring-preserving swap with c
    assert game.players["a"].mission != old_mission
    assert "a" not in game.claims
    assert not awaiting_ack(game, "a")


def test_acknowledging_a_refusal_deals_a_mission_only():
    game = running_game(["a", "b", "c"], FirstPicker())
    target, old_mission = game.players["a"].target_id, game.players["a"].mission
    add_claim(game, "a")
    mark_resolved(game, "a", confirmed=False)

    advance_after_resolution(game, "a", FirstPicker())

    assert game.players["a"].target_id == target
    assert game.players["a"].mission != old_mission
    assert game.players["a"].score == 0
    assert "a" not in game.claims


def test_nothing_to_acknowledge_while_pending_or_without_claim():
    game = running_game(["a", "b"], FirstPicker())
    with pytest.raises(ClaimNotFound):
        advance_after_resolution(game, "a", FirstPicker())
    add_claim(game, "a")
    with pytest.raises(ClaimNotResolved):
        advance_after_resolution(game, "a", FirstPicker())
    assert not awaiting_ack(game, "a")  # pending is not "awaiting ack"


def test_advance_for_unknown_attacker_raises():
    game = running_game(["a", "b"], FirstPicker())
    with pytest.raises(PlayerNotFound):
        advance_after_resolution(game, "ghost", FirstPicker())


def test_finish_ends_the_game_and_settles_every_claim():
    game = running_game(["a", "b", "c"], FirstPicker())
    add_claim(game, "a")
    add_claim(game, "b")
    mark_resolved(game, "a", confirmed=True)
    finish(game)
    assert game.status is GameStatus.ENDED
    assert game.claims == {}
    assert game.players["a"].score == 1  # already counted


# --- review of #19: rules that must hold around the acknowledgement --------------------


def test_open_claim_requires_acknowledging_first_even_without_target():
    game = running_game(["a", "b"], FirstPicker())
    add_claim(game, "a")
    mark_resolved(game, "a", confirmed=True)
    game.players["a"].target_id = None  # e.g. the only other player left
    with pytest.raises(ClaimAwaitingAck):
        open_claim(game, "a", ts=1)


def test_open_claim_records_a_pending_claim_on_the_current_target():
    game = running_game(["a", "b", "c"], FirstPicker())
    claim = open_claim(game, "a", ts=42)
    assert (claim.target, claim.status, claim.ts) == ("b", ClaimStatus.PENDING, 42)
    assert game.claims["a"] is claim


def test_open_claim_without_target_or_player_raises():
    game = running_game(["a", "b"], FirstPicker())
    game.players["a"].target_id = None
    with pytest.raises(NoTargetAssigned):
        open_claim(game, "a", ts=1)
    with pytest.raises(PlayerNotFound):
        open_claim(game, "ghost", ts=1)


def test_swap_mission_waits_for_the_acknowledgement():
    game = running_game(["a", "b"], FirstPicker())
    add_claim(game, "a")
    mark_resolved(game, "a", confirmed=False)
    with pytest.raises(ClaimAwaitingAck):
        swap_mission(game, "a", FirstPicker())
    assert game.players["a"].score == 0


def test_victim_leaving_before_the_ack_keeps_the_attackers_new_target():
    game = running_game(["a", "b", "c", "d"], FirstPicker())  # a -> b -> c -> d -> a
    add_claim(game, "a")
    mark_resolved(game, "a", confirmed=True)

    remove_player(game, "b", FirstPicker())
    assert game.players["a"].target_id == "c"  # inherited from the leaver
    assert game.claims["a"].status is ClaimStatus.OK  # still to acknowledge

    advance_after_resolution(game, "a", FirstPicker())
    assert game.players["a"].target_id == "c"  # c was not eliminated: no second move
    assert set(_hunt_counts(game).values()) == {1}


def test_refused_victim_leaving_before_the_ack_keeps_the_new_target_too():
    game = running_game(["a", "b", "c", "d"], FirstPicker())
    add_claim(game, "a")
    mark_resolved(game, "a", confirmed=False)
    remove_player(game, "b", FirstPicker())
    advance_after_resolution(game, "a", FirstPicker())
    assert game.players["a"].target_id == "c"


def test_a_player_slow_to_acknowledge_does_not_break_the_ring():
    # ring a -> b -> c -> d -> e -> a; c scored on d and has not acknowledged yet
    game = running_game(["a", "b", "c", "d", "e"], FirstPicker())
    add_claim(game, "c")
    mark_resolved(game, "c", confirmed=True)
    add_claim(game, "d")  # pending: d is off limits, so c is the only partner for a swap
    add_claim(game, "a")
    mark_resolved(game, "a", confirmed=True)

    advance_after_resolution(game, "a", FirstPicker())  # may swap with c
    advance_after_resolution(game, "c", FirstPicker())

    assert set(_hunt_counts(game).values()) == {1}
    assert all(p.target_id != p.id for p in game.players.values())


def test_remove_player_drops_pending_claims_on_them_and_passes_the_host_role():
    game = running_game(["a", "b", "c"], FirstPicker())
    add_claim(game, "c")  # c -> a, pending
    add_claim(game, "a")
    remove_player(game, "a", FirstPicker())
    assert game.claims == {}
    assert game.host_id == "b"


def test_remove_last_player_leaves_an_empty_game():
    game = make_game(["solo"])
    remove_player(game, "solo", FirstPicker())
    assert game.players == {}
