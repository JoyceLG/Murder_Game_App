"""End-to-end fixtures. The stack under test is given by environment variables:

E2E_APP_URL  where the Angular app is served (default http://localhost:8080, the compose front)
E2E_API_URL  where the API answers (default: same as the app — through nginx or a dev proxy)
E2E_NGINX=1  the app is served by the production nginx: also check its headers, caching and
             SPA fallback (scripts/e2e.sh compose sets it; skipped otherwise)
"""

from __future__ import annotations

import json
import os
import re
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass

import httpx
import pytest
from playwright.sync_api import Browser, Page, expect
from websockets.exceptions import ConnectionClosed
from websockets.sync.client import ClientConnection, connect

APP_URL = os.environ.get("E2E_APP_URL", "http://localhost:8080").rstrip("/")
API_URL = os.environ.get("E2E_API_URL", APP_URL).rstrip("/")
WS_URL = "ws" + API_URL.removeprefix("http")
BEHIND_NGINX = os.environ.get("E2E_NGINX") == "1"


def pytest_collection_modifyitems(config, items):
    if BEHIND_NGINX:
        return
    skip = pytest.mark.skip(reason="not behind the production nginx (set E2E_NGINX=1)")
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


class Agents:
    """Players in their own browser contexts (French UI by default). Collects page errors and
    console errors from every page, and closes every context at the end of the test."""

    def __init__(self, browser: Browser, context_args: dict, base_url: str) -> None:
        self._browser, self._args, self.base_url = browser, context_args, base_url
        self._contexts = []
        self.errors: list[str] = []

    def new(self, locale: str = "fr-FR", **context_options) -> Page:
        context = self._browser.new_context(**{**self._args, "locale": locale, **context_options})
        self._contexts.append(context)
        page = context.new_page()
        page.on("pageerror", lambda exc: self.errors.append(f"pageerror: {exc}"))
        page.on("console", lambda m: m.type == "error" and self.errors.append(f"console: {m.text}"))
        return page

    def create_game(self, page: Page, name: str = "Hôte") -> str:
        """Create a game from the French home screen; return its code."""
        page.goto(f"{self.base_url}/")
        page.get_by_placeholder("Ex. Corbeau").fill(name)
        page.get_by_role("button", name="Créer une partie").click()
        page.wait_for_url(re.compile(r"/g/[A-Z0-9]{4}$"))
        return page.url.rsplit("/", 1)[-1]

    def join_game(self, page: Page, code: str, name: str = "Invité") -> None:
        """Join from the French home screen."""
        page.goto(f"{self.base_url}/")
        page.get_by_placeholder("Ex. Corbeau").fill(name)
        page.get_by_placeholder("••••").fill(code)
        page.get_by_role("button", name="Rejoindre").click()
        page.wait_for_url(f"**/g/{code}")

    def start_two_player_game(self, host: Page, guest: Page) -> str:
        code = self.create_game(host)
        self.join_game(guest, code)
        expect(host.get_by_text("Agents recrutés — 2")).to_be_visible()
        host.get_by_role("button", name="Lancer l'opération").click()
        host.wait_for_url(f"**/g/{code}/play")
        guest.wait_for_url(f"**/g/{code}/play")
        return code

    def close(self) -> None:
        for context in self._contexts:
            context.close()


@pytest.fixture
def agents(browser, browser_context_args, base_url) -> Iterator[Agents]:
    crew = Agents(browser, browser_context_args, base_url)
    yield crew
    crew.close()
