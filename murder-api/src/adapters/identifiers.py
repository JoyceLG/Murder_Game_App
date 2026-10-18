"""Identifier adapters: player ids, session secrets and short, human-friendly game codes."""

from __future__ import annotations

import secrets
from uuid import uuid4

# Code alphabet ported from legacy-js code4(): no I/O/0/1 to avoid ambiguity when read aloud.
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 4


class UuidGenerator:
    """Player id = a full uuid4 hex. Public (other players see it); identity is the secret."""

    def new_id(self) -> str:
        return uuid4().hex


class TokenGenerator:
    """Session secret: 256 bits of randomness, URL-safe. Proves the caller owns a player id."""

    def new_secret(self) -> str:
        return secrets.token_urlsafe(32)


class RandomCodeGenerator:
    def new_code(self) -> str:
        return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
