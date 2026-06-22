# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A real-time multiplayer "murder party" game. Each player gets a secret target and a mission; they eliminate the target, **the target confirms** the kill, a point is scored, and a new target/mission is dealt. Active development lives on the `python-rewrite` branch (the README, in French, is the canonical product/architecture reference).

Three top-level pieces:
- `murder-api/` — Python/FastAPI backend, hexagonal (ports & adapters) + DDD + TDD.
- `murder-front/` — Angular 20 frontend (standalone components, signals, control-flow).
- `legacy-js/` — the original vanilla-JS + Firestore prototype. **Read-only historical context** — it explains why the rewrite exists; don't edit it.

## Commands

### Backend (`murder-api/`)
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn src.api.main:app --reload          # API + Swagger on :8000 (in-memory repo by default)
pytest                                      # full suite + coverage (gate 85%, repo sits at 100%)
pytest tests/domain/test_rules.py           # single file
pytest tests/domain/test_rules.py::test_x   # single test
pytest -m "not integration"                 # skip tests needing real PostgreSQL
ruff check . && ruff format --check .        # lint + format (line length 100, target py312)
```
SQL adapter integration tests run on **SQLite** by default (fast, no Docker). Set `TEST_DATABASE_URL` to a PostgreSQL DSN to exercise the same adapter against prod's target.

#### Database migrations (Alembic)
The PostgreSQL schema is owned by **Alembic** (`murder-api/alembic/`), not `create_all`. The Docker
entrypoint runs `alembic upgrade head` before the API starts; for a local Postgres run, do it once
yourself. `DATABASE_URL` is read by `alembic/env.py` from the same `Settings` the app uses.
```bash
alembic upgrade head                              # apply all pending migrations
alembic revision --autogenerate -m "add x"        # new migration from a model change
alembic check                                     # CI guard: fail if models drift from migrations
alembic downgrade -1                              # roll back one revision
alembic stamp head                                # mark an existing DB as migrated (no DDL)
```
After **any** change to a SQLAlchemy model in `adapters/sql_repository.py`, generate a migration and
review it. `create_all` is kept only for the ephemeral SQLite test databases (`tests/`), never prod.

### Frontend (`murder-front/`)
```bash
npm install
npm start                                              # ng serve on :4200 (hits API on :8000)
npm test -- --watch=false --browsers=ChromeHeadless    # Karma/Jasmine
npm run build                                          # prod build (switches to relative URLs)
```
Note: Node 20 toolchain is at `~/tools/node20/bin` on this machine (nvm is blocked).

### Full stack
```bash
docker compose up --build   # front :8080, api :8000 (Swagger /docs), postgres :5432
```
nginx (front) reverse-proxies `/games` and the WebSocket to the API → single origin, no CORS.

## Architecture

### Dependency rule (backend)
Everything points inward. Never invert these:
- `domain/` — pure business core. **No framework imports, no I/O, synchronous.** `models` (dataclasses: `Game`/`Player`/`Claim`), `rules` (in-place mutations of the `Game` aggregate), `missions`, `randomness` (`Picker`).
- `ports/` — interfaces as `Protocol`s. The I/O-facing ones (`GameRepository`, `RealtimeNotifier`) are **async**; the domain stays sync and pure.
- `application/` — one use case per file (`CreateGame`, `StartGame`, `ClaimElimination`, `ConfirmClaim`, …), each a dataclass with an `async execute(...)`. Depends only on `domain` + `ports`. Shared helpers in `_support.py` (`get_game_or_404`, `settle_end`).
- `adapters/` + `api/` — outermost ring. `InMemoryGameRepository` / `SqlGameRepository` (SQLAlchemy 2.0 async + asyncpg), `WebSocketNotifier`, FastAPI routes/schemas/DI.

**Switching in-memory → PostgreSQL is one env var (`DATABASE_URL`)** and touches no business code. `api/dependencies.py` is the *only* place that knows which concrete adapters are wired; components are built once in `api/main.create_app` and stored on `app.state`.

### The central invariant
In legacy-js, the attacker's own browser resolved its kill ("client-side scoring trust"). The rewrite moves authority server-side: only the claim's **target** may confirm/deny, and scoring/reassignment runs on the server. This is `application/confirm_claim.py` (`ConfirmClaim`) calling `domain/rules.resolve_claim`. The regression guard is the test asserting `confirm by non-target → 403`. Preserve this when touching claims.

### Request → response shape (backend)
Routes are thin: call a use case, then map the resulting domain `Game` to a DTO via the single mapper `api/mappers.to_game_out` (the anti-corruption boundary — **DTOs are never domain entities**). Caller identity comes from the `X-Player-Id` header (`dependencies.player_id`). Randomness is the injected `Picker`, so domain tests are deterministic.

### Frontend
`core/services/game-store.ts` (`GameStore`) is the single source of truth and the Angular port of legacy `_recompute`: the WebSocket feeds a `state` signal, and everything the screens need (`me`, `target`, `incoming` claim, `ranking`, `screen`) is a `computed` derived from it. The only genuinely client-side value is the 1s countdown. Actions call REST; the resulting WebSocket push refreshes `state`. `rehydrate()` revalidates a stored session on load (survives refresh); a session pointing at a vanished game routes to the `gone` screen. Routes (`app.routes.ts`) lazy-load feature components and gate in-game routes with `inGameGuard`.

## Conventions & constraints
- Game rules live **only** in `domain/rules.py` and mutate the `Game` aggregate in place; keep them pure and pass the `Picker` for any randomness.
- New use case = new file in `application/` + a provider in `api/dependencies.py` + a thin route in `api/routes.py`.
- Coverage gate is 85% in CI; `src/api/main.py` is omitted from coverage.
- **WebSocket is single-worker** (connections held in process memory) → run `uvicorn --workers 1`; multi-worker would need a Redis pub/sub backplane.
- End-of-game is **lazy** — computed at read time via `settle_end`, no scheduler.

## Mobile-ready guardrails

The long-term goal is native **Android + iOS apps via Capacitor** (the Angular SPA wrapped in a
native WebView) with push notifications — full plan in `ROADMAP_Murder_app.md` ("Feuille de route —
Déploiement mobile"). The port isn't started yet, but every new feature must stay WebView/Capacitor-
safe. These are cheap to honor now and expensive to retrofit:

- **Never hardcode API/WebSocket URLs.** All base URLs come from `environment.apiBase` /
  `environment.wsBase` (`murder-front/src/environments/`). The *only* place allowed to derive a URL
  from `window.location` is `core/services/realtime.ts` — don't scatter `location.host`/`location.origin`
  elsewhere. In a Capacitor WebView the origin is `capacitor://localhost`, so prod will run with
  absolute URLs.
