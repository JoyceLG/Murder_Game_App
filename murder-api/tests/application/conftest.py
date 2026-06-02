import pytest

from src.adapters.memory_repository import InMemoryGameRepository
from src.domain.models import Game
from tests.builders import running_game
from tests.doubles import FakeClock, FirstPicker, SpyNotifier


@pytest.fixture
def repo() -> InMemoryGameRepository:
    return InMemoryGameRepository()


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(now_ms=1_000_000)


@pytest.fixture
def picker() -> FirstPicker:
    return FirstPicker()


@pytest.fixture
def notifier() -> SpyNotifier:
    return SpyNotifier()


def make_running(clock: FakeClock, picker: FirstPicker, player_ids=("h", "p2", "p3")) -> Game:
    """A running game with targets assigned and a 15-minute clock that has not expired."""
    game = running_game(list(player_ids), picker, code="ABCD")
    game.start_at = clock.now_ms()
    game.duration_sec = 900
    game.end_at = clock.now_ms() + 900_000
    return game
