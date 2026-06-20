"""Domain models — pure data, no framework imports.

Ported from the Firestore-shaped objects used by legacy-js/src/game.js:
  games/{code}, games/{code}/players/{playerId}, games/{code}/claims/{attackerId}.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class GameStatus(StrEnum):
    LOBBY = "lobby"
    RUNNING = "running"
    ENDED = "ended"


class ClaimStatus(StrEnum):
    PENDING = "pending"
    OK = "ok"
    NO = "no"


class MissionMode(StrEnum):
    """How the per-game mission pool combines with the default catalogue."""

    AUGMENT = "augment"  # catalogue + pool
    REPLACE = "replace"  # pool only (when non-empty)


@dataclass
class PooledMission:
    """A custom mission added to a game's pool. `by` is the id of the player who added it."""

    id: str
    text: str
    by: str


@dataclass
class Player:
    id: str
    name: str
    score: int = 0
    mission: str = ""
    target_id: str | None = None
    joined_at: int = 0  # unix ms


@dataclass
class Claim:
    """An attacker's pending elimination claim. Keyed by attacker id (one active per attacker)."""

    atk: str  # attacker id (== the claim's key in Game.claims)
    atk_name: str
    target: str  # the target's player id
    mission: str  # the mission the attacker claims to have completed
    status: ClaimStatus = ClaimStatus.PENDING
    ts: int = 0  # unix ms


DEFAULT_MAX_PLAYERS = 12


@dataclass
class Game:
    code: str
    host_id: str
    status: GameStatus = GameStatus.LOBBY
    duration_sec: int = 0
    start_at: int = 0  # unix ms
    end_at: int = 0  # unix ms
    max_players: int = DEFAULT_MAX_PLAYERS
    max_score: int | None = None  # None = no score cap; the game then ends on time only
    mission_mode: MissionMode = MissionMode.AUGMENT
    players: dict[str, Player] = field(default_factory=dict)
    claims: dict[str, Claim] = field(default_factory=dict)
    mission_pool: list[PooledMission] = field(default_factory=list)

    def is_time_up(self, now_ms: int) -> bool:
        """True once the running clock has reached end_at (JS: now() >= endAt)."""
        return self.end_at > 0 and now_ms >= self.end_at

    def is_full(self) -> bool:
        """True once the lobby has reached its player cap."""
        return len(self.players) >= self.max_players

    def score_cap_reached(self) -> bool:
        """True when a score cap is set and at least one player has reached it."""
        return self.max_score is not None and any(
            p.score >= self.max_score for p in self.players.values()
        )

    def ranking(self) -> list[Player]:
        """Players sorted by score descending. Stable: ties keep insertion (join) order."""
        return sorted(self.players.values(), key=lambda p: p.score, reverse=True)
