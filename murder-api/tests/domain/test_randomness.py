import random

import src.domain.randomness as rnd
from src.domain.missions import MISSIONS
from src.domain.randomness import RandomPicker, pick_mission_excluding
from tests.doubles import FirstPicker


def test_random_picker_returns_member_of_sequence():
    seq = ["a", "b", "c"]
    assert RandomPicker(random.Random(0)).choice(seq) in seq


def test_random_picker_is_seeded_deterministic():
    a = RandomPicker(random.Random(42)).choice(list(range(100)))
    b = RandomPicker(random.Random(42)).choice(list(range(100)))
    assert a == b


def test_pick_mission_excluding_never_returns_excluded():
    current = MISSIONS[0]
    for _ in range(50):
        assert pick_mission_excluding(RandomPicker(), current) != current


def test_pick_mission_excluding_returns_any_mission_when_exclude_absent():
    assert pick_mission_excluding(FirstPicker(), "not-a-real-mission") == MISSIONS[0]


def test_pick_mission_excluding_falls_back_when_single_mission(monkeypatch):
    monkeypatch.setattr(rnd, "MISSIONS", ("solo",))
    assert pick_mission_excluding(FirstPicker(), "solo") == "solo"
