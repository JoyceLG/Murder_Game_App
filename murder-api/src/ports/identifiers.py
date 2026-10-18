"""Driven ports: generation of player ids, session secrets and game codes (scripted in tests)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class IdGenerator(Protocol):
    def new_id(self) -> str: ...


@runtime_checkable
class CodeGenerator(Protocol):
    def new_code(self) -> str: ...


@runtime_checkable
class SecretGenerator(Protocol):
    def new_secret(self) -> str: ...
