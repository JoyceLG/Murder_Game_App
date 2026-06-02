"""FastAPI application assembly and dependency wiring.

`create_app` is the composition root: it chooses concrete adapters and stores them on app.state.
Tests build their own app with in-memory adapters; production uses the defaults here.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncEngine

from src.adapters.identifiers import RandomCodeGenerator, UuidGenerator
from src.adapters.memory_repository import InMemoryGameRepository
from src.adapters.sql_repository import (
    SqlGameRepository,
    build_engine,
    build_session_factory,
    create_all,
)
from src.adapters.system_clock import SystemClock
from src.api import routes, websocket
from src.api.config import get_settings
from src.api.errors import register_error_handlers
from src.api.ws_notifier import WebSocketNotifier
from src.domain.randomness import RandomPicker
from src.ports.clock import Clock
from src.ports.identifiers import CodeGenerator, IdGenerator
from src.ports.notifier import RealtimeNotifier
from src.ports.repository import GameRepository


@asynccontextmanager
async def _lifespan(app: FastAPI):
    engine: AsyncEngine | None = app.state.engine
    if engine is not None:
        await create_all(engine)  # idempotent; production would use Alembic migrations
    yield
    if engine is not None:
        await engine.dispose()


def create_app(
    *,
    repo: GameRepository | None = None,
    clock: Clock | None = None,
    ids: IdGenerator | None = None,
    codes: CodeGenerator | None = None,
    picker: RandomPicker | None = None,
    notifier: RealtimeNotifier | None = None,
) -> FastAPI:
    app = FastAPI(title="Murder API", version="0.1.0", lifespan=_lifespan)

    engine: AsyncEngine | None = None
    if repo is None:
        repo, engine = _build_repo()
    app.state.engine = engine

    clock = clock or SystemClock()
    ids = ids or UuidGenerator()
    codes = codes or RandomCodeGenerator()
    picker = picker or RandomPicker()
    notifier = notifier or WebSocketNotifier(repo, clock)

    app.state.repo = repo
    app.state.clock = clock
    app.state.ids = ids
    app.state.codes = codes
    app.state.picker = picker
    app.state.notifier = notifier

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_error_handlers(app)
    app.include_router(routes.router)
    app.include_router(websocket.router)
    return app


def _build_repo() -> tuple[GameRepository, AsyncEngine | None]:
    """Select the persistence adapter from config: SQL when DATABASE_URL is set, else in-memory.

    This single line is the hexagonal swap — nothing in the domain or application changes.
    """
    settings = get_settings()
    if settings.database_url:
        engine = build_engine(settings.database_url)
        return SqlGameRepository(build_session_factory(engine)), engine
    return InMemoryGameRepository(), None


app = create_app()
