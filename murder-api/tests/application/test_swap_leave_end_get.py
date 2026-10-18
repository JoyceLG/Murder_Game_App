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


async def test_swap_mission_rerolls_and_publishes(repo, clock, picker, notifier):
    game = make_running(clock, picker)
    old_mission = game.players["h"].mission
    await repo.save(game)
    uc = SwapMission(repo=repo, clock=clock, picker=picker, notifier=notifier)

    result = await uc.execute("ABCD", "h")

    assert result.players["h"].mission != old_mission
    assert result.players["h"].score == 0  # the one free swap at 0 points
    assert (await repo.get("ABCD")).players["h"].free_swap_used  # persisted
    assert len(notifier.published) == 1


async def test_swap_mission_on_non_running_raises(repo, clock, picker, notifier):
    await repo.save(make_game(["h", "p2"], code="ABCD", host="h"))
    uc = SwapMission(repo=repo, clock=clock, picker=picker, notifier=notifier)
    with pytest.raises(GameNotRunning):
        await uc.execute("ABCD", "h")


# --- LeaveGame -------------------------------------------------------------------------


def _leave(repo, clock, picker, notifier) -> LeaveGame:
    return LeaveGame(repo=repo, clock=clock, picker=picker, notifier=notifier)


async def test_leave_game_removes_player_and_publishes(repo, clock, picker, notifier):
    await repo.save(make_game(["h", "p2", "p3"], code="ABCD", host="h"))

    result = await _leave(repo, clock, picker, notifier).execute("ABCD", "p2")

    assert set(result.players) == {"h", "p3"}
    assert len(notifier.published) == 1
    assert "p2" not in (await repo.get("ABCD")).players


async def test_leave_game_last_player_deletes_game_and_disconnects_watchers(
    repo, clock, picker, notifier
):
    await repo.save(make_game(["solo"], code="ABCD", host="solo"))
    await _leave(repo, clock, picker, notifier).execute("ABCD", "solo")
    assert await repo.get("ABCD") is None
    assert notifier.closed == ["ABCD"]


async def test_leave_game_host_reassigns_host(repo, clock, picker, notifier):
    await repo.save(make_game(["h", "p2"], code="ABCD", host="h"))
    result = await _leave(repo, clock, picker, notifier).execute("ABCD", "h")
    assert result.host_id == "p2"


async def test_leave_during_running_hands_the_leavers_target_to_their_hunter(
    repo, clock, picker, notifier
):
    # FirstPicker keeps insertion order, so the ring is h -> p2 -> p3 -> h.
    game = make_running(clock, picker)
    assert game.players["p3"].target_id == "h"
    await repo.save(game)

    result = await _leave(repo, clock, picker, notifier).execute("ABCD", "h")

    # h's hunter (p3) inherits h's target (p2): the ring closes as p2 <-> p3.
    assert result.players["p3"].target_id == "p2"
    assert result.players["p2"].target_id == "p3"


async def test_leave_game_drops_claims_targeting_the_leaver(repo, clock, picker, notifier):
    game = make_running(clock, picker)
    game.claims["h"] = Claim(
        atk="h", atk_name="H", target="p2", mission="m", status=ClaimStatus.PENDING
    )
    await repo.save(game)
    result = await _leave(repo, clock, picker, notifier).execute("ABCD", "p2")
    assert "h" not in result.claims


async def test_leaving_keeps_a_resolved_claim_for_the_attacker_to_acknowledge(
    repo, clock, picker, notifier
):
    game = make_running(clock, picker)  # ring h -> p2 -> p3 -> h
    game.claims["h"] = Claim(atk="h", atk_name="H", target="p2", mission="m", status=ClaimStatus.OK)
    await repo.save(game)
    result = await _leave(repo, clock, picker, notifier).execute("ABCD", "p2")
    assert result.claims["h"].status is ClaimStatus.OK


async def test_leave_an_ended_game_keeps_the_player_in_the_final_ranking(
    repo, clock, picker, notifier
):
    game = make_running(clock, picker)
    game.status = GameStatus.ENDED
    game.players["p2"].score = 4
    await repo.save(game)

    result = await _leave(repo, clock, picker, notifier).execute("ABCD", "p2")

    assert "p2" in result.players
    stored = await repo.get("ABCD")
    assert [p.id for p in stored.ranking()][0] == "p2"
    assert notifier.published == []


