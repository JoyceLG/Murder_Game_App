"""Use case: prove the caller is the player they claim to be (id + session secret).

The single place identity is checked. Phase 17 replaces the secret with a signed JWT; callers
(`api/dependencies.player_id` and the WebSocket handshake) do not change.
"""

from __future__ import annotations

import hmac
from dataclasses import dataclass

from src.application._support import digest_secret, get_game_or_404
from src.domain.errors import NotAuthenticated
from src.ports.repository import GameRepository


@dataclass
class AuthenticatePlayer:
    repo: GameRepository

    async def execute(self, code: str, player_id: str, token: str) -> str:
        game = await get_game_or_404(self.repo, code)
        player = game.players.get(player_id)
        if (
            player is None
            or not player.token_hash
            or not hmac.compare_digest(player.token_hash, digest_secret(token))
        ):
            raise NotAuthenticated()
        return player_id