- **Identity stays in the `X-Player-Id` header**, never a cookie/session. It's read once in
  `api/dependencies.py:player_id`; keep auth stateless and header-based so the WebView client works
  unchanged. JWT signing is the planned hardening — keep it swappable behind that single point.
- **No browser-only APIs without a WebView fallback** (avoid `window.open`, clipboard, raw history
  nav outside the Angular router, file downloads). Prefer a Capacitor plugin when a native capability
  is needed.
- **Keep CSS responsive and safe-area aware** (`viewport-fit=cover` is already set in `index.html`;
  use `env(safe-area-inset-*)` for notches). Design small-touch-screen first.
- **Backend stays 12-factor** (config via env vars, see `api/config.py`) — no hardcoded URLs/secrets.
- **Notifications go through a port.** Server-push already flows through `RealtimeNotifier`; future
  push notifications must slot in as a sibling port, not ad-hoc calls — preserve the hexagonal boundary.

## Dev workflow (branch-per-issue → PR → review → merge)

Feature work is tracked as GitHub issues (milestone *"Features pré-déploiement mobile"*, currently
#10–#16). `main` is the integration branch (the `python-rewrite` branch is legacy — already merged
via PR #1). For **every** issue:

1. **One branch per issue**, cut from up-to-date `main`: `feat/<issue-number>-<slug>`
   (e.g. `feat/10-i18n-infra`). Never commit feature work directly to `main`.
2. **Tests are part of the issue, not optional.** Update existing tests and add new ones covering the
   new behavior — TDD on the backend (keep the **85% coverage gate**; `pytest` + `ruff`), and keep the
   frontend ChromeHeadless tests green. An issue is not "done" without tests.
3. **Document the validation scenarios in the GitHub wiki** — one page per issue (e.g. *"Issue 10 —
   i18n"*): the concrete end-to-end steps a reviewer follows to validate the feature, with expected
   results. The wiki is the canonical place for these manual/acceptance scenarios.
4. **Open a PR to `main`** at the end of the issue, with `Closes #<n>` and a link to its wiki page.
5. **Reviewer mode (required before merge).** Claude performs a complete review of the PR
   (correctness, test coverage, mobile-ready guardrails, hexagonal boundaries) and then **asks the
   user to validate the issue**. **Never merge to `main` without explicit user approval.**
6. After approval: **squash-merge** to `main` and delete the branch.

Every feature branch must respect the **Mobile-ready guardrails** above.

## CI
`.github/workflows/ci.yml` on push/PR to `main`/`python-rewrite`: backend (`ruff check` + `ruff format --check` + `pytest --cov` against a real PostgreSQL service) → frontend (`npm run build` + ChromeHeadless tests) → Docker image builds for both.
