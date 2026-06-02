"""Deterministic test doubles for the injected ports (Picker, Clock, id/code generators)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from src.domain.models import Game


class FirstPicker:
    """Picker that always returns the first element of the sequence."""

    def choice[T](self, seq: Sequence[T]) -> T:
        return list(seq)[0]


class SequencePicker:
    """Picker that returns scripted values in order, ignoring the offered sequence."""

    def __init__(self, *values: Any) -> None:
        self._values = list(values)
        self._i = 0

    def choice[T](self, seq: Sequence[T]) -> T:
        value = self._values[self._i]
        self._i += 1
        return value


class FakeClock:
    """Controllable Clock for deterministic time in use-case tests."""

    def __init__(self, now_ms: int = 1_000_000) -> None:
        self._now = now_ms

    def now_ms(self) -> int:
        return self._now

    def advance(self, ms: int) -> None:
        self._now += ms


class SequenceIds:
    """IdGenerator returning scripted player ids in order."""

    def __init__(self, *ids: str) -> None:
        self._ids = list(ids)
        self._i = 0

    def new_id(self) -> str:
        value = self._ids[self._i]
        self._i += 1
        return value


class FixedCodes:
    """CodeGenerator returning scripted codes in order (to drive collision-retry tests)."""

    def __init__(self, *codes: str) -> None:
        self._codes = list(codes)
        self._i = 0

    def new_code(self) -> str:
        value = self._codes[self._i]
        self._i += 1
        return value


class SpyNotifier:
    """RealtimeNotifier that records every published game, to assert use cases broadcast."""

    def __init__(self) -> None:
        self.published: list[Game] = []

    async def publish(self, game: Game) -> None:
        self.published.append(game)
