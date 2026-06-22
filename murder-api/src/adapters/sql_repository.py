"""SQL persistence adapter (SQLAlchemy 2.0, async). Driver-agnostic.

Production wires PostgreSQL via asyncpg (postgresql+asyncpg://...); the test suite exercises the
exact same adapter on SQLite via aiosqlite. Same port, different driver — the hexagonal payoff.

The Game aggregate is persisted as a whole: on save we upsert the game row and replace its child
players/claims, so the stored state always mirrors the in-memory aggregate.
"""

from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, Integer, String, delete, select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.pool import StaticPool

from src.domain.models import (
    DEFAULT_MAX_PLAYERS,
    Claim,
    ClaimStatus,
    Game,
    GameStatus,
    MissionMode,
    Player,
    PooledMission,
)


class Base(DeclarativeBase):
    pass


class GameRow(Base):
    __tablename__ = "games"

    code: Mapped[str] = mapped_column(String(8), primary_key=True)
    host_id: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16))
    duration_sec: Mapped[int] = mapped_column(Integer, default=0)
    start_at: Mapped[int] = mapped_column(BigInteger, default=0)
    end_at: Mapped[int] = mapped_column(BigInteger, default=0)
    max_players: Mapped[int] = mapped_column(Integer, default=DEFAULT_MAX_PLAYERS)
    max_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mission_mode: Mapped[str] = mapped_column(String(16), default=str(MissionMode.AUGMENT))


class PlayerRow(Base):
    __tablename__ = "players"

    game_code: Mapped[str] = mapped_column(
        String(8), ForeignKey("games.code", ondelete="CASCADE"), primary_key=True
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    score: Mapped[int] = mapped_column(Integer, default=0)
    mission: Mapped[str] = mapped_column(String(255), default="")
    target_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    joined_at: Mapped[int] = mapped_column(BigInteger, default=0)


class ClaimRow(Base):
    __tablename__ = "claims"

    game_code: Mapped[str] = mapped_column(
        String(8), ForeignKey("games.code", ondelete="CASCADE"), primary_key=True
    )
    atk: Mapped[str] = mapped_column(String(64), primary_key=True)
    atk_name: Mapped[str] = mapped_column(String(64))
    target: Mapped[str] = mapped_column(String(64))
    mission: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(16))
    ts: Mapped[int] = mapped_column(BigInteger, default=0)


