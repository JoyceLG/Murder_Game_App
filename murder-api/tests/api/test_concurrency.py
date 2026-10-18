"""B1 regression: concurrent requests on one game against the real SQL adapter.

Before the per-game lock + optimistic versioning, five simultaneous joins on the SQL adapter
raised `IntegrityError: UNIQUE constraint failed: players...` and then hung; on PostgreSQL a
player could get a 201 and still be missing from the game (last write wins). Runs on SQLite by
default and on PostgreSQL when TEST_DATABASE_URL points at one (as in CI).
"""

import asyncio

import httpx
import pytest
import pytest_asyncio

from src.adapters.sql_repository import SqlGameRepository, build_session_factory
from src.api.config import Settings
from src.api.main import create_app
from tests.sql_support import empty_database

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture
async def http():
    engine = await empty_database()
    app = create_app(
        repo=SqlGameRepository(build_session_factory(engine)),
        settings=Settings(rate_limit_per_minute=0, create_rate_limit_per_minute=0),
    )
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield client
    finally:
        await engine.dispose()


async def test_parallel_joins_all_land_in_the_game(http):
    code = (await http.post("/games", json={"host_name": "Host"})).json()["code"]

    responses = await asyncio.gather(
        *(http.post(f"/games/{code}/players", json={"name": f"P{i}"}) for i in range(5))
    )

    assert [r.status_code for r in responses] == [201] * 5
    state = (await http.get(f"/games/{code}")).json()
    assert {p["name"] for p in state["players"]} == {"Host", "P0", "P1", "P2", "P3", "P4"}
    assert state["version"] == 6  # 1 create + 5 joins, none lost


async def test_parallel_pool_additions_are_all_kept(http):
    body = (await http.post("/games", json={"host_name": "Host"})).json()
    code = body["code"]
    headers = {"X-Player-Id": body["player_id"], "X-Player-Token": body["player_token"]}

    responses = await asyncio.gather(
        *(
            http.post(f"/games/{code}/missions", json={"text": f"Mission {i}"}, headers=headers)
            for i in range(5)
        )
    )

    assert [r.status_code for r in responses] == [200] * 5
    pool = (await http.get(f"/games/{code}")).json()["mission_pool"]
    assert sorted(m["text"] for m in pool) == [f"Mission {i}" for i in range(5)]
