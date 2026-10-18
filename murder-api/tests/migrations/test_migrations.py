"""Alembic migrations against a real PostgreSQL (the schema prod actually runs).

Each test gets its own throwaway database and drives Alembic through its CLI, exactly like the
Docker entrypoint does (`alembic upgrade head` with DATABASE_URL in the environment).
"""

import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from src.adapters.sql_repository import SqlGameRepository, build_engine, build_session_factory
from tests.sql_support import TEST_DATABASE_URL, postgres_only

pytestmark = [pytest.mark.integration, pytest.mark.postgres, postgres_only]

API_DIR = Path(__file__).resolve().parents[2]


@pytest_asyncio.fixture
async def database_url():
    """A brand-new empty database on the test server; dropped afterwards."""
    name = f"murder_mig_{uuid.uuid4().hex[:10]}"
    admin = create_async_engine(
        make_url(TEST_DATABASE_URL).set(database="postgres"), isolation_level="AUTOCOMMIT"
    )
    async with admin.connect() as conn:
        await conn.execute(text(f'CREATE DATABASE "{name}"'))
    try:
        yield make_url(TEST_DATABASE_URL).set(database=name).render_as_string(hide_password=False)
    finally:
        async with admin.connect() as conn:
            await conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        await admin.dispose()


def alembic(url: str, *args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "DATABASE_URL": url}
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=API_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def ok(result: subprocess.CompletedProcess[str]) -> str:
    assert result.returncode == 0, result.stderr
    return result.stdout + result.stderr


async def scalar(url: str, sql: str):
    engine = build_engine(url)
    try:
        async with engine.connect() as conn:
            return (await conn.execute(text(sql))).scalar()
    finally:
        await engine.dispose()


async def test_upgrade_head_matches_the_models(database_url):
    ok(alembic(database_url, "upgrade", "head"))
    assert "No new upgrade operations detected" in ok(alembic(database_url, "check"))


async def test_full_downgrade_and_upgrade_round_trip(database_url):
    ok(alembic(database_url, "upgrade", "head"))
    ok(alembic(database_url, "downgrade", "base"))
    assert await scalar(database_url, "SELECT to_regclass('public.games')") is None
    ok(alembic(database_url, "upgrade", "head"))
    assert "No new upgrade operations detected" in ok(alembic(database_url, "check"))


async def test_0002_keeps_existing_games_playable(database_url):
    """A game stored before 0002 survives it and can still be loaded and saved."""
    ok(alembic(database_url, "upgrade", "0001_initial"))
    engine = build_engine(database_url)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO games VALUES ('OLD1', 'h', 'running', 900, 1, 2, 12, NULL, 'augment')"
            )
        )
        await conn.execute(
            text("INSERT INTO players VALUES ('OLD1', 'h', 'Host', 3, 'm', NULL, 1)")
        )
    await engine.dispose()
    before = int(time.time() * 1000)

    ok(alembic(database_url, "upgrade", "head"))

    engine = build_engine(database_url)
    try:
        repo = SqlGameRepository(build_session_factory(engine))
        game = await repo.get("OLD1")
        assert game.version == 1  # a loaded game must be saveable (version 0 means "new")
        assert game.created_at >= before  # stamped, so the first purge does not delete it
        assert game.players["h"].score == 3
        assert game.players["h"].token_hash == ""  # old sessions cannot authenticate

        game.players["h"].score = 4
        await repo.save(game)
        assert (await repo.get("OLD1")).players["h"].score == 4
    finally:
        await engine.dispose()
