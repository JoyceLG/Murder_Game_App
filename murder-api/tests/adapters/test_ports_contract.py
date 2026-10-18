"""Each concrete adapter structurally satisfies its port — the heart of ports & adapters."""

from src.adapters.identifiers import RandomCodeGenerator, TokenGenerator, UuidGenerator
from src.adapters.memory_repository import InMemoryGameRepository
from src.adapters.system_clock import SystemClock
from src.api.ws_notifier import WebSocketNotifier
from src.ports.clock import Clock
from src.ports.identifiers import CodeGenerator, IdGenerator, SecretGenerator
from src.ports.notifier import RealtimeNotifier
from src.ports.repository import GameRepository
from tests.doubles import SpyNotifier


def test_in_memory_repository_satisfies_repository_port():
    assert isinstance(InMemoryGameRepository(), GameRepository)


def test_system_clock_satisfies_clock_port():
    assert isinstance(SystemClock(), Clock)


def test_identifier_adapters_satisfy_their_ports():
    assert isinstance(UuidGenerator(), IdGenerator)
    assert isinstance(RandomCodeGenerator(), CodeGenerator)
    assert isinstance(TokenGenerator(), SecretGenerator)


def test_spy_notifier_satisfies_notifier_port():
    assert isinstance(SpyNotifier(), RealtimeNotifier)


def test_websocket_notifier_satisfies_notifier_port():
    assert isinstance(WebSocketNotifier(SystemClock()), RealtimeNotifier)
