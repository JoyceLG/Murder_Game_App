"""Driven port: a source of time, injected so use cases are deterministic under test."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Clock(Protocol):
    def now_ms(self) -> int: ...
