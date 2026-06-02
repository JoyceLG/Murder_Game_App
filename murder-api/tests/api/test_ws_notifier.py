from src.adapters.memory_repository import InMemoryGameRepository
from src.api.ws_notifier import WebSocketNotifier
from tests.builders import make_game
from tests.doubles import FakeClock


class _BrokenSocket:
    async def send_json(self, _payload):
        raise RuntimeError("socket is gone")


async def test_publish_drops_socket_that_fails_to_send():
    repo = InMemoryGameRepository()
    notifier = WebSocketNotifier(repo, FakeClock())
    game = make_game(["a"], code="ABCD")
    await repo.save(game)
    broken = _BrokenSocket()
    notifier._rooms["ABCD"].add(broken)  # white-box: inject a dead connection

    await notifier.publish(game)  # must not raise

    assert broken not in notifier._rooms["ABCD"]
