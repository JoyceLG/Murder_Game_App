import pytest

from src.application.start_game import StartGame
from src.domain.errors import GameAlreadyStarted, NotEnoughPlayers, NotTheHost
from src.domain.models import GameStatus
from tests.builders import make_game


async def test_start_game_assigns_targets_and_sets_running_and_end_at(
    repo, clock, picker, notifier
):
    await repo.save(make_game(["h", "p2"], code="ABCD", host="h"))
    uc = StartGame(repo=repo, clock=clock, picker=picker, notifier=notifier)

    game = await uc.execute("ABCD", "h", 15)

    assert game.status is GameStatus.RUNNING
    assert game.duration_sec == 15 * 60
    assert game.start_at == clock.now_ms()
    assert game.end_at == clock.now_ms() + 15 * 60 * 1000
    for player in game.players.values():
        assert player.target_id is not None
        assert player.target_id != player.id
    assert len(notifier.published) == 1


async def test_start_by_non_host_raises_not_the_host(repo, clock, picker, notifier):
    await repo.save(make_game(["h", "p2"], code="ABCD", host="h"))
    uc = StartGame(repo=repo, clock=clock, picker=picker, notifier=notifier)
    with pytest.raises(NotTheHost):
        await uc.execute("ABCD", "p2", 15)


async def test_start_with_one_player_raises_not_enough_players(repo, clock, picker, notifier):
    await repo.save(make_game(["h"], code="ABCD", host="h"))
    uc = StartGame(repo=repo, clock=clock, picker=picker, notifier=notifier)
    with pytest.raises(NotEnoughPlayers):
        await uc.execute("ABCD", "h", 15)


async def test_start_twice_raises_already_started(repo, clock, picker, notifier):
    await repo.save(make_game(["h", "p2"], code="ABCD", host="h"))
    uc = StartGame(repo=repo, clock=clock, picker=picker, notifier=notifier)
    await uc.execute("ABCD", "h", 15)
    with pytest.raises(GameAlreadyStarted):
        await uc.execute("ABCD", "h", 15)


@pytest.mark.parametrize(("requested", "expected_sec"), [(0, 60), (999, 240 * 60), (15, 15 * 60)])
async def test_start_clamps_duration(repo, clock, picker, notifier, requested, expected_sec):
    await repo.save(make_game(["h", "p2"], code="ABCD", host="h"))
    uc = StartGame(repo=repo, clock=clock, picker=picker, notifier=notifier)
    game = await uc.execute("ABCD", "h", requested)
    assert game.duration_sec == expected_sec
