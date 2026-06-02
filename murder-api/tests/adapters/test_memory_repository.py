from src.adapters.memory_repository import InMemoryGameRepository
from tests.builders import make_game


async def test_save_then_get_round_trip():
    repo = InMemoryGameRepository()
    await repo.save(make_game(["a", "b"], code="WXYZ"))
    loaded = await repo.get("WXYZ")
    assert loaded is not None
    assert loaded.code == "WXYZ"
    assert set(loaded.players) == {"a", "b"}


async def test_get_unknown_returns_none():
    repo = InMemoryGameRepository()
    assert await repo.get("NONE") is None


async def test_exists_reflects_save_and_delete():
    repo = InMemoryGameRepository()
    assert await repo.exists("WXYZ") is False
    await repo.save(make_game(["a", "b"], code="WXYZ"))
    assert await repo.exists("WXYZ") is True
    await repo.delete("WXYZ")
    assert await repo.exists("WXYZ") is False


async def test_get_returns_detached_copy():
    repo = InMemoryGameRepository()
    await repo.save(make_game(["a", "b"], code="WXYZ"))
    loaded = await repo.get("WXYZ")
    loaded.players["a"].score = 99  # mutate the copy, not the store
    reloaded = await repo.get("WXYZ")
    assert reloaded.players["a"].score == 0


async def test_delete_unknown_is_noop():
    repo = InMemoryGameRepository()
    await repo.delete("NONE")  # must not raise
