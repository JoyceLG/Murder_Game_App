#!/usr/bin/env bash
# One-shot developer setup: everything lives in ./.venv, nothing is installed system-wide.
#
#   .venv/                Python 3.12 (same as CI/Docker) + API deps + dev tools
#   .venv/bin/node, npm   Node.js (nodeenv)
#   .venv/ms-playwright/  Chromium for Playwright and Karma
#   murder-front/node_modules
#
# Re-running is safe (idempotent). Requires: curl, git. No sudo.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$ROOT/.venv"
PYTHON_VERSION="${PYTHON_VERSION:-3.12}"
NODE_VERSION="${NODE_VERSION:-20.20.2}"
export PLAYWRIGHT_BROWSERS_PATH="$VENV/ms-playwright"

step() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }

# 1. uv: fetches the right Python and creates the venv (user-level install, no sudo).
if ! command -v uv >/dev/null 2>&1; then
  if [ -x "$HOME/.local/bin/uv" ]; then
    export PATH="$HOME/.local/bin:$PATH"
  else
    step "Installing uv into ~/.local/bin"
    curl -LsSf https://astral.sh/uv/install.sh | env UV_NO_MODIFY_PATH=1 sh
    export PATH="$HOME/.local/bin:$PATH"
  fi
fi

step "Python $PYTHON_VERSION venv at .venv"
if [ ! -x "$VENV/bin/python" ] || ! "$VENV/bin/python" -c \
  "import sys; sys.exit(sys.version_info[:2] != tuple(map(int, '$PYTHON_VERSION'.split('.'))))"; then
  rm -rf "$VENV"
  uv venv --python "$PYTHON_VERSION" "$VENV"
fi

step "Python dependencies (API + dev tooling)"
uv pip install --python "$VENV/bin/python" -r "$ROOT/requirements-dev.txt"

step "Node.js $NODE_VERSION inside the venv"
if [ "$("$VENV/bin/node" --version 2>/dev/null)" != "v$NODE_VERSION" ]; then
  VIRTUAL_ENV="$VENV" "$VENV/bin/nodeenv" --python-virtualenv --node="$NODE_VERSION" --force
fi

step "Chromium (Playwright; also the browser Karma runs in)"
"$VENV/bin/playwright" install chromium

step "Frontend dependencies (npm ci)"
(cd "$ROOT/murder-front" && PATH="$VENV/bin:$PATH" npm ci --no-audit --no-fund)

# Make `source .venv/bin/activate` enough: point Karma and Playwright at the venv's Chromium.
MARK="# --- murder dev env ---"
if ! grep -q "$MARK" "$VENV/bin/activate"; then
  CHROME="$("$VENV/bin/python" "$ROOT/scripts/chrome_path.py")"
  cat >>"$VENV/bin/activate" <<ACT

$MARK
export PLAYWRIGHT_BROWSERS_PATH="$PLAYWRIGHT_BROWSERS_PATH"
export CHROME_BIN="$CHROME"
ACT
fi

step "Checking the browser can start"
if ! "$("$VENV/bin/python" "$ROOT/scripts/chrome_path.py")" --headless --no-sandbox --dump-dom about:blank >/dev/null 2>&1; then
  cat <<'MSG'
Chromium is installed but cannot start: some system libraries are missing.
Install them once (needs sudo):   sudo .venv/bin/playwright install-deps chromium
MSG
  exit 1
fi

cat <<'DONE'

Setup complete. Next:
  source .venv/bin/activate
  make test          # unit + integration on SQLite, Angular unit tests
  make test-pg       # backend suite + migration tests on a real PostgreSQL 16
  make e2e           # full stack, API + browser end-to-end tests
DONE