async def test_last_player_leaving_an_ended_game_does_not_delete_it(repo, clock, picker, notifier):
    game = make_game(["solo"], code="ABCD", host="solo", status=GameStatus.ENDED)
    await repo.save(game)
    await _leave(repo, clock, picker, notifier).execute("ABCD", "solo")
    assert await repo.get("ABCD") is not None


async def test_leave_after_the_clock_ran_out_settles_the_end_and_keeps_the_player(
    repo, clock, picker, notifier
):
    game = make_running(clock, picker)
    game.end_at = clock.now_ms() - 1
    await repo.save(game)

    result = await _leave(repo, clock, picker, notifier).execute("ABCD", "p2")

    assert result.status is GameStatus.ENDED
    assert "p2" in result.players
    assert len(notifier.published) == 1  # the end itself is broadcast


# --- EndGame ---------------------------------------------------------------------------


def _end(repo, clock, notifier) -> EndGame:
    return EndGame(repo=repo, clock=clock, notifier=notifier)


async def test_end_game_by_host_sets_ended_and_publishes(repo, clock, picker, notifier):
    await repo.save(make_running(clock, picker))
    result = await _end(repo, clock, notifier).execute("ABCD", "h")
    assert result.status is GameStatus.ENDED
    assert len(notifier.published) == 1


async def test_end_game_by_non_host_raises(repo, clock, picker, notifier):
    await repo.save(make_running(clock, picker))
    with pytest.raises(NotTheHost):
        await _end(repo, clock, notifier).execute("ABCD", "p2")


async def test_end_game_in_lobby_raises_not_running(repo, clock, notifier):
    await repo.save(make_game(["h", "p2"], code="ABCD", host="h"))
    with pytest.raises(GameNotRunning):
        await _end(repo, clock, notifier).execute("ABCD", "h")
    assert notifier.published == []


async def test_end_game_already_ended_raises_not_running(repo, clock, notifier):
    await repo.save(make_game(["h", "p2"], code="ABCD", host="h", status=GameStatus.ENDED))
    with pytest.raises(GameNotRunning):
        await _end(repo, clock, notifier).execute("ABCD", "h")
    assert notifier.published == []


# --- GetGame (lazy auto-end) -----------------------------------------------------------


async def test_get_game_marks_ended_when_time_up_and_broadcasts_it(repo, clock, picker, notifier):
    game = make_running(clock, picker)
    game.end_at = clock.now_ms() - 1  # already expired
    await repo.save(game)

    result = await GetGame(repo=repo, clock=clock, notifier=notifier).execute("ABCD")

    assert result.status is GameStatus.ENDED
    assert (await repo.get("ABCD")).status is GameStatus.ENDED  # persisted
    assert [g.status for g in notifier.published] == [GameStatus.ENDED]


async def test_get_game_running_not_expired_stays_running_and_is_silent(
    repo, clock, picker, notifier
):
    await repo.save(make_running(clock, picker))
    result = await GetGame(repo=repo, clock=clock, notifier=notifier).execute("ABCD")
    assert result.status is GameStatus.RUNNING
    assert notifier.published == []


async def test_get_game_marks_ended_when_score_cap_reached(repo, clock, picker, notifier):
    game = make_running(clock, picker)  # clock not expired
    game.max_score = 3
    game.players["h"].score = 3
    await repo.save(game)

    result = await GetGame(repo=repo, clock=clock, notifier=notifier).execute("ABCD")

    assert result.status is GameStatus.ENDED
    assert (await repo.get("ABCD")).status is GameStatus.ENDED  # persisted


async def test_get_game_unknown_raises_game_not_found(repo, clock, notifier):
    with pytest.raises(GameNotFound):
        await GetGame(repo=repo, clock=clock, notifier=notifier).execute("NOPE")


async def test_last_player_standing_in_a_running_game_sees_the_end(repo, clock, picker, notifier):
    await repo.save(make_running(clock, picker, player_ids=("h", "p2")))
    result = await _leave(repo, clock, picker, notifier).execute("ABCD", "p2")
    assert result.status is GameStatus.ENDED
    assert (await repo.get("ABCD")).status is GameStatus.ENDED
    assert notifier.published[-1].status is GameStatus.ENDED
