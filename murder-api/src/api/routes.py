"""REST endpoints — thin adapters that call a use case and map the result to a DTO."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from src.api import schemas
from src.api.dependencies import (
    add_mission_uc,
    claim_uc,
    confirm_uc,
    create_game_uc,
    end_uc,
    get_clock,
    get_game_uc,
    join_game_uc,
    leave_uc,
    player_id,
    remove_mission_uc,
    start_game_uc,
    swap_uc,
    update_config_uc,
)
from src.api.mappers import claim_out, to_game_out
from src.application.add_mission_to_pool import AddMissionToPool
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
from src.domain.models import MissionMode
from src.ports.clock import Clock

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/games", status_code=201, response_model=schemas.CreatedGameOut)
async def create_game(
    body: schemas.CreateGameIn,
    uc: CreateGame = Depends(create_game_uc),
    clock: Clock = Depends(get_clock),
) -> schemas.CreatedGameOut:
    game, pid = await uc.execute(body.host_name)
    return schemas.CreatedGameOut(player_id=pid, **to_game_out(game, clock.now_ms()).model_dump())


@router.post("/games/{code}/players", status_code=201, response_model=schemas.JoinedGameOut)
async def join_game(
    code: str,
    body: schemas.JoinGameIn,
    uc: JoinGame = Depends(join_game_uc),
    clock: Clock = Depends(get_clock),
) -> schemas.JoinedGameOut:
    game, pid = await uc.execute(code, body.name)
    return schemas.JoinedGameOut(player_id=pid, **to_game_out(game, clock.now_ms()).model_dump())


@router.post("/games/{code}/start", response_model=schemas.GameOut)
async def start_game(
    code: str,
    body: schemas.StartGameIn,
    pid: str = Depends(player_id),
    uc: StartGame = Depends(start_game_uc),
    clock: Clock = Depends(get_clock),
) -> schemas.GameOut:
    game = await uc.execute(code, pid, body.duration_min)
    return to_game_out(game, clock.now_ms())


@router.patch("/games/{code}/config", response_model=schemas.GameOut)
async def update_config(
    code: str,
    body: schemas.UpdateGameConfigIn,
    pid: str = Depends(player_id),
    uc: UpdateGameConfig = Depends(update_config_uc),
    clock: Clock = Depends(get_clock),
) -> schemas.GameOut:
    game = await uc.execute(
        code, pid, body.max_players, body.max_score, MissionMode(body.mission_mode)
    )
    return to_game_out(game, clock.now_ms())


@router.post("/games/{code}/missions", response_model=schemas.GameOut)
async def add_mission(
    code: str,
    body: schemas.AddMissionToPoolIn,
    pid: str = Depends(player_id),
    uc: AddMissionToPool = Depends(add_mission_uc),
    clock: Clock = Depends(get_clock),
) -> schemas.GameOut:
    game = await uc.execute(code, pid, body.text)
    return to_game_out(game, clock.now_ms())


@router.delete("/games/{code}/missions/{mission_id}", response_model=schemas.GameOut)
async def remove_mission(
    code: str,
    mission_id: str,
    pid: str = Depends(player_id),
    uc: RemoveMissionFromPool = Depends(remove_mission_uc),
    clock: Clock = Depends(get_clock),
) -> schemas.GameOut:
    game = await uc.execute(code, pid, mission_id)
    return to_game_out(game, clock.now_ms())


@router.post("/games/{code}/claims", status_code=201, response_model=schemas.ClaimOut)
async def claim_elimination(
    code: str,
    pid: str = Depends(player_id),
    uc: ClaimElimination = Depends(claim_uc),
) -> schemas.ClaimOut:
    claim = await uc.execute(code, pid)
    return claim_out(claim)


@router.post("/games/{code}/claims/{attacker_id}/confirm", response_model=schemas.GameOut)
async def confirm_claim(
    code: str,
    attacker_id: str,
    body: schemas.ConfirmClaimIn,
    pid: str = Depends(player_id),
    uc: ConfirmClaim = Depends(confirm_uc),
    clock: Clock = Depends(get_clock),
) -> schemas.GameOut:
    game = await uc.execute(code, attacker_id, pid, body.confirmed)
    return to_game_out(game, clock.now_ms())


@router.post("/games/{code}/swap-mission", response_model=schemas.GameOut)
async def swap_mission(
    code: str,
    pid: str = Depends(player_id),
    uc: SwapMission = Depends(swap_uc),
    clock: Clock = Depends(get_clock),
) -> schemas.GameOut:
    game = await uc.execute(code, pid)
    return to_game_out(game, clock.now_ms())


@router.post("/games/{code}/end", response_model=schemas.GameOut)
async def end_game(
    code: str,
    pid: str = Depends(player_id),
    uc: EndGame = Depends(end_uc),
    clock: Clock = Depends(get_clock),
) -> schemas.GameOut:
    game = await uc.execute(code, pid)
    return to_game_out(game, clock.now_ms())


@router.delete("/games/{code}/players/me", response_model=schemas.GameOut)
async def leave_game(
    code: str,
    pid: str = Depends(player_id),
    uc: LeaveGame = Depends(leave_uc),
    clock: Clock = Depends(get_clock),
) -> schemas.GameOut:
    game = await uc.execute(code, pid)
    return to_game_out(game, clock.now_ms())


@router.get("/games/{code}", response_model=schemas.GameOut)
async def get_game(
    code: str,
    uc: GetGame = Depends(get_game_uc),
    clock: Clock = Depends(get_clock),
) -> schemas.GameOut:
    game = await uc.execute(code)
    return to_game_out(game, clock.now_ms())
