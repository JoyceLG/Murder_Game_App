"""Shared setup for tests that hit a real SQL database.

SQLite in-memory (the default) starts empty for every engine, but a PostgreSQL test database
(TEST_DATABASE_URL, as in CI) keeps its rows between tests. Each test therefore starts from
empty tables, otherwise a game saved by one test would collide with the next one's.
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from src.adapters.sql_repository import Base, build_engine, create_all

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
ON_POSTGRES = TEST_DATABASE_URL.startswith("postgresql")

# For tests that need what only a real server gives: separate connections running truly
# concurrent transactions, CREATE DATABASE, Alembic migrations. Run with `make test-pg`.
postgres_only = pytest.mark.skipif(
    not ON_POSTGRES, reason="needs PostgreSQL: set TEST_DATABASE_URL (make test-pg)"
)


async def empty_database() -> AsyncEngine:
    """An engine on the test database with the schema present and every table empty."""
    engine = build_engine(TEST_DATABASE_URL)
    await create_all(engine)
    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())
    return engine
