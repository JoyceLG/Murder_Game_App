"""Map domain errors to HTTP status codes via a single exception handler."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.api.rate_limit import client_key
from src.domain.errors import (
    ClaimAlreadyResolved,
    ClaimAwaitingAck,
    ClaimNotFound,
    ClaimNotResolved,
    CodeSpaceExhausted,
    ConcurrentUpdate,
    DomainError,
    GameAlreadyStarted,
    GameNotFound,
    GameNotRunning,
    InvalidGameConfig,
    InvalidMission,
    MissionNotFound,
    NotAllowedToRemoveMission,
    NoTargetAssigned,
    NotAuthenticated,
    NotEnoughPlayers,
    NotTheClaimAttacker,
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
    NotAuthenticated: 401,
    NotTheClaimAttacker: 403,
    ClaimAlreadyResolved: 409,
    ClaimNotResolved: 409,
    ClaimAwaitingAck: 409,
    ConcurrentUpdate: 409,
    CodeSpaceExhausted: 503,
}


async def domain_error_handler(request: Request | None, exc: DomainError) -> JSONResponse:
    status = STATUS_MAP.get(type(exc), 400)
    if isinstance(exc, GameNotFound) and request is not None:
        # Unknown codes count against the caller: this is what makes code enumeration slow.
        limiter = getattr(request.app.state, "miss_limiter", None)
        if limiter is not None:
            limiter.hit(client_key(request))
    return JSONResponse(status_code=status, content={"error": type(exc).__name__})


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, domain_error_handler)
