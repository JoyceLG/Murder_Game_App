import pytest
from fastapi.testclient import TestClient

from src.api.main import create_app


@pytest.fixture
def client() -> TestClient:
    # Default wiring: in-memory repository + real WebSocket notifier, fresh per test.
    with TestClient(create_app()) as test_client:
        yield test_client


def new_game(client: TestClient, host_name: str = "Alice") -> tuple[str, str]:
    """Create a game; return (code, host_player_id)."""
    body = client.post("/games", json={"host_name": host_name}).json()
    return body["code"], body["player_id"]


def join(client: TestClient, code: str, name: str) -> str:
    """Join a game; return the new player's id."""
    return client.post(f"/games/{code}/players", json={"name": name}).json()["player_id"]
