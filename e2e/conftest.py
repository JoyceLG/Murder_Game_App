"""End-to-end fixtures. The stack under test is given by environment variables:

E2E_APP_URL  where the Angular app is served (default http://localhost:8080, the compose front)
E2E_API_URL  where the API answers (default: same as the app, i.e. through nginx)

When both are the same origin the suite also checks the nginx-specific behaviour (headers,
caching, SPA fallback); against `ng serve` + uvicorn those checks are skipped.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass

import httpx
import pytest
from websockets.exceptions import ConnectionClosed
from websockets.sync.client import ClientConnection, connect

APP_URL = os.environ.get("E2E_APP_URL", "http://localhost:8080").rstrip("/")
API_URL = os.environ.get("E2E_API_URL", APP_URL).rstrip("/")
WS_URL = "ws" + API_URL.removeprefix("http")
BEHIND_NGINX = APP_URL == API_URL


def pytest_collection_modifyitems(config, items):
    if BEHIND_NGINX:
        return
    skip = pytest.mark.skip(reason="not behind the nginx front (E2E_API_URL != E2E_APP_URL)")
    for item in items:
        if "nginx" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(scope="session", autouse=True)
def stack_is_up() -> None:
    deadline = time.monotonic() + 60
    while True:
        try:
            if httpx.get(f"{API_URL}/health", timeout=2).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        if time.monotonic() > deadline:
            pytest.exit(
                f"stack not reachable at {API_URL}/health — is it running?",
                returncode=2,
            )
        time.sleep(1)


@pytest.fixture(scope="session")
def base_url() -> str:
    """Base URL for Playwright pages (overrides pytest-base-url)."""
    return APP_URL


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    # French UI (the app picks the device language), phone-sized viewport like real players.
    return {
        **browser_context_args,
        "locale": "fr-FR",
        "viewport": {"width": 390, "height": 844},
    }


@pytest.fixture
def api() -> Iterator[httpx.Client]:
    with httpx.Client(base_url=API_URL, timeout=10) as client:
        yield client


@dataclass(frozen=True)
class Agent:
    id: str
    token: str
    name: str

    @property
    def headers(self) -> dict[str, str]:
        return {"X-Player-Id": self.id, "X-Player-Token": self.token}


def new_game(api: httpx.Client, name: str = "Alice") -> tuple[str, Agent]:
    response = api.post("/games", json={"host_name": name})
    assert response.status_code == 201, response.text
    body = response.json()
    return body["code"], Agent(body["player_id"], body["player_token"], name)


def join(api: httpx.Client, code: str, name: str) -> Agent:
    response = api.post(f"/games/{code}/players", json={"name": name})
    assert response.status_code == 201, response.text
    body = response.json()
    return Agent(body["player_id"], body["player_token"], name)


class Live:
    """A player's authenticated WebSocket, as the Angular client opens it."""

    def __init__(self, code: str, agent: Agent | None, hello: dict | None = None) -> None:
        self.ws: ClientConnection = connect(f"{WS_URL}/games/{code}/live", open_timeout=10)
        payload = hello if hello is not None else {"player_id": agent.id, "token": agent.token}
        self.ws.send(json.dumps(payload))

    def next_state(self, until: Callable[[dict], bool] = lambda s: True, timeout=10) -> dict:
        """The next pushed state matching `until` (skips pongs and older states)."""
        deadline = time.monotonic() + timeout
        while True:
            message = self.ws.recv(timeout=max(0.1, deadline - time.monotonic()))
            if message == "pong":
                continue
            state = json.loads(message)
            if until(state):
                return state

    def close_code(self, timeout=10) -> int:
        try:
            while True:
                self.ws.recv(timeout=timeout)
        except ConnectionClosed as closed:
            return closed.rcvd.code if closed.rcvd else -1

    def close(self) -> None:
        self.ws.close()
