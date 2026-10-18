"""players.free_swap_used: the one free mission swap at 0 points (#20)

Revision ID: 0003_free_swap
Revises: 0002_version_token
Create Date: 2026-10-18

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_free_swap"
down_revision: str | None = "0002_version_token"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Existing players have not used their free swap yet.
    op.add_column(
        "players",
        sa.Column("free_swap_used", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    # The ORM always writes the column; drop the default so the schema matches the model.
    with op.batch_alter_table("players") as batch:
        batch.alter_column("free_swap_used", server_default=None)


def downgrade() -> None:
    op.drop_column("players", "free_swap_used")
