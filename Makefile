# Developer entry points. Everything runs from the repo-root .venv created by `make setup`
# (Python 3.12, Node 20, PostgreSQL 16 binaries, Chromium) — no system packages, no sudo.
# See TESTING.md.

VENV := $(CURDIR)/.venv
BIN := $(VENV)/bin
PY := $(BIN)/python
export PATH := $(BIN):$(PATH)
export PLAYWRIGHT_BROWSERS_PATH := $(VENV)/ms-playwright

.PHONY: help setup lint test test-api test-front test-pg e2e e2e-local e2e-compose ci pg-stop clean

help: ## list the targets
	@grep -E '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) | awk -F':.*?## ' '{printf "  make %-12s %s\n", $$1, $$2}'

setup: ## create/refresh .venv (Python, Node, PostgreSQL, Chromium) + npm ci
	scripts/setup-dev.sh

lint: ## ruff check + format check (API), as in CI
	cd murder-api && $(BIN)/ruff check . && $(BIN)/ruff format --check .

test: test-api test-front ## fast suites: API on SQLite + Angular unit tests

test-api: ## API: unit + integration on SQLite, coverage gate
	cd murder-api && $(PY) -m pytest

test-front: ## Angular unit tests in headless Chromium
	cd murder-front && CHROME_BIN="$$($(PY) $(CURDIR)/scripts/chrome_path.py)" \
		npx ng test --watch=false --browsers=ChromeHeadlessNoSandbox

test-pg: ## API suite + concurrency + migration tests on a real PostgreSQL 16
	@url="$$(scripts/pg.sh fresh murder_test)"; \
	cd murder-api && \
	DATABASE_URL="$$url" $(PY) -m alembic upgrade head && \
	DATABASE_URL="$$url" $(PY) -m alembic check && \
	TEST_DATABASE_URL="$$url" $(PY) -m pytest

e2e: ## end-to-end suite (compose if Docker is usable, else local servers)
	scripts/e2e.sh

e2e-local: ## end-to-end on PostgreSQL + uvicorn + ng serve (no Docker)
	scripts/e2e.sh local

e2e-compose: ## end-to-end on the docker compose stack (nginx), as in CI
	scripts/e2e.sh compose

ci: lint test test-pg e2e ## everything CI runs

pg-stop: ## stop the local test PostgreSQL and delete its data
	scripts/pg.sh stop

clean: pg-stop ## remove test artifacts (keeps .venv)
	rm -rf .tools e2e/test-results murder-api/.coverage murder-api/coverage.xml murder-front/coverage
