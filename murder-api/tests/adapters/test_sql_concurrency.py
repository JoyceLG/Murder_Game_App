"""Optimistic locking under real concurrency (PostgreSQL only).

The API serializes requests per game with an in-process lock, which only covers one worker.
These tests take that lock away and hammer the repository from separate connections, the way
several workers (or a misbehaving client) would: no write may be lost, and no request may fail
with anything but a clean ConcurrentUpdate (HTTP 409).
"""

import asyncio
from contextlib import asynccontextmanager

import httpx
import pytest
import pytest_asyncio

from src.adapters.sql_repository import SqlGameRepository, build_session_factory
from src.api.config import Settings
from src.api.main import create_app
from src.domain.errors import ConcurrentUpdate
from tests.builders import make_game
from tests.sql_support import empty_database, postgres_only

pytestmark = [pytest.mark.integration, pytest.mark.postgres, postgres_only]


@pytest_asyncio.fixture
async def engine():
    engine = await empty_database()
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def repo(engine):
    return SqlGameRepository(build_session_factory(engine))


async def test_two_writers_from_the_same_version_only_one_wins(repo):
    await repo.save(make_game(["a", "b"], code="RACE"))
    first, second = await repo.get("RACE"), await repo.get("RACE")
    first.players["a"].score = 1
    second.players["b"].score = 1

    results = await asyncio.gather(repo.save(first), repo.save(second), return_exceptions=True)

    assert sorted(type(r).__name__ for r in results) == ["ConcurrentUpdate", "NoneType"]
    stored = await repo.get("RACE")
    winner = first if results[0] is None else second
    assert {p.id: p.score for p in stored.players.values()} == {
        p.id: p.score for p in winner.players.values()
    }
    assert stored.version == 2


async def test_read_modify_write_with_retry_loses_no_update(repo):
    """20 concurrent "+1" writers, each retrying on conflict: the final score is exactly 20."""
    await repo.save(make_game(["a"], code="CNTR"))

    async def increment() -> int:
        for attempt in range(1, 200):
            game = await repo.get("CNTR")
            game.players["a"].score += 1
            try:
                await repo.save(game)
                return attempt
            except ConcurrentUpdate:
                await asyncio.sleep(0)
        raise AssertionError("gave up")

    attempts = await asyncio.gather(*(increment() for _ in range(20)))

    stored = await repo.get("CNTR")
    assert stored.players["a"].score == 20
    assert stored.version == 21
    assert max(attempts) > 1  # the race really happened


class _NoLock:
    """Stands in for GameLocks to simulate several workers (no shared in-process lock)."""

    @asynccontextmanager
    async def hold(self, code):
        yield


async def test_without_the_app_lock_conflicts_are_clean_409s_and_nothing_is_lost(engine):
    app = create_app(
        repo=SqlGameRepository(build_session_factory(engine)),
        settings=Settings(rate_limit_per_minute=0, create_rate_limit_per_minute=0),
    )
    app.state.locks = _NoLock()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        code = (await http.post("/games", json={"host_name": "Host"})).json()["code"]
        responses = await asyncio.gather(
            *(http.post(f"/games/{code}/players", json={"name": f"P{i}"}) for i in range(8))
        )
        state = (await http.get(f"/games/{code}")).json()

    statuses = [r.status_code for r in responses]
    assert set(statuses) <= {201, 409}, statuses  # never a 500 / IntegrityError
    assert all(r.json()["error"] == "ConcurrentUpdate" for r in responses if r.status_code == 409)
    joined = {r.json()["player_id"] for r in responses if r.status_code == 201}
    assert joined <= {p["id"] for p in state["players"]}  # every 201 really is in the game
    assert len(state["players"]) == 1 + len(joined)
