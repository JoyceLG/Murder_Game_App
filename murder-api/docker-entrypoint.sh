#!/bin/sh
# Container entrypoint: bring the schema up to date, then start the API.
#
# Migrations run here (a separate, pre-start step) rather than in the FastAPI
# lifespan so that with multiple workers only one process touches the schema and
# the app never starts against a half-migrated database.
set -e

if [ -n "$DATABASE_URL" ]; then
  echo "[entrypoint] applying database migrations (alembic upgrade head)..."
  alembic upgrade head
else
  echo "[entrypoint] DATABASE_URL unset — in-memory repository, skipping migrations."
fi

exec "$@"
