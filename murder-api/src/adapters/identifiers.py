"""Identifier adapters: unguessable player ids and short, human-friendly game codes."""

from __future__ import annotations

import secrets
from uuid import uuid4

# Code alphabet ported from legacy-js code4(): no I/O/0/1 to avoid ambiguity when read aloud.
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 4


class UuidGenerator:
    """Player id = a full uuid4 hex. Doubles as the (unsigned) identity token; see README."""

    def new_id(self) -> str:
        return uuid4().hex


class RandomCodeGenerator:
    def new_code(self) -> str:
        return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