class MissionPoolRow(Base):
    __tablename__ = "mission_pool"

    game_code: Mapped[str] = mapped_column(
        String(8), ForeignKey("games.code", ondelete="CASCADE"), primary_key=True
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    text: Mapped[str] = mapped_column(String(255))
    added_by: Mapped[str] = mapped_column(String(64))


def _to_domain(
    game_row: GameRow,
    player_rows: list[PlayerRow],
    claim_rows: list[ClaimRow],
    mission_rows: list[MissionPoolRow],
) -> Game:
    game = Game(
        code=game_row.code,
        host_id=game_row.host_id,
        status=GameStatus(game_row.status),
        duration_sec=game_row.duration_sec,
        start_at=game_row.start_at,
        end_at=game_row.end_at,
        max_players=game_row.max_players,
        max_score=game_row.max_score,
        mission_mode=MissionMode(game_row.mission_mode),
    )
    for row in mission_rows:
        game.mission_pool.append(PooledMission(id=row.id, text=row.text, by=row.added_by))
    for row in player_rows:
        game.players[row.id] = Player(
            id=row.id,
            name=row.name,
            score=row.score,
            mission=row.mission,
            target_id=row.target_id,
            joined_at=row.joined_at,
        )
    for row in claim_rows:
        game.claims[row.atk] = Claim(
            atk=row.atk,
            atk_name=row.atk_name,
            target=row.target,
            mission=row.mission,
            status=ClaimStatus(row.status),
            ts=row.ts,
        )
    return game


class SqlGameRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get(self, code: str) -> Game | None:
        async with self._session_factory() as session:
            game_row = await session.get(GameRow, code)
            if game_row is None:
                return None
            # Order so the reloaded aggregate mirrors in-memory insertion order: players by
            # join time (Game.ranking and host reassignment rely on it), claims by timestamp.
            players = (
                (
                    await session.execute(
                        select(PlayerRow)
                        .where(PlayerRow.game_code == code)
                        .order_by(PlayerRow.joined_at, PlayerRow.id)
                    )
                )
                .scalars()
                .all()
            )
            claims = (
                (
                    await session.execute(
                        select(ClaimRow)
                        .where(ClaimRow.game_code == code)
                        .order_by(ClaimRow.ts, ClaimRow.atk)
                    )
                )
                .scalars()
                .all()
            )
            missions = (
                (
                    await session.execute(
                        select(MissionPoolRow)
                        .where(MissionPoolRow.game_code == code)
                        .order_by(MissionPoolRow.position, MissionPoolRow.id)
                    )
                )
                .scalars()
                .all()
            )
            return _to_domain(game_row, list(players), list(claims), list(missions))

    async def save(self, game: Game) -> None:
        async with self._session_factory() as session, session.begin():
            game_row = await session.get(GameRow, game.code)
            if game_row is None:
                game_row = GameRow(code=game.code)
                session.add(game_row)
            game_row.host_id = game.host_id
            game_row.status = str(game.status)
            game_row.duration_sec = game.duration_sec
            game_row.start_at = game.start_at
            game_row.end_at = game.end_at
            game_row.max_players = game.max_players
            game_row.max_score = game.max_score
            game_row.mission_mode = str(game.mission_mode)
            await session.flush()

            # Replace the aggregate's children wholesale.
            await session.execute(delete(PlayerRow).where(PlayerRow.game_code == game.code))
            await session.execute(delete(ClaimRow).where(ClaimRow.game_code == game.code))
            await session.execute(
                delete(MissionPoolRow).where(MissionPoolRow.game_code == game.code)
            )
            await session.flush()

            for player in game.players.values():
                session.add(
                    PlayerRow(
                        game_code=game.code,
                        id=player.id,
                        name=player.name,
                        score=player.score,
                        mission=player.mission,
                        target_id=player.target_id,
                        joined_at=player.joined_at,
                    )
                )
            for claim in game.claims.values():
                session.add(
                    ClaimRow(
                        game_code=game.code,
                        atk=claim.atk,
                        atk_name=claim.atk_name,
                        target=claim.target,
                        mission=claim.mission,
                        status=str(claim.status),
                        ts=claim.ts,
                    )
                )
            for position, mission in enumerate(game.mission_pool):
                session.add(
                    MissionPoolRow(
                        game_code=game.code,
                        id=mission.id,
                        position=position,
                        text=mission.text,
                        added_by=mission.by,
                    )
                )

    async def delete(self, code: str) -> None:
        async with self._session_factory() as session, session.begin():
            await session.execute(delete(ClaimRow).where(ClaimRow.game_code == code))
            await session.execute(delete(PlayerRow).where(PlayerRow.game_code == code))
            await session.execute(delete(MissionPoolRow).where(MissionPoolRow.game_code == code))
            await session.execute(delete(GameRow).where(GameRow.code == code))

    async def exists(self, code: str) -> bool:
        async with self._session_factory() as session:
            result = await session.execute(select(GameRow.code).where(GameRow.code == code))
            return result.first() is not None


def build_engine(database_url: str) -> AsyncEngine:
    """Create an async engine. SQLite in-memory uses a shared connection so the DB survives."""
    if database_url.startswith("sqlite"):
        return create_async_engine(
            database_url, poolclass=StaticPool, connect_args={"check_same_thread": False}
        )
    return create_async_engine(database_url, pool_pre_ping=True)


def build_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def create_all(engine: AsyncEngine) -> None:
    """Create the schema directly from the models.

    Used only for the ephemeral SQLite databases in the test suite. The persistent
    PostgreSQL schema is owned by Alembic (`alembic upgrade head`) — never call this
    in production, or it will diverge from the migration history.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
