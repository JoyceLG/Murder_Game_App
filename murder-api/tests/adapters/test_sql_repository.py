"""Integration tests for the SQL adapter.

By default they run on SQLite in-memory (fast, no Docker). Point TEST_DATABASE_URL at a real
Postgres (postgresql+asyncpg://...) to exercise the exact same adapter against the production
backend — the whole point of the port abstraction.
"""

import pytest
import pytest_asyncio

from src.adapters.sql_repository import (
    SqlGameRepository,
    build_engine,
    build_session_factory,
)
from src.domain.errors import ConcurrentUpdate
from src.domain.models import GameStatus, MissionMode, PooledMission
from src.ports.repository import GameRepository
from tests.builders import add_claim, make_game
from tests.sql_support import empty_database

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture
async def repo():
    engine = await empty_database()
    try:
        yield SqlGameRepository(build_session_factory(engine))
    finally:
        await engine.dispose()


async def test_sql_repository_satisfies_repository_port(repo):
    assert isinstance(repo, GameRepository)


async def test_save_then_get_round_trip_with_players_and_claims(repo):
    game = make_game(["alice", "bob"], code="WXYZ", host="alice")
    game.players["alice"].score = 3
    game.players["alice"].mission = "Fais dire « banane »."
    game.players["alice"].target_id = "bob"
    add_claim(game, "alice")

    await repo.save(game)
    loaded = await repo.get("WXYZ")

    assert loaded is not None
    assert loaded.host_id == "alice"
    assert loaded.players["alice"].score == 3
    assert loaded.players["alice"].target_id == "bob"
    assert loaded.players["alice"].mission == "Fais dire « banane »."
    assert loaded.claims["alice"].target == "bob"


async def test_get_unknown_returns_none(repo):
    assert await repo.get("NONE") is None


async def test_exists_and_delete(repo):
    await repo.save(make_game(["a", "b"], code="WXYZ"))
    assert await repo.exists("WXYZ") is True
    await repo.delete("WXYZ")
    assert await repo.exists("WXYZ") is False
    assert await repo.get("WXYZ") is None


async def test_save_replaces_children(repo):
    game = make_game(["a", "b", "c"], code="WXYZ")
    await repo.save(game)
    game.players.pop("c")
    await repo.save(game)
    loaded = await repo.get("WXYZ")
    assert set(loaded.players) == {"a", "b"}


async def test_get_orders_players_by_join_time(repo):
    # Insertion order is non-alphabetical; the adapter must restore join order, not PK order,
    # so it matches the in-memory repository (Game.ranking and host reassignment depend on it).
    game = make_game(["zoe", "amy", "max"], code="WXYZ", host="zoe")
    game.players["zoe"].joined_at = 100
    game.players["amy"].joined_at = 200
    game.players["max"].joined_at = 300
    await repo.save(game)

    loaded = await repo.get("WXYZ")

    assert list(loaded.players) == ["zoe", "amy", "max"]


async def test_config_caps_round_trip(repo):
    game = make_game(["a", "b"], code="WXYZ")
    game.max_players = 6
    game.max_score = 10
    await repo.save(game)
    loaded = await repo.get("WXYZ")
    assert loaded.max_players == 6
    assert loaded.max_score == 10


async def test_default_caps_round_trip(repo):
    await repo.save(make_game(["a", "b"], code="WXYZ"))
    loaded = await repo.get("WXYZ")
    assert loaded.max_players == 12
    assert loaded.max_score is None


async def test_mission_pool_and_mode_round_trip(repo):
    game = make_game(["a", "b"], code="WXYZ")
    game.mission_mode = MissionMode.REPLACE
    game.mission_pool = [
        PooledMission(id="m1", text="Custom A", by="a"),
        PooledMission(id="m2", text="Custom B", by="b"),
    ]
    await repo.save(game)
    loaded = await repo.get("WXYZ")
    assert loaded.mission_mode is MissionMode.REPLACE
    assert [(m.id, m.text, m.by) for m in loaded.mission_pool] == [
        ("m1", "Custom A", "a"),
        ("m2", "Custom B", "b"),
    ]


async def test_default_mission_mode_round_trips(repo):
    await repo.save(make_game(["a", "b"], code="WXYZ"))
    loaded = await repo.get("WXYZ")
    assert loaded.mission_mode is MissionMode.AUGMENT
    assert loaded.mission_pool == []


async def test_status_enum_round_trips(repo):
    game = make_game(["a", "b"], code="WXYZ")
    game.status = GameStatus.RUNNING
    await repo.save(game)
    loaded = await repo.get("WXYZ")
    assert loaded.status is GameStatus.RUNNING


async def test_build_engine_for_postgres_url_uses_postgres_dialect():
    engine = build_engine("postgresql+asyncpg://u:p@localhost:5432/murder")
    assert engine.dialect.name == "postgresql"
    await engine.dispose()


async def test_version_created_at_and_token_digest_round_trip(repo):
    game = make_game(["a", "b"], code="WXYZ")
    game.created_at = 1234
    game.players["a"].token_hash = "f" * 64
    await repo.save(game)
    assert game.version == 1
    loaded = await repo.get("WXYZ")
    assert loaded.version == 1
    assert loaded.created_at == 1234
    assert loaded.players["a"].token_hash == "f" * 64


async def test_save_from_a_stale_copy_is_rejected(repo):
    await repo.save(make_game(["a", "b"], code="WXYZ"))
    first, second = await repo.get("WXYZ"), await repo.get("WXYZ")
    first.players["a"].score = 1
    await repo.save(first)

    second.players.pop("b")  # would have wiped b if the stale write went through
    with pytest.raises(ConcurrentUpdate):
        await repo.save(second)

    loaded = await repo.get("WXYZ")
    assert loaded.players["a"].score == 1
    assert set(loaded.players) == {"a", "b"}
    assert loaded.version == 2


async def test_saving_a_new_game_over_an_existing_code_is_rejected(repo):
    await repo.save(make_game(["a"], code="WXYZ"))
    with pytest.raises(ConcurrentUpdate):
        await repo.save(make_game(["b"], code="WXYZ"))
    assert set((await repo.get("WXYZ")).players) == {"a"}


async def test_saving_a_deleted_game_is_rejected(repo):
    await repo.save(make_game(["a"], code="WXYZ"))
    stale = await repo.get("WXYZ")
    await repo.delete("WXYZ")
    with pytest.raises(ConcurrentUpdate):
        await repo.save(stale)


async def test_delete_created_before(repo):
    old, new = make_game(["a"], code="OLD1"), make_game(["b"], code="NEW1")
    old.created_at, new.created_at = 100, 200
    old.players["a"].target_id = "a"
    add_claim(old, "a")
    old.mission_pool = [PooledMission(id="m1", text="x", by="a")]
    await repo.save(old)
    await repo.save(new)

    assert await repo.delete_created_before(150) == ["OLD1"]
    assert await repo.get("OLD1") is None
    assert await repo.get("NEW1") is not None
    assert await repo.delete_created_before(150) == []
