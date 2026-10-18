#!/usr/bin/env bash
# Run the end-to-end suite (e2e/) against a freshly started stack.
#
#   scripts/e2e.sh compose   production-like: docker compose (nginx + API + PostgreSQL), as in CI
#   scripts/e2e.sh local     no Docker: PostgreSQL from scripts/pg.sh + uvicorn + ng serve (prod
#                            build, /games proxied: same origin), on free ports
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
  export E2E_APP_URL=http://localhost:8080 E2E_NGINX=1
  unset E2E_API_URL
  run_suite "$@"
  exit 0
fi

# --- local: no Docker ------------------------------------------------------------------
# The production build of the front, served by `ng serve` with a proxy for /games (REST and
# WebSocket) and /health: same origin and relative URLs, like behind nginx. Ports are free
# ones by default, so a dev server or a running compose stack (8000/8080/4200) is no problem.
# Two distinct free ports, picked while both sockets are held (so they cannot be the same).
read -r FREE_A FREE_B < <("$PY" -c '
import socket
a, b = socket.socket(), socket.socket()
a.bind(("127.0.0.1", 0)); b.bind(("127.0.0.1", 0))
print(a.getsockname()[1], b.getsockname()[1])')
API_PORT="${E2E_API_PORT:-$FREE_A}"
APP_PORT="${E2E_APP_PORT:-$FREE_B}"

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

(cd "$ROOT/murder-api" && exec setsid env DATABASE_URL="$DB_URL" \
  RATE_LIMIT_PER_MINUTE=0 CREATE_RATE_LIMIT_PER_MINUTE=0 LOOKUP_MISS_LIMIT_PER_MINUTE=0 \
  "$PY" -m uvicorn src.api.main:app --host 127.0.0.1 --port "$API_PORT" >"$RESULTS/api.log" 2>&1) &
PIDS+=($!)

cat >"$RESULTS/proxy.json" <<JSON
{
  "/games": { "target": "http://127.0.0.1:$API_PORT", "ws": true },
  "/health": { "target": "http://127.0.0.1:$API_PORT" }
}
JSON
(cd "$ROOT/murder-front" && exec setsid npx ng serve --configuration production --port "$APP_PORT" \
  --proxy-config "$RESULTS/proxy.json" --no-hmr --no-live-reload >"$RESULTS/front.log" 2>&1) &
PIDS+=($!)

wait_for "http://127.0.0.1:$API_PORT/health" 60
wait_for "http://localhost:$APP_PORT/health" 180
export E2E_APP_URL="http://localhost:$APP_PORT"
unset E2E_API_URL E2E_NGINX
run_suite "$@"
