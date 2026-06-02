"""Dependency-injection wiring. Components are built once in main.create_app and stored on
app.state; these providers read them and assemble use cases per request. This module is the only
place that knows which concrete adapters are in play.
"""

from __future__ import annotations

from fastapi import Depends, Header, Request

from src.application.claim_elimination import ClaimElimination
from src.application.confirm_claim import ConfirmClaim
from src.application.create_game import CreateGame
from src.application.end_game import EndGame
from src.application.get_game import GetGame
from src.application.join_game import JoinGame
from src.application.leave_game import LeaveGame
from src.application.start_game import StartGame
from src.application.swap_mission import SwapMission
from src.domain.randomness import Picker
from src.ports.clock import Clock
from src.ports.identifiers import CodeGenerator, IdGenerator
from src.ports.notifier import RealtimeNotifier
from src.ports.repository import GameRepository

# --- component accessors (from app.state) ----------------------------------------------


def get_repo(request: Request) -> GameRepository:
    return request.app.state.repo


def get_clock(request: Request) -> Clock:
    return request.app.state.clock


def get_ids(request: Request) -> IdGenerator:
    return request.app.state.ids


def get_codes(request: Request) -> CodeGenerator:
    return request.app.state.codes


def get_picker(request: Request) -> Picker:
    return request.app.state.picker


def get_notifier(request: Request) -> RealtimeNotifier:
    return request.app.state.notifier


def player_id(x_player_id: str = Header(...)) -> str:
    """Caller identity, read from the X-Player-Id header (422 if absent)."""
    return x_player_id


# --- use-case providers -----------------------------------------------------------------


def create_game_uc(
    repo: GameRepository = Depends(get_repo),
    ids: IdGenerator = Depends(get_ids),
    codes: CodeGenerator = Depends(get_codes),
    clock: Clock = Depends(get_clock),
) -> CreateGame:
    return CreateGame(repo=repo, ids=ids, codes=codes, clock=clock)


def join_game_uc(
    repo: GameRepository = Depends(get_repo),
    ids: IdGenerator = Depends(get_ids),
    clock: Clock = Depends(get_clock),
    notifier: RealtimeNotifier = Depends(get_notifier),
) -> JoinGame:
    return JoinGame(repo=repo, ids=ids, clock=clock, notifier=notifier)


def start_game_uc(
    repo: GameRepository = Depends(get_repo),
    clock: Clock = Depends(get_clock),
    picker: Picker = Depends(get_picker),
    notifier: RealtimeNotifier = Depends(get_notifier),
) -> StartGame:
    return StartGame(repo=repo, clock=clock, picker=picker, notifier=notifier)


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
    picker: Picker = Depends(get_picker),
    notifier: RealtimeNotifier = Depends(get_notifier),
) -> LeaveGame:
    return LeaveGame(repo=repo, picker=picker, notifier=notifier)


def end_uc(
    repo: GameRepository = Depends(get_repo),
    notifier: RealtimeNotifier = Depends(get_notifier),
) -> EndGame:
    return EndGame(repo=repo, notifier=notifier)


def get_game_uc(
    repo: GameRepository = Depends(get_repo),
    clock: Clock = Depends(get_clock),
) -> GetGame:
    return GetGame(repo=repo, clock=clock)
