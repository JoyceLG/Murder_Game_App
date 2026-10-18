"""Dependency-injection wiring. Components are built once in main.create_app and stored on
app.state; these providers read them and assemble use cases per request. This module is the only
place that knows which concrete adapters are in play.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Depends, Header, HTTPException
from starlette.requests import HTTPConnection

from src.api.rate_limit import RateLimiter, client_key
from src.application.add_mission_to_pool import AddMissionToPool
from src.application.authenticate_player import AuthenticatePlayer
from src.application.claim_elimination import ClaimElimination
from src.application.confirm_claim import ConfirmClaim
from src.application.create_game import CreateGame
from src.application.end_game import EndGame
from src.application.get_game import GetGame
from src.application.join_game import JoinGame
from src.application.leave_game import LeaveGame
from src.application.remove_mission_from_pool import RemoveMissionFromPool
from src.application.start_game import StartGame
from src.application.swap_mission import SwapMission
from src.application.update_config import UpdateGameConfig
from src.domain.randomness import Picker
from src.ports.clock import Clock
from src.ports.identifiers import CodeGenerator, IdGenerator, SecretGenerator
from src.ports.notifier import RealtimeNotifier
from src.ports.repository import GameRepository

# --- component accessors (from app.state) ----------------------------------------------
# Typed on HTTPConnection so the same providers serve REST requests and the WebSocket.


def get_repo(conn: HTTPConnection) -> GameRepository:
    return conn.app.state.repo


def get_clock(conn: HTTPConnection) -> Clock:
    return conn.app.state.clock


def get_ids(conn: HTTPConnection) -> IdGenerator:
    return conn.app.state.ids


def get_secrets(conn: HTTPConnection) -> SecretGenerator:
    return conn.app.state.secrets


def get_codes(conn: HTTPConnection) -> CodeGenerator:
    return conn.app.state.codes


def get_picker(conn: HTTPConnection) -> Picker:
    return conn.app.state.picker


def get_notifier(conn: HTTPConnection) -> RealtimeNotifier:
    return conn.app.state.notifier


# --- abuse control & concurrency -----------------------------------------------------------


def _limit(limiter: RateLimiter | None, conn: HTTPConnection) -> None:
    if limiter is not None and not limiter.allow(client_key(conn)):
        raise HTTPException(status_code=429, detail="RateLimited")


def rate_limited(conn: HTTPConnection) -> None:
    """Global per-client budget, applied to every route."""
    _limit(conn.app.state.rate_limiter, conn)


def create_rate_limited(conn: HTTPConnection) -> None:
    """Tighter budget for game creation."""
    _limit(conn.app.state.create_limiter, conn)


def lookup_guard(conn: HTTPConnection) -> None:
    """Refuse code-addressed calls from a client that keeps asking for codes that don't exist."""
    limiter: RateLimiter | None = conn.app.state.miss_limiter
    if limiter is not None and limiter.exhausted(client_key(conn)):
        raise HTTPException(status_code=429, detail="RateLimited")


async def game_lock(code: str, conn: HTTPConnection) -> AsyncIterator[None]:
    """Serialize the requests that touch one game (see api/locks.py)."""
    async with conn.app.state.locks.hold(code):
        yield


# --- identity --------------------------------------------------------------------------


def authenticate_uc(repo: GameRepository = Depends(get_repo)) -> AuthenticatePlayer:
    return AuthenticatePlayer(repo=repo)


