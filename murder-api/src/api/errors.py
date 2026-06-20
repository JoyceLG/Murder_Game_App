"""Map domain errors to HTTP status codes via a single exception handler."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.domain.errors import (
    ClaimNotFound,
    DomainError,
    GameAlreadyStarted,
    GameNotFound,
    GameNotRunning,
    InvalidGameConfig,
    InvalidMission,
    MissionNotFound,
    NotAllowedToRemoveMission,
    NoTargetAssigned,
    NotEnoughPlayers,
    NotTheClaimTarget,
    NotTheHost,
    PlayerNotFound,
    TooManyPlayers,
)

STATUS_MAP: dict[type[DomainError], int] = {
    GameNotFound: 404,
    PlayerNotFound: 404,
    ClaimNotFound: 404,
    MissionNotFound: 404,
    GameAlreadyStarted: 409,
    GameNotRunning: 409,
    NotEnoughPlayers: 409,
    TooManyPlayers: 409,
    InvalidGameConfig: 409,
    InvalidMission: 422,
    NoTargetAssigned: 409,
    NotTheHost: 403,
    NotTheClaimTarget: 403,
    NotAllowedToRemoveMission: 403,
}


async def domain_error_handler(_request: Request, exc: DomainError) -> JSONResponse:
    status = STATUS_MAP.get(type(exc), 400)
    return JSONResponse(status_code=status, content={"error": type(exc).__name__})


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, domain_error_handler)
