import pytest

from src.application.update_config import UpdateGameConfig
from src.domain.errors import GameAlreadyStarted, InvalidGameConfig, NotTheHost
from src.domain.models import GameStatus, MissionMode
from tests.builders import make_game

AUGMENT = MissionMode.AUGMENT


async def test_update_config_sets_caps_and_publishes(repo, notifier):
    await repo.save(make_game(["h", "p2"], code="ABCD", host="h"))
    uc = UpdateGameConfig(repo=repo, notifier=notifier)

    result = await uc.execute("ABCD", "h", max_players=6, max_score=5, mission_mode=AUGMENT)

    assert result.max_players == 6
    assert result.max_score == 5
    assert len(notifier.published) == 1
    stored = await repo.get("ABCD")
    assert stored.max_players == 6
    assert stored.max_score == 5


async def test_update_config_sets_mission_mode(repo, notifier):
    await repo.save(make_game(["h", "p2"], code="ABCD", host="h"))
    uc = UpdateGameConfig(repo=repo, notifier=notifier)
    result = await uc.execute(
        "ABCD", "h", max_players=12, max_score=None, mission_mode=MissionMode.REPLACE
    )
    assert result.mission_mode is MissionMode.REPLACE
    assert (await repo.get("ABCD")).mission_mode is MissionMode.REPLACE


async def test_update_config_allows_clearing_score_cap(repo, notifier):
    await repo.save(make_game(["h", "p2"], code="ABCD", host="h"))
    uc = UpdateGameConfig(repo=repo, notifier=notifier)
    result = await uc.execute("ABCD", "h", max_players=12, max_score=None, mission_mode=AUGMENT)
    assert result.max_score is None


async def test_update_config_by_non_host_raises(repo, notifier):
    await repo.save(make_game(["h", "p2"], code="ABCD", host="h"))
    uc = UpdateGameConfig(repo=repo, notifier=notifier)
    with pytest.raises(NotTheHost):
        await uc.execute("ABCD", "p2", max_players=6, max_score=5, mission_mode=AUGMENT)


async def test_update_config_after_start_raises(repo, notifier):
    game = make_game(["h", "p2"], code="ABCD", host="h")
    game.status = GameStatus.RUNNING
    await repo.save(game)
    uc = UpdateGameConfig(repo=repo, notifier=notifier)
    with pytest.raises(GameAlreadyStarted):
        await uc.execute("ABCD", "h", max_players=6, max_score=5, mission_mode=AUGMENT)


async def test_update_config_cap_below_current_players_raises(repo, notifier):
    await repo.save(make_game(["h", "p2", "p3"], code="ABCD", host="h"))
    uc = UpdateGameConfig(repo=repo, notifier=notifier)
    with pytest.raises(InvalidGameConfig):
        await uc.execute("ABCD", "h", max_players=2, max_score=None, mission_mode=AUGMENT)
