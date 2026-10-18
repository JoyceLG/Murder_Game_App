#!/usr/bin/env bash
# Run the end-to-end suite (e2e/) against a freshly started stack.
#
#   scripts/e2e.sh compose   production-like: docker compose (nginx + API + PostgreSQL), as in CI
#   scripts/e2e.sh local     no Docker: PostgreSQL from scripts/pg.sh + uvicorn + ng serve
#   scripts/e2e.sh           compose if Docker is usable, else local
#
# Extra arguments go to pytest, e.g.  scripts/e2e.sh local -k browser --headed
# Failure artifacts (screenshots, Playwright traces, server logs): e2e/test-results/
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RESULTS="$ROOT/e2e/test-results"
PY="${PYTHON:-$ROOT/.venv/bin/python}"
[ -x "$PY" ] || PY="python"
if [ -d "$ROOT/.venv/bin" ]; then
  export PATH="$ROOT/.venv/bin:$PATH"
  export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-$ROOT/.venv/ms-playwright}"
fi

mode="${1:-auto}"
case "$mode" in compose|local|auto) shift || true ;; *) mode=auto ;; esac
if [ "$mode" = auto ]; then
  if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then mode=compose; else mode=local; fi
fi

rm -rf "$RESULTS"
mkdir -p "$RESULTS"

wait_for() { # url, seconds
  for _ in $(seq "$2"); do curl -fsS -o /dev/null "$1" 2>/dev/null && return 0; sleep 1; done
  echo "timed out waiting for $1" >&2
  return 1
}

run_suite() {
  echo "==> e2e against app=$E2E_APP_URL api=${E2E_API_URL:-$E2E_APP_URL}"
  (cd "$ROOT/e2e" && "$PY" -m pytest "$@")
}

if [ "$mode" = compose ]; then
  COMPOSE=(docker compose -p murder-e2e -f "$ROOT/docker-compose.yml" -f "$ROOT/docker-compose.e2e.yml")
  cleanup() {
    status=$?
    if [ $status -ne 0 ]; then "${COMPOSE[@]}" logs --no-color >"$RESULTS/compose.log" 2>&1 || true; fi
    "${COMPOSE[@]}" down -v --remove-orphans >/dev/null 2>&1 || true
    exit $status
  }
  trap cleanup EXIT
  "${COMPOSE[@]}" up -d --build --wait
  wait_for http://localhost:8080/health 60
  export E2E_APP_URL=http://localhost:8080
  unset E2E_API_URL
  run_suite "$@"
  exit 0
fi

# --- local: no Docker ------------------------------------------------------------------
for port in 8000 4200; do
  if curl -s -o /dev/null "http://localhost:$port"; then
    echo "port $port is already in use — stop whatever runs there (uvicorn / ng serve) first" >&2
    exit 1
  fi
done

PIDS=()
cleanup() {
  status=$?
  # each server runs in its own process group (setsid): kill the group, not just the leader
  for pid in "${PIDS[@]}"; do kill -- "-$pid" 2>/dev/null || kill "$pid" 2>/dev/null || true; done
  wait 2>/dev/null || true
  [ -n "${KEEP_PG:-}" ] || "$ROOT/scripts/pg.sh" stop
  [ $status -ne 0 ] && echo "server logs: $RESULTS/api.log, $RESULTS/front.log" >&2
  exit $status
}
trap cleanup EXIT

DB_URL="$("$ROOT/scripts/pg.sh" fresh murder_e2e)"
(cd "$ROOT/murder-api" && DATABASE_URL="$DB_URL" "$PY" -m alembic upgrade head >/dev/null)

(cd "$ROOT/murder-api" && exec setsid env DATABASE_URL="$DB_URL" ALLOWED_ORIGINS=http://localhost:4200 \
  RATE_LIMIT_PER_MINUTE=0 CREATE_RATE_LIMIT_PER_MINUTE=0 LOOKUP_MISS_LIMIT_PER_MINUTE=0 \
  "$PY" -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000 >"$RESULTS/api.log" 2>&1) &
PIDS+=($!)
(cd "$ROOT/murder-front" && exec setsid npx ng serve --port 4200 --no-hmr --no-live-reload \
  >"$RESULTS/front.log" 2>&1) &
PIDS+=($!)

wait_for http://localhost:8000/health 60
wait_for http://localhost:4200/ 180
export E2E_APP_URL=http://localhost:4200 E2E_API_URL=http://localhost:8000
run_suite "$@"
