import pytest

from src.domain.errors import PlayerNotFound
from src.domain.missions import MISSIONS
from src.domain.rules import (
    assign_targets,
    clamp_duration_min,
    resolve_claim,
    swap_mission,
)
from tests.builders import add_claim, make_game, running_game
from tests.doubles import FirstPicker, SequencePicker

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
        assert player.mission in MISSIONS


def test_assign_targets_two_players_target_each_other():
    game = make_game(["alice", "bob"])
    assign_targets(game, FirstPicker())
    assert game.players["alice"].target_id == "bob"
    assert game.players["bob"].target_id == "alice"


def test_assign_targets_is_deterministic_with_injected_picker():
    game = make_game(["alice", "bob", "carol"])
    # scripted as (target, mission) per player, in insertion order
    picker = SequencePicker("bob", MISSIONS[0], "carol", MISSIONS[1], "alice", MISSIONS[2])
    assign_targets(game, picker)
    assert (game.players["alice"].target_id, game.players["alice"].mission) == ("bob", MISSIONS[0])
    assert (game.players["bob"].target_id, game.players["bob"].mission) == ("carol", MISSIONS[1])
    assert (game.players["carol"].target_id, game.players["carol"].mission) == (
        "alice",
        MISSIONS[2],
    )


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
