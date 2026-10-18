from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from src.api.config import Settings
from src.api.main import create_app
from tests.doubles import FakeClock


@pytest.fixture
def client() -> TestClient:
    # Default wiring (in-memory repository + real WebSocket notifier), fresh per test, with a
    # controllable clock: tests reach it as `client.app.state.clock`.
    with TestClient(create_app(settings=Settings(), clock=FakeClock())) as test_client:
        yield test_client


@dataclass(frozen=True)
class Agent:
    """A player as the API client knows them: public id + session secret."""

    id: str
    token: str

    @property
    def headers(self) -> dict[str, str]:
        return {"X-Player-Id": self.id, "X-Player-Token": self.token}

    @property
    def hello(self) -> dict[str, str]:
        """The WebSocket authentication message."""
        return {"player_id": self.id, "token": self.token}


def new_game(client: TestClient, host_name: str = "Alice") -> tuple[str, Agent]:
    """Create a game; return (code, host)."""
    body = client.post("/games", json={"host_name": host_name}).json()
    return body["code"], Agent(body["player_id"], body["player_token"])


def join(client: TestClient, code: str, name: str) -> Agent:
    """Join a game; return the new player."""
    body = client.post(f"/games/{code}/players", json={"name": name}).json()
    return Agent(body["player_id"], body["player_token"])


def start(client: TestClient, code: str, host: Agent, minutes: int = 15) -> dict:
    return client.post(
        f"/games/{code}/start", json={"duration_min": minutes}, headers=host.headers
    ).json()


def state_for(client: TestClient, code: str, agent: Agent | None = None) -> dict:
    return client.get(f"/games/{code}", headers=agent.headers if agent else {}).json()
