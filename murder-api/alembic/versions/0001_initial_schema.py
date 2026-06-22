"""initial schema (games, players, claims, mission_pool)

Mirrors the SQLAlchemy models in src/adapters/sql_repository.py as of this
revision. Future model changes get their own revision via
`alembic revision --autogenerate`.

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-22

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "games",
        sa.Column("code", sa.String(length=8), nullable=False),
        sa.Column("host_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("duration_sec", sa.Integer(), nullable=False),
        sa.Column("start_at", sa.BigInteger(), nullable=False),
        sa.Column("end_at", sa.BigInteger(), nullable=False),
        sa.Column("max_players", sa.Integer(), nullable=False),
        sa.Column("max_score", sa.Integer(), nullable=True),
        sa.Column("mission_mode", sa.String(length=16), nullable=False),
        sa.PrimaryKeyConstraint("code"),
    )
    op.create_table(
        "players",
        sa.Column("game_code", sa.String(length=8), nullable=False),
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("mission", sa.String(length=255), nullable=False),
        sa.Column("target_id", sa.String(length=64), nullable=True),
        sa.Column("joined_at", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["game_code"], ["games.code"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("game_code", "id"),
    )
    op.create_table(
        "claims",
        sa.Column("game_code", sa.String(length=8), nullable=False),
        sa.Column("atk", sa.String(length=64), nullable=False),
        sa.Column("atk_name", sa.String(length=64), nullable=False),
        sa.Column("target", sa.String(length=64), nullable=False),
        sa.Column("mission", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("ts", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["game_code"], ["games.code"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("game_code", "atk"),
    )
    op.create_table(
        "mission_pool",
        sa.Column("game_code", sa.String(length=8), nullable=False),
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("text", sa.String(length=255), nullable=False),
        sa.Column("added_by", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["game_code"], ["games.code"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("game_code", "id"),
    )


def downgrade() -> None:
    op.drop_table("mission_pool")
    op.drop_table("claims")
    op.drop_table("players")
    op.drop_table("games")
