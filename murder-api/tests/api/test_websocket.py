import pytest
from starlette.websockets import WebSocketDisconnect

from src.api.dependencies import get_game_uc
from src.domain.errors import GameNotFound
from tests.api.conftest import join, new_game, start


def test_websocket_receives_initial_snapshot_after_authenticating(client):
    code, alice = new_game(client, "Alice")
    with client.websocket_connect(f"/games/{code}/live") as ws:
        ws.send_json(alice.hello)
        snapshot = ws.receive_json()
    assert snapshot["code"] == code
    assert snapshot["status"] == "lobby"
    assert snapshot["players"][0]["name"] == "Alice"
    assert snapshot["me"]["id"] == alice.id


def test_websocket_with_bad_credentials_is_closed_4401(client):
    code, alice = new_game(client, "Alice")
    with client.websocket_connect(f"/games/{code}/live") as ws:
        ws.send_json({"player_id": alice.id, "token": "guess"})
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()
    assert closed.value.code == 4401


def test_websocket_with_malformed_hello_is_closed_4401(client):
    code, _ = new_game(client, "Alice")
    with client.websocket_connect(f"/games/{code}/live") as ws:
        ws.send_text("not json")
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()
    assert closed.value.code == 4401


def test_websocket_on_unknown_game_is_closed_4404(client):
    _, alice = new_game(client, "Alice")
    with client.websocket_connect("/games/NOPE/live") as ws:
        ws.send_json(alice.hello)
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()
    assert closed.value.code == 4404


def test_websocket_answers_ping_with_pong(client):
    code, alice = new_game(client, "Alice")
    with client.websocket_connect(f"/games/{code}/live") as ws:
        ws.send_json(alice.hello)
        ws.receive_json()
        ws.send_text("ping")
        assert ws.receive_text() == "pong"


def test_rest_join_pushes_updated_state_to_open_socket(client):
    code, alice = new_game(client, "Alice")
    with client.websocket_connect(f"/games/{code}/live") as ws:
        ws.send_json(alice.hello)
        ws.receive_json()  # initial snapshot
        client.post(f"/games/{code}/players", json={"name": "Bob"})
        pushed = ws.receive_json()
    assert any(p["name"] == "Bob" for p in pushed["players"])


def test_each_socket_receives_its_own_players_view(client):
    code, alice = new_game(client, "Alice")
    bob = join(client, code, "Bob")
    with (
        client.websocket_connect(f"/games/{code}/live") as ws_alice,
        client.websocket_connect(f"/games/{code}/live") as ws_bob,
    ):
        ws_alice.send_json(alice.hello)
        ws_bob.send_json(bob.hello)
        ws_alice.receive_json()
        ws_bob.receive_json()
        start(client, code, alice)
        for_alice = ws_alice.receive_json()
        for_bob = ws_bob.receive_json()
    assert for_alice["me"]["id"] == alice.id
    assert for_alice["me"]["target_id"] == bob.id
    assert for_bob["me"]["id"] == bob.id
    assert for_bob["me"]["target_id"] == alice.id
    assert all("mission" not in p for p in for_alice["players"] + for_bob["players"])


def test_socket_only_receives_pushes_for_its_own_code(client):
    code_a, _ = new_game(client, "Alice")
    code_b, zed = new_game(client, "Zed")
    with client.websocket_connect(f"/games/{code_b}/live") as ws_b:
        ws_b.send_json(zed.hello)
        ws_b.receive_json()  # b's initial snapshot
        client.post(f"/games/{code_a}/players", json={"name": "Bob"})  # push to A only
        client.post(f"/games/{code_b}/players", json={"name": "Max"})  # push to B
        # If the A push had leaked into B's socket, this would be A's state instead of B's.
        message = ws_b.receive_json()
    assert message["code"] == code_b
    assert any(p["name"] == "Max" for p in message["players"])


def test_player_who_leaves_is_disconnected_4403(client):
    code, alice = new_game(client, "Alice")
    bob = join(client, code, "Bob")
    with client.websocket_connect(f"/games/{code}/live") as ws:
        ws.send_json(bob.hello)
        ws.receive_json()
        client.request("DELETE", f"/games/{code}/players/me", headers=bob.headers)
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()
    assert closed.value.code == 4403


def test_rest_get_after_the_clock_ran_out_pushes_the_end(client):
    clock = client.app.state.clock
    code, alice = new_game(client, "Alice")
    join(client, code, "Bob")
    start(client, code, alice, minutes=1)
    with client.websocket_connect(f"/games/{code}/live") as ws:
        ws.send_json(alice.hello)
        assert ws.receive_json()["status"] == "running"
        clock.advance(61_000)
        client.get(f"/games/{code}")
        assert ws.receive_json()["status"] == "ended"


def test_client_hanging_up_before_authenticating_is_handled(client):
    code, _ = new_game(client, "Alice")
    with client.websocket_connect(f"/games/{code}/live"):
        pass  # closes without sending the hello
    assert client.app.state.notifier.watched_codes() == []


def test_game_deleted_during_the_handshake_closes_4404(client):
    class _Vanished:
        async def execute(self, code):
            raise GameNotFound(code)

    code, alice = new_game(client, "Alice")
    client.app.dependency_overrides[get_game_uc] = _Vanished
    with client.websocket_connect(f"/games/{code}/live") as ws:
        ws.send_json(alice.hello)
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()
    assert closed.value.code == 4404
    assert client.app.state.notifier.watched_codes() == []


def test_attacker_is_pushed_the_result_of_their_claim(client):
    code, alice = new_game(client, "Alice")
    bob = join(client, code, "Bob")
    start(client, code, alice)
    client.post(f"/games/{code}/claims", headers=alice.headers)
    with client.websocket_connect(f"/games/{code}/live") as ws:
        ws.send_json(alice.hello)
        assert ws.receive_json()["claims"][0]["status"] == "pending"
        client.post(
            f"/games/{code}/claims/{alice.id}/confirm",
            json={"confirmed": True},
            headers=bob.headers,
        )
        pushed = ws.receive_json()
    assert pushed["claims"][0]["status"] == "ok"
    assert pushed["me"]["score"] == 1
