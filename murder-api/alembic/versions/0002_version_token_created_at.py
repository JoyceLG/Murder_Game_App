"""optimistic-lock version, game creation time, player session-token digest

- games.version     : optimistic concurrency guard (see SqlGameRepository.save)
- games.created_at  : lets stale games be purged; existing rows are stamped with the
                      migration time so they are not purged on the first sweep
- players.token_hash: digest of each player's session secret (identity proof)

Revision ID: 0002_version_token
Revises: 0001_initial
Create Date: 2026-10-18

"""

from __future__ import annotations

import time
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_version_token"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("games", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column(
        "games", sa.Column("created_at", sa.BigInteger(), nullable=False, server_default="0")
    )
    op.add_column(
        "players",
        sa.Column("token_hash", sa.String(length=64), nullable=False, server_default=""),
    )
    op.execute(
        sa.text("UPDATE games SET created_at = :now").bindparams(now=int(time.time() * 1000))
    )
    # The ORM always writes these columns; drop the defaults so the schema matches the models.
    with op.batch_alter_table("games") as batch:
        batch.alter_column("version", server_default=None)
        batch.alter_column("created_at", server_default=None)
    with op.batch_alter_table("players") as batch:
        batch.alter_column("token_hash", server_default=None)


def downgrade() -> None:
    op.drop_column("players", "token_hash")
    op.drop_column("games", "created_at")
    op.drop_column("games", "version")
