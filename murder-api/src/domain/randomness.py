"""Randomness, injected as a port so the domain stays pure and deterministically testable.

`rules.py` never imports `random`; it receives a `Picker`. Production wires `RandomPicker`;
tests inject scripted pickers (see tests/doubles.py).
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from typing import Protocol

from src.domain.missions import MISSIONS


class Picker(Protocol):
    def choice[T](self, seq: Sequence[T]) -> T: ...


class RandomPicker:
    """Default production picker, backed by `random.Random` (seedable for reproducibility)."""

    def __init__(self, rng: random.Random | None = None) -> None:
        self._rng = rng or random.Random()

    def choice[T](self, seq: Sequence[T]) -> T:
        return self._rng.choice(list(seq))


def pick_mission_excluding(picker: Picker, exclude: str) -> str:
    """Pick a mission different from `exclude` when possible.

    Replaces the JS single-retry quirk (`m = pick(); if m === cur: m = pick()`), which could
    still land on the same mission. Here we exclude up front and fall back only if the catalogue
    has a single entry.
    """
    pool = [m for m in MISSIONS if m != exclude] or list(MISSIONS)
    return picker.choice(pool)
