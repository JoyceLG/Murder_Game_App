import random
from collections import Counter

import pytest

from src.domain.errors import PlayerNotFound
from src.domain.missions import MISSION_KEYS
from src.domain.randomness import RandomPicker
from src.domain.rules import (
    assign_targets,
    clamp_duration_min,
    reassign_targets_away_from,
    resolve_claim,
    swap_mission,
)
from tests.builders import add_claim, make_game, running_game
from tests.doubles import FirstPicker, SequencePicker


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


def test_swap_mission_can_make_score_negative():
    game = running_game(["alice", "bob"], FirstPicker())
    assert game.players["alice"].score == 0
    swap_mission(game, "alice", FirstPicker())
    assert game.players["alice"].score == -1


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
