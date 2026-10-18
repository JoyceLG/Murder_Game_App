"""Pydantic DTOs — the API contract. Domain entities are never exposed directly."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# --- requests --------------------------------------------------------------------------


class CreateGameIn(BaseModel):
    host_name: str = Field(min_length=1, max_length=18)  # matches the legacy UI maxlength


class JoinGameIn(BaseModel):
    name: str = Field(min_length=1, max_length=18)


class StartGameIn(BaseModel):
    duration_min: int = Field(ge=1, le=240)


class UpdateGameConfigIn(BaseModel):
    max_players: int = Field(ge=2, le=12)
    max_score: int | None = Field(default=None, ge=1)
    mission_mode: Literal["augment", "replace"] = "augment"


class AddMissionToPoolIn(BaseModel):
    text: str = Field(min_length=1, max_length=200)


class ConfirmClaimIn(BaseModel):
    confirmed: bool


# --- responses -------------------------------------------------------------------------


class PlayerOut(BaseModel):
    """What every player may know about any player."""

    id: str
    name: str
    score: int


class MeOut(PlayerOut):
    """The viewer's own secrets: their mission and who they hunt. Never sent to anyone else."""

    mission: str
    target_id: str | None
    swap_cost: int | None  # 1 point, 0 (the one free swap at 0 points), None = cannot swap


class ClaimOut(BaseModel):
    atk: str
    atk_name: str
    target: str
    mission: str
    status: str


class PooledMissionOut(BaseModel):
    id: str
    text: str
    by: str


class GameOut(BaseModel):
    """One player's view of a game (see mappers.to_player_view)."""

    code: str
    host_id: str
    status: str
    duration_sec: int
    start_at: int
    end_at: int
    remaining_sec: int
    server_now: int  # server clock (unix ms) when this view was built: lets clients fix skew
    version: int  # increases with every change; clients keep the newest state they have seen
    max_players: int
    max_score: int | None
    mission_mode: str
    players: list[PlayerOut]
    me: MeOut | None  # None for an anonymous viewer
    claims: list[ClaimOut]  # only the claims the viewer makes or must answer
    mission_pool: list[PooledMissionOut]
    ranking: list[PlayerOut]


class CreatedGameOut(GameOut):
    player_id: str
    player_token: str  # the session secret: returned once, sent back in X-Player-Token


class JoinedGameOut(GameOut):
    player_id: str
    player_token: str
