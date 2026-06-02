from tests.api.conftest import new_game

HEADER = "X-Player-Id"


def test_websocket_receives_initial_snapshot_on_connect(client):
    code, _ = new_game(client, "Alice")
    with client.websocket_connect(f"/games/{code}/live") as ws:
        snapshot = ws.receive_json()
    assert snapshot["code"] == code
    assert snapshot["status"] == "lobby"
    assert snapshot["players"][0]["name"] == "Alice"


def test_rest_join_pushes_updated_state_to_open_socket(client):
    code, _ = new_game(client, "Alice")
    with client.websocket_connect(f"/games/{code}/live") as ws:
        ws.receive_json()  # initial snapshot
        client.post(f"/games/{code}/players", json={"name": "Bob"})
        pushed = ws.receive_json()
    assert any(p["name"] == "Bob" for p in pushed["players"])


def test_two_sockets_same_code_both_receive_push(client):
    code, _ = new_game(client, "Alice")
    with (
        client.websocket_connect(f"/games/{code}/live") as ws1,
        client.websocket_connect(f"/games/{code}/live") as ws2,
    ):
        ws1.receive_json()
        ws2.receive_json()
        client.post(f"/games/{code}/players", json={"name": "Bob"})
        msg1 = ws1.receive_json()
        msg2 = ws2.receive_json()
    assert any(p["name"] == "Bob" for p in msg1["players"])
    assert any(p["name"] == "Bob" for p in msg2["players"])


def test_socket_only_receives_pushes_for_its_own_code(client):
    code_a, _ = new_game(client, "Alice")
    code_b, _ = new_game(client, "Zed")
    with client.websocket_connect(f"/games/{code_b}/live") as ws_b:
        ws_b.receive_json()  # b's initial snapshot
        client.post(f"/games/{code_a}/players", json={"name": "Bob"})  # push to A only
        client.post(f"/games/{code_b}/players", json={"name": "Max"})  # push to B
        # If the A push had leaked into B's socket, this would be A's state instead of B's.
        message = ws_b.receive_json()
    assert message["code"] == code_b
    assert any(p["name"] == "Max" for p in message["players"])
