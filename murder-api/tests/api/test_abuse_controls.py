"""Rate limiting, CORS allowlist and per-game request serialization."""

import asyncio

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from src.api.config import Settings
from src.api.locks import GameLocks
from src.api.main import create_app
from src.api.rate_limit import RateLimiter


def _client(**settings) -> TestClient:
    return TestClient(create_app(settings=Settings(**settings)))


# --- RateLimiter ---------------------------------------------------------------------


def test_rate_limiter_spends_tokens_then_refills_over_time():
    now = [0.0]
    limiter = RateLimiter(per_minute=2, now=lambda: now[0])
    assert limiter.allow("ip") and limiter.allow("ip")
    assert not limiter.allow("ip")
    assert limiter.exhausted("ip")
    now[0] += 30  # half a minute refills one token
    assert limiter.allow("ip")
    assert limiter.allow("other-ip")  # budgets are per client


def test_rate_limiter_forgets_idle_clients_but_not_active_ones(monkeypatch):
    now = [0.0]
    limiter = RateLimiter(per_minute=1, now=lambda: now[0])
    monkeypatch.setattr(RateLimiter, "MAX_TRACKED_CLIENTS", 2)
    assert limiter.allow("idle")
    now[0] += 120  # "idle" has fully refilled
    assert limiter.allow("busy")
    assert limiter.allow("newcomer")  # evicts "idle", keeps "busy" (still empty)
    assert not limiter.allow("busy")
    assert not limiter.allow("newcomer")  # the newcomer's spend was recorded


def test_rate_limiter_zero_means_unlimited():
    limiter = RateLimiter(per_minute=0)
    assert all(limiter.allow("ip") for _ in range(1000))
    assert not limiter.exhausted("ip")


# --- wired into the app --------------------------------------------------------------


def test_game_creation_is_rate_limited():
    with _client(create_rate_limit_per_minute=2) as client:
        statuses = [client.post("/games", json={"host_name": "A"}).status_code for _ in range(3)]
    assert statuses == [201, 201, 429]


def test_probing_unknown_codes_gets_the_client_blocked():
    with _client(lookup_miss_limit_per_minute=3) as client:
        statuses = [client.get(f"/games/NO{i:02d}").status_code for i in range(5)]
        code = client.post("/games", json={"host_name": "A"}).json()["code"]
        # once blocked, even a real code is refused until the budget refills
        assert client.get(f"/games/{code}").status_code == 429
    assert statuses == [404, 404, 404, 429, 429]


def test_global_request_budget():
    with _client(rate_limit_per_minute=3) as client:
        statuses = [client.get("/health").status_code for _ in range(4)]
    assert statuses == [200, 200, 200, 429]


# --- CORS ----------------------------------------------------------------------------


def _preflight(client: TestClient, origin: str):
    return client.options(
        "/games",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "X-Player-Id, X-Player-Token",
        },
    )


def test_cors_allows_listed_origins_only():
    with _client(allowed_origins="https://murder.example, capacitor://localhost") as client:
        allowed = _preflight(client, "capacitor://localhost")
        refused = _preflight(client, "https://evil.example")
    assert allowed.headers["access-control-allow-origin"] == "capacitor://localhost"
    assert "x-player-token" in allowed.headers["access-control-allow-headers"].lower()
    assert "access-control-allow-origin" not in refused.headers


def test_settings_parse_comma_separated_origins():
    assert Settings(allowed_origins=" a , ,b").cors_origins == ["a", "b"]


# --- GameLocks -----------------------------------------------------------------------


async def test_game_locks_serialize_same_code_and_clean_up():
    locks = GameLocks()
    order: list[str] = []

    async def worker(name: str, code: str) -> None:
        async with locks.hold(code):
            order.append(f"{name}-in")
            await asyncio.sleep(0.01)
            order.append(f"{name}-out")

    await asyncio.gather(worker("a", "ABCD"), worker("b", "ABCD"))
    assert order in (
        ["a-in", "a-out", "b-in", "b-out"],
        ["b-in", "b-out", "a-in", "a-out"],
    )
    assert len(locks) == 0


async def test_game_locks_do_not_block_other_games():
    locks = GameLocks()
    async with locks.hold("AAAA"):
        await asyncio.wait_for(_enter(locks, "BBBB"), 0.5)


async def _enter(locks: GameLocks, code: str) -> None:
    async with locks.hold(code):
        pass


@pytest.mark.parametrize("missing", ["X-Player-Id", "X-Player-Token"])
def test_both_identity_headers_are_required(missing):
    with _client() as client:
        body = client.post("/games", json={"host_name": "A"}).json()
        headers = {"X-Player-Id": body["player_id"], "X-Player-Token": body["player_token"]}
        headers.pop(missing)
        response = client.post(f"/games/{body['code']}/end", headers=headers)
    assert response.status_code == 422


def test_websocket_handshakes_count_against_the_budget():
    with _client(rate_limit_per_minute=1) as client:
        client.get("/health")
        with (
            client.websocket_connect("/games/ABCD/live") as ws,
            pytest.raises(WebSocketDisconnect) as closed,
        ):
            ws.receive_json()
    assert closed.value.code == 4429
