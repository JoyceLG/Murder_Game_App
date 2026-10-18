"""FastAPI application assembly and dependency wiring.

`create_app` is the composition root: it chooses concrete adapters and stores them on app.state.
Tests build their own app with in-memory adapters; production uses the defaults here.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncEngine

from src.adapters.identifiers import RandomCodeGenerator, TokenGenerator, UuidGenerator
from src.adapters.memory_repository import InMemoryGameRepository
from src.adapters.sql_repository import (
    SqlGameRepository,
    build_engine,
    build_session_factory,
)
from src.adapters.system_clock import SystemClock
from src.api import routes, websocket
from src.api.config import Settings, get_settings
from src.api.errors import register_error_handlers
from src.api.locks import GameLocks
from src.api.rate_limit import RateLimiter
from src.api.ws_notifier import WebSocketNotifier
from src.application.purge_stale_games import PurgeStaleGames
from src.domain.randomness import Picker, RandomPicker
from src.ports.clock import Clock
from src.ports.identifiers import CodeGenerator, IdGenerator, SecretGenerator
from src.ports.notifier import RealtimeNotifier
from src.ports.repository import GameRepository

logger = logging.getLogger(__name__)


async def _purge_forever(purge: PurgeStaleGames, every_sec: int) -> None:
    while True:
        await asyncio.sleep(every_sec)
        try:
            purged = await purge.execute()
            if purged:
                logger.info("purged %d stale game(s)", len(purged))
        except Exception:  # keep sweeping even if one pass fails (e.g. DB briefly down)
            logger.exception("stale-game purge failed")


@asynccontextmanager
async def _lifespan(app: FastAPI):
    # Schema is owned by Alembic, applied before startup by docker-entrypoint.sh
    # (`alembic upgrade head`). For local Postgres runs, run that command once
    # yourself. Tests create their schema directly via sql_repository.create_all.
    settings: Settings = app.state.settings
    purge = PurgeStaleGames(
        repo=app.state.repo,
        clock=app.state.clock,
        notifier=app.state.notifier,
        ttl_ms=settings.game_ttl_hours * 3_600_000,
    )
    sweeper = asyncio.create_task(_purge_forever(purge, settings.purge_interval_sec))
    yield
    sweeper.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await sweeper
    engine: AsyncEngine | None = app.state.engine
    if engine is not None:
        await engine.dispose()


def create_app(
    *,
    repo: GameRepository | None = None,
    clock: Clock | None = None,
    ids: IdGenerator | None = None,
    secrets: SecretGenerator | None = None,
    codes: CodeGenerator | None = None,
    picker: Picker | None = None,
    notifier: RealtimeNotifier | None = None,
    settings: Settings | None = None,
) -> FastAPI:
    app = FastAPI(title="Murder API", version="0.1.0", lifespan=_lifespan)
    settings = settings or get_settings()

    engine: AsyncEngine | None = None
    if repo is None:
        repo, engine = _build_repo(settings)
    app.state.engine = engine

    clock = clock or SystemClock()
    app.state.settings = settings
    app.state.repo = repo
    app.state.clock = clock
    app.state.ids = ids or UuidGenerator()
    app.state.secrets = secrets or TokenGenerator()
    app.state.codes = codes or RandomCodeGenerator()
    app.state.picker = picker or RandomPicker()
    app.state.notifier = notifier or WebSocketNotifier(clock)
    app.state.locks = GameLocks()
    app.state.rate_limiter = RateLimiter(settings.rate_limit_per_minute)
    app.state.create_limiter = RateLimiter(settings.create_rate_limit_per_minute)
    app.state.miss_limiter = RateLimiter(settings.lookup_miss_limit_per_minute)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-Player-Id", "X-Player-Token"],
    )
    register_error_handlers(app)
    app.include_router(routes.router)
    app.include_router(websocket.router)
    return app


def _build_repo(settings: Settings) -> tuple[GameRepository, AsyncEngine | None]:
    """Select the persistence adapter from config: SQL when DATABASE_URL is set, else in-memory.

    This single line is the hexagonal swap — nothing in the domain or application changes.
    """
    if settings.database_url:
        engine = build_engine(settings.database_url)
        return SqlGameRepository(build_session_factory(engine)), engine
    return InMemoryGameRepository(), None


app = create_app()
