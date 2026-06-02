import pytest

from src.application.end_game import EndGame
from src.application.get_game import GetGame
from src.application.leave_game import LeaveGame
from src.application.swap_mission import SwapMission
from src.domain.errors import GameNotFound, GameNotRunning, NotTheHost
from src.domain.models import Claim, ClaimStatus, GameStatus
from tests.application.conftest import make_running
from tests.builders import make_game

# --- SwapMission -----------------------------------------------------------------------


async def test_swap_mission_rerolls_and_penalizes_and_publishes(repo, clock, picker, notifier):
    game = make_running(clock, picker)
    old_mission = game.players["h"].mission
    await repo.save(game)
    uc = SwapMission(repo=repo, clock=clock, picker=picker, notifier=notifier)

    result = await uc.execute("ABCD", "h")

    assert result.players["h"].mission != old_mission
    assert result.players["h"].score == -1
    assert len(notifier.published) == 1


async def test_swap_mission_on_non_running_raises(repo, clock, picker, notifier):
    await repo.save(make_game(["h", "p2"], code="ABCD", host="h"))
    uc = SwapMission(repo=repo, clock=clock, picker=picker, notifier=notifier)
    with pytest.raises(GameNotRunning):
        await uc.execute("ABCD", "h")


# --- LeaveGame -------------------------------------------------------------------------


async def test_leave_game_removes_player_and_publishes(repo, picker, notifier):
    await repo.save(make_game(["h", "p2", "p3"], code="ABCD", host="h"))
    uc = LeaveGame(repo=repo, picker=picker, notifier=notifier)

    result = await uc.execute("ABCD", "p2")

    assert set(result.players) == {"h", "p3"}
    assert len(notifier.published) == 1
    assert "p2" not in (await repo.get("ABCD")).players


async def test_leave_game_last_player_deletes_game(repo, picker, notifier):
    await repo.save(make_game(["solo"], code="ABCD", host="solo"))
    uc = LeaveGame(repo=repo, picker=picker, notifier=notifier)
    await uc.execute("ABCD", "solo")
    assert await repo.get("ABCD") is None


async def test_leave_game_host_reassigns_host(repo, picker, notifier):
    await repo.save(make_game(["h", "p2"], code="ABCD", host="h"))
    uc = LeaveGame(repo=repo, picker=picker, notifier=notifier)
    result = await uc.execute("ABCD", "h")
    assert result.host_id == "p2"


async def test_leave_during_running_reassigns_hunters_of_the_leaver(repo, clock, picker, notifier):
    # FirstPicker assigns each player the first candidate != self: h->p2, p2->h, p3->h.
    game = make_running(clock, picker)
    assert game.players["p2"].target_id == "h"  # p2 and p3 both hunt h
    assert game.players["p3"].target_id == "h"
    await repo.save(game)

    result = await LeaveGame(repo=repo, picker=picker, notifier=notifier).execute("ABCD", "h")

    ids = set(result.players)
    assert "h" not in ids
    for pid in ids:  # nobody is left hunting the player who left
        target = result.players[pid].target_id
        assert target is None or target in ids


async def test_leave_game_drops_claims_targeting_the_leaver(repo, clock, picker, notifier):
    game = make_running(clock, picker)
    game.claims["p3"] = Claim(
        atk="p3", atk_name="P3", target="p2", mission="m", status=ClaimStatus.PENDING
    )
    await repo.save(game)
    uc = LeaveGame(repo=repo, picker=picker, notifier=notifier)
    result = await uc.execute("ABCD", "p2")
    assert "p3" not in result.claims


# --- EndGame ---------------------------------------------------------------------------


async def test_end_game_by_host_sets_ended_and_publishes(repo, clock, picker, notifier):
    await repo.save(make_running(clock, picker))
    uc = EndGame(repo=repo, notifier=notifier)
    result = await uc.execute("ABCD", "h")
    assert result.status is GameStatus.ENDED
    assert len(notifier.published) == 1


async def test_end_game_by_non_host_raises(repo, clock, picker, notifier):
    await repo.save(make_running(clock, picker))
    uc = EndGame(repo=repo, notifier=notifier)
    with pytest.raises(NotTheHost):
        await uc.execute("ABCD", "p2")


# --- GetGame (lazy auto-end) -----------------------------------------------------------


async def test_get_game_marks_ended_when_time_up(repo, clock, picker):
    game = make_running(clock, picker)
    game.end_at = clock.now_ms() - 1  # already expired
    await repo.save(game)
    uc = GetGame(repo=repo, clock=clock)

    result = await uc.execute("ABCD")

    assert result.status is GameStatus.ENDED
    assert (await repo.get("ABCD")).status is GameStatus.ENDED  # persisted


async def test_get_game_running_not_expired_stays_running(repo, clock, picker):
    await repo.save(make_running(clock, picker))
    uc = GetGame(repo=repo, clock=clock)
    result = await uc.execute("ABCD")
    assert result.status is GameStatus.RUNNING


async def test_get_game_unknown_raises_game_not_found(repo, clock):
    uc = GetGame(repo=repo, clock=clock)
    with pytest.raises(GameNotFound):
        await uc.execute("NOPE")
