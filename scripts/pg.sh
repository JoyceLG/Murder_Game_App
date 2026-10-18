#!/usr/bin/env bash
# Throwaway local PostgreSQL 16 for integration / e2e tests.
#
#   scripts/pg.sh start          start it (no-op if already running), print nothing
#   scripts/pg.sh stop           stop it
#   scripts/pg.sh url [db]       print the SQLAlchemy URL (creating database `db` if needed)
#   scripts/pg.sh fresh <db>     drop + recreate database `db`, print its URL
#
# Uses, in order: Docker (if usable from this shell), else the PostgreSQL binaries shipped in
# the venv by `pgserver` (scripts/setup-dev.sh), else a system install (initdb on PATH).
# Data lives in .tools/pg (deleted by `stop`). Listens on 127.0.0.1:$PG_PORT only, trust auth.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PG_PORT="${PG_PORT:-54329}"
DIR="$ROOT/.tools/pg"
CONTAINER="murder-test-pg"

docker_ok() { command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; }

pg_bin() {
  local bundled
  bundled="$("$ROOT/.venv/bin/python" -c \
    'import os, pgserver; print(os.path.join(os.path.dirname(pgserver.__file__), "pginstall", "bin"))' \
    2>/dev/null || true)"
  if [ -n "$bundled" ] && [ -x "$bundled/initdb" ]; then echo "$bundled"; return; fi
  if command -v initdb >/dev/null 2>&1; then dirname "$(command -v initdb)"; return; fi
  local system
  system="$(ls -d /usr/lib/postgresql/*/bin 2>/dev/null | sort -V | tail -1 || true)"
  if [ -n "$system" ]; then echo "$system"; return; fi
  echo "No PostgreSQL found: run scripts/setup-dev.sh, or enable Docker's WSL integration." >&2
  exit 1
}

psql_cmd() {
  if [ -f "$DIR/docker" ]; then
    docker exec -i -e PGOPTIONS="-c client_min_messages=warning" "$CONTAINER" \
      psql -U postgres -v ON_ERROR_STOP=1 -q "$@"
  else
    PGOPTIONS="-c client_min_messages=warning" \
      "$(pg_bin)/psql" -h 127.0.0.1 -p "$PG_PORT" -U postgres -v ON_ERROR_STOP=1 -q "$@"
  fi
}

running() {
  if [ -f "$DIR/docker" ]; then
    docker exec "$CONTAINER" pg_isready -U postgres >/dev/null 2>&1
  else
    [ -d "$DIR/data" ] && "$(pg_bin)/pg_ctl" -D "$DIR/data" status >/dev/null 2>&1
  fi
}

start() {
  if running; then return; fi
  mkdir -p "$DIR"
  if docker_ok; then
    touch "$DIR/docker"
    docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
    docker run -d --name "$CONTAINER" -e POSTGRES_HOST_AUTH_METHOD=trust \
      -p "127.0.0.1:$PG_PORT:5432" postgres:16-alpine >/dev/null
    for _ in $(seq 60); do running && return; sleep 0.5; done
    echo "PostgreSQL container did not become ready" >&2; exit 1
  fi
  local bin; bin="$(pg_bin)"
  rm -rf "$DIR/data"
  "$bin/initdb" -D "$DIR/data" -U postgres --auth=trust -E UTF8 >/dev/null
  "$bin/pg_ctl" -D "$DIR/data" -l "$DIR/postgres.log" -w \
    -o "-p $PG_PORT -k $DIR -c listen_addresses=127.0.0.1 -c fsync=off" start >/dev/null
}

stop() {
  if [ -f "$DIR/docker" ]; then
    docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
  elif [ -d "$DIR/data" ]; then
    "$(pg_bin)/pg_ctl" -D "$DIR/data" -m fast stop >/dev/null 2>&1 || true
  fi
  rm -rf "$DIR"
}

url() { echo "postgresql+asyncpg://postgres@127.0.0.1:$PG_PORT/$1"; }

case "${1:-}" in
  start) start ;;
  stop) stop ;;
  url)
    db="${2:-murder_test}"
    start
    psql_cmd -tAc "SELECT 1 FROM pg_database WHERE datname = '$db'" | grep -q 1 \
      || psql_cmd -c "CREATE DATABASE \"$db\""
    url "$db"
    ;;
  fresh)
    db="${2:?database name required}"
    start
    psql_cmd -c "DROP DATABASE IF EXISTS \"$db\" WITH (FORCE)"
    psql_cmd -c "CREATE DATABASE \"$db\""
    url "$db"
    ;;
  *) echo "usage: $0 {start|stop|url [db]|fresh <db>}" >&2; exit 2 ;;
esac