async def player_id(
    code: str,
    x_player_id: str = Header(..., min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$"),
    x_player_token: str = Header(..., min_length=1, max_length=128),
    auth: AuthenticatePlayer = Depends(authenticate_uc),
) -> str:
    """Caller identity: the public id in X-Player-Id, proven by the secret in X-Player-Token.

    422 if a header is missing or malformed, 401 if the pair does not match a player of the
    game. This is the single point to swap for JWT verification (phase 17).
    """
    return await auth.execute(code, x_player_id, x_player_token)


async def optional_player_id(
    code: str,
    x_player_id: str | None = Header(None, max_length=64, pattern=r"^[A-Za-z0-9_-]+$"),
    x_player_token: str | None = Header(None, max_length=128),
    auth: AuthenticatePlayer = Depends(authenticate_uc),
) -> str | None:
    """Like `player_id`, but anonymous callers (no headers) get the public view."""
    if not x_player_id or not x_player_token:
        return None
    return await auth.execute(code, x_player_id, x_player_token)


# --- use-case providers -----------------------------------------------------------------


def create_game_uc(
    repo: GameRepository = Depends(get_repo),
    ids: IdGenerator = Depends(get_ids),
    codes: CodeGenerator = Depends(get_codes),
    clock: Clock = Depends(get_clock),
    secrets: SecretGenerator = Depends(get_secrets),
) -> CreateGame:
    return CreateGame(repo=repo, ids=ids, codes=codes, clock=clock, secrets=secrets)


def join_game_uc(
    repo: GameRepository = Depends(get_repo),
    ids: IdGenerator = Depends(get_ids),
    clock: Clock = Depends(get_clock),
    notifier: RealtimeNotifier = Depends(get_notifier),
    secrets: SecretGenerator = Depends(get_secrets),
) -> JoinGame:
    return JoinGame(repo=repo, ids=ids, clock=clock, notifier=notifier, secrets=secrets)


def start_game_uc(
    repo: GameRepository = Depends(get_repo),
    clock: Clock = Depends(get_clock),
    picker: Picker = Depends(get_picker),
    notifier: RealtimeNotifier = Depends(get_notifier),
) -> StartGame:
    return StartGame(repo=repo, clock=clock, picker=picker, notifier=notifier)


def update_config_uc(
    repo: GameRepository = Depends(get_repo),
    notifier: RealtimeNotifier = Depends(get_notifier),
) -> UpdateGameConfig:
    return UpdateGameConfig(repo=repo, notifier=notifier)


def add_mission_uc(
    repo: GameRepository = Depends(get_repo),
    ids: IdGenerator = Depends(get_ids),
    notifier: RealtimeNotifier = Depends(get_notifier),
) -> AddMissionToPool:
    return AddMissionToPool(repo=repo, ids=ids, notifier=notifier)


def remove_mission_uc(
    repo: GameRepository = Depends(get_repo),
    notifier: RealtimeNotifier = Depends(get_notifier),
) -> RemoveMissionFromPool:
    return RemoveMissionFromPool(repo=repo, notifier=notifier)


def claim_uc(
    repo: GameRepository = Depends(get_repo),
    clock: Clock = Depends(get_clock),
    notifier: RealtimeNotifier = Depends(get_notifier),
) -> ClaimElimination:
    return ClaimElimination(repo=repo, clock=clock, notifier=notifier)


def confirm_uc(
    repo: GameRepository = Depends(get_repo),
    clock: Clock = Depends(get_clock),
    picker: Picker = Depends(get_picker),
    notifier: RealtimeNotifier = Depends(get_notifier),
) -> ConfirmClaim:
    return ConfirmClaim(repo=repo, clock=clock, picker=picker, notifier=notifier)


def swap_uc(
    repo: GameRepository = Depends(get_repo),
    clock: Clock = Depends(get_clock),
    picker: Picker = Depends(get_picker),
    notifier: RealtimeNotifier = Depends(get_notifier),
) -> SwapMission:
    return SwapMission(repo=repo, clock=clock, picker=picker, notifier=notifier)


def leave_uc(
    repo: GameRepository = Depends(get_repo),
    clock: Clock = Depends(get_clock),
    picker: Picker = Depends(get_picker),
    notifier: RealtimeNotifier = Depends(get_notifier),
) -> LeaveGame:
    return LeaveGame(repo=repo, clock=clock, picker=picker, notifier=notifier)


def end_uc(
    repo: GameRepository = Depends(get_repo),
    clock: Clock = Depends(get_clock),
    notifier: RealtimeNotifier = Depends(get_notifier),
) -> EndGame:
    return EndGame(repo=repo, clock=clock, notifier=notifier)


def get_game_uc(
    repo: GameRepository = Depends(get_repo),
    clock: Clock = Depends(get_clock),
    notifier: RealtimeNotifier = Depends(get_notifier),
) -> GetGame:
    return GetGame(repo=repo, clock=clock, notifier=notifier)
