import asyncio

from src.api import ws_notifier
from src.api.ws_notifier import CLOSE_GAME_NOT_FOUND, CLOSE_NOT_A_PLAYER, WebSocketNotifier
from tests.builders import make_game
from tests.doubles import FakeClock


class _Socket:
    def __init__(self) -> None:
        self.sent: list[dict] = []
        self.closed_with: int | None = None

    async def send_json(self, payload):
        self.sent.append(payload)

    async def close(self, code: int = 1000):
        self.closed_with = code


class _BrokenSocket(_Socket):
    async def send_json(self, _payload):
        raise RuntimeError("socket is gone")


class _StalledSocket(_Socket):
    async def send_json(self, _payload):
        await asyncio.sleep(3600)


async def test_publish_drops_socket_that_fails_to_send():
    notifier = WebSocketNotifier(FakeClock())
    game = make_game(["a"], code="ABCD")
    broken = _BrokenSocket()
    notifier.subscribe("ABCD", broken, "a")

    await notifier.publish(game)  # must not raise

    assert "ABCD" not in notifier.watched_codes()  # the room emptied and was removed


async def test_publish_sends_each_viewer_their_own_view():
    notifier = WebSocketNotifier(FakeClock())
    game = make_game(["a", "b"], code="ABCD")
    game.players["a"].mission = "secret-a"
    game.players["b"].mission = "secret-b"
    sock_a, sock_b = _Socket(), _Socket()
    notifier.subscribe("ABCD", sock_a, "a")
    notifier.subscribe("ABCD", sock_b, "b")

    await notifier.publish(game)

    assert sock_a.sent[0]["me"]["mission"] == "secret-a"
    assert sock_b.sent[0]["me"]["mission"] == "secret-b"
    assert "secret-b" not in str(sock_a.sent)


async def test_publish_disconnects_viewers_no_longer_in_the_game():
    notifier = WebSocketNotifier(FakeClock())
    gone = _Socket()
    notifier.subscribe("ABCD", gone, "left")

    await notifier.publish(make_game(["a"], code="ABCD"))

    assert gone.closed_with == CLOSE_NOT_A_PLAYER
    assert gone.sent == []


async def test_a_stalled_client_does_not_hold_up_the_others(monkeypatch):
    monkeypatch.setattr(ws_notifier, "SEND_TIMEOUT_SEC", 0.05)
    notifier = WebSocketNotifier(FakeClock())
    stalled, healthy = _StalledSocket(), _Socket()
    notifier.subscribe("ABCD", stalled, "a")
    notifier.subscribe("ABCD", healthy, "b")

    await asyncio.wait_for(notifier.publish(make_game(["a", "b"], code="ABCD")), 1)

    assert len(healthy.sent) == 1
    notifier.unsubscribe("ABCD", healthy)
    assert notifier.watched_codes() == []  # the stalled socket was dropped


async def test_close_disconnects_everyone_and_forgets_the_room():
    notifier = WebSocketNotifier(FakeClock())
    first, second = _Socket(), _Socket()
    notifier.subscribe("ABCD", first, "a")
    notifier.subscribe("ABCD", second, "b")

    await notifier.close("ABCD")

    assert first.closed_with == second.closed_with == CLOSE_GAME_NOT_FOUND
    assert notifier.watched_codes() == []


async def test_unsubscribe_unknown_room_is_a_no_op():
    WebSocketNotifier(FakeClock()).unsubscribe("NOPE", _Socket())
