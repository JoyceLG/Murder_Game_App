"""Pydantic DTOs — the API contract. Domain entities are never exposed directly."""

from __future__ import annotations

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


class ConfirmClaimIn(BaseModel):
    confirmed: bool


# --- responses -------------------------------------------------------------------------


class PlayerOut(BaseModel):
    id: str
    name: str
    score: int
    mission: str
    target_id: str | None


class ClaimOut(BaseModel):
    atk: str
    atk_name: str
    target: str
    mission: str
    status: str


class GameOut(BaseModel):
    code: str
    host_id: str
    status: str
    duration_sec: int
    start_at: int
    end_at: int
    remaining_sec: int
    max_players: int
    max_score: int | None
    players: list[PlayerOut]
    claims: list[ClaimOut]
    ranking: list[PlayerOut]


class CreatedGameOut(GameOut):
    player_id: str


class JoinedGameOut(GameOut):
    player_id: str
