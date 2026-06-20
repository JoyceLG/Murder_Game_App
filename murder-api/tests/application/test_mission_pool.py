import pytest

from src.application.add_mission_to_pool import AddMissionToPool
from src.application.remove_mission_from_pool import RemoveMissionFromPool
from src.domain.errors import (
    GameAlreadyStarted,
    InvalidMission,
    MissionNotFound,
    NotAllowedToRemoveMission,
    PlayerNotFound,
)
from src.domain.models import GameStatus
from tests.builders import make_game
from tests.doubles import SequenceIds


def _add(repo, notifier, ids="m1"):
    return AddMissionToPool(repo=repo, ids=SequenceIds(ids), notifier=notifier)


# --- AddMissionToPool ------------------------------------------------------------------


async def test_add_mission_appends_trimmed_and_tags_author(repo, notifier):
    await repo.save(make_game(["h", "p2"], code="ABCD", host="h"))

    result = await _add(repo, notifier).execute("ABCD", "p2", "  Fais un clin d'œil  ")

    assert len(result.mission_pool) == 1
    item = result.mission_pool[0]
    assert (item.id, item.text, item.by) == ("m1", "Fais un clin d'œil", "p2")
    assert len(notifier.published) == 1


async def test_add_mission_rejects_blank(repo, notifier):
    await repo.save(make_game(["h"], code="ABCD", host="h"))
    with pytest.raises(InvalidMission):
        await _add(repo, notifier).execute("ABCD", "h", "   ")


async def test_add_mission_after_start_raises(repo, notifier):
    game = make_game(["h", "p2"], code="ABCD", host="h")
    game.status = GameStatus.RUNNING
    await repo.save(game)
    with pytest.raises(GameAlreadyStarted):
        await _add(repo, notifier).execute("ABCD", "h", "x")


async def test_add_mission_by_non_member_raises(repo, notifier):
    await repo.save(make_game(["h"], code="ABCD", host="h"))
    with pytest.raises(PlayerNotFound):
        await _add(repo, notifier).execute("ABCD", "ghost", "x")


async def test_add_mission_rejects_when_pool_is_full(repo, notifier):
    from src.application.add_mission_to_pool import MAX_POOL_SIZE
    from src.domain.models import PooledMission

    game = make_game(["h"], code="ABCD", host="h")
    game.mission_pool = [
        PooledMission(id=str(i), text=f"m{i}", by="h") for i in range(MAX_POOL_SIZE)
    ]
    await repo.save(game)
    with pytest.raises(InvalidMission):
        await _add(repo, notifier).execute("ABCD", "h", "one too many")


# --- RemoveMissionFromPool -------------------------------------------------------------


async def test_remove_mission_by_author(repo, notifier):
    await repo.save(make_game(["h", "p2"], code="ABCD", host="h"))
    await _add(repo, notifier).execute("ABCD", "p2", "Custom")
    result = await RemoveMissionFromPool(repo=repo, notifier=notifier).execute("ABCD", "p2", "m1")
    assert result.mission_pool == []


async def test_remove_mission_by_host_even_if_not_author(repo, notifier):
    await repo.save(make_game(["h", "p2"], code="ABCD", host="h"))
    await _add(repo, notifier).execute("ABCD", "p2", "Custom")
    result = await RemoveMissionFromPool(repo=repo, notifier=notifier).execute("ABCD", "h", "m1")
    assert result.mission_pool == []


async def test_remove_mission_by_other_player_raises(repo, notifier):
    await repo.save(make_game(["h", "p2", "p3"], code="ABCD", host="h"))
    await _add(repo, notifier).execute("ABCD", "p2", "Custom")
    with pytest.raises(NotAllowedToRemoveMission):
        await RemoveMissionFromPool(repo=repo, notifier=notifier).execute("ABCD", "p3", "m1")


async def test_remove_unknown_mission_raises(repo, notifier):
    await repo.save(make_game(["h"], code="ABCD", host="h"))
    with pytest.raises(MissionNotFound):
        await RemoveMissionFromPool(repo=repo, notifier=notifier).execute("ABCD", "h", "nope")
