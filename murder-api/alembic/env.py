"""Alembic migration environment (async, SQLAlchemy 2.0 + asyncpg).

The URL is resolved from the app's own settings (DATABASE_URL) so migrations and
the running API always target the same database — no second source of truth.
`target_metadata` is the live `Base.metadata`, which makes `alembic revision
--autogenerate` diff future model changes against the recorded schema.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# `prepend_sys_path = .` in alembic.ini puts the project root (murder-api/) on the
# path, so `src` imports resolve whether alembic runs locally or in the container.
from src.adapters.sql_repository import Base
from src.api.config import get_settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    """Single source for the URL: DATABASE_URL via Settings, else alembic.ini."""
    url = get_settings().database_url or config.get_main_option("sqlalchemy.url")
    if not url:
        raise RuntimeError(
            "No database URL: set DATABASE_URL (or sqlalchemy.url) to run migrations."
        )
    return url


def run_migrations_offline() -> None:
    """Emit SQL to stdout without a DBAPI connection (`alembic upgrade --sql`)."""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations against a live async engine built from DATABASE_URL."""
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = _database_url()
    engine = async_engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with engine.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
