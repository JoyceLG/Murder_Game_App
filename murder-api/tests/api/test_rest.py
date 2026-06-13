from tests.api.conftest import join, new_game

HEADER = "X-Player-Id"


def test_health_returns_ok(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_openapi_schema_served(client):
    schema = client.get("/openapi.json").json()
    assert "/games" in schema["paths"]
    assert "/games/{code}/live" not in schema["paths"]  # websocket is not in the REST schema


def test_create_game_returns_201_and_player_id(client):
    response = client.post("/games", json={"host_name": "Alice"})
    assert response.status_code == 201
    body = response.json()
    assert body["player_id"]
    assert body["status"] == "lobby"
    assert len(body["players"]) == 1


def test_create_game_rejects_blank_name(client):
    assert client.post("/games", json={"host_name": ""}).status_code == 422


def test_create_then_join_then_get_state(client):
    code, _ = new_game(client, "Alice")
    assert client.post(f"/games/{code}/players", json={"name": "Bob"}).status_code == 201
    state = client.get(f"/games/{code}").json()
    assert {p["name"] for p in state["players"]} == {"Alice", "Bob"}


def test_join_unknown_game_returns_404(client):
    response = client.post("/games/NOPE/players", json={"name": "Bob"})
    assert response.status_code == 404
    assert response.json()["error"] == "GameNotFound"


def test_start_without_player_id_header_returns_422(client):
    code, _ = new_game(client)
    assert client.post(f"/games/{code}/start", json={"duration_min": 15}).status_code == 422


def test_start_by_non_host_returns_403(client):
    code, _ = new_game(client, "Alice")
    bob = join(client, code, "Bob")
    response = client.post(f"/games/{code}/start", json={"duration_min": 15}, headers={HEADER: bob})
    assert response.status_code == 403
    assert response.json()["error"] == "NotTheHost"


def test_start_with_one_player_returns_409(client):
    code, host = new_game(client)
    response = client.post(
        f"/games/{code}/start", json={"duration_min": 15}, headers={HEADER: host}
    )
    assert response.status_code == 409
    assert response.json()["error"] == "NotEnoughPlayers"


def test_full_happy_path_two_players_kill_confirmed_score_increments(client):
    code, alice = new_game(client, "Alice")
    bob = join(client, code, "Bob")
    client.post(f"/games/{code}/start", json={"duration_min": 15}, headers={HEADER: alice})

    # Two players => Alice's target is necessarily Bob. Alice claims, Bob confirms.
    assert client.post(f"/games/{code}/claims", headers={HEADER: alice}).status_code == 201
    response = client.post(
        f"/games/{code}/claims/{alice}/confirm", json={"confirmed": True}, headers={HEADER: bob}
    )
    assert response.status_code == 200
    alice_player = next(p for p in response.json()["players"] if p["id"] == alice)
    assert alice_player["score"] == 1


def test_confirm_by_non_target_returns_403(client):
    code, alice = new_game(client, "Alice")
    bob = join(client, code, "Bob")
    carol = join(client, code, "Carol")
    client.post(f"/games/{code}/start", json={"duration_min": 15}, headers={HEADER: alice})
    client.post(f"/games/{code}/claims", headers={HEADER: alice})

    state = client.get(f"/games/{code}").json()
    alice_target = next(p["target_id"] for p in state["players"] if p["id"] == alice)
    non_target = next(pid for pid in (bob, carol) if pid != alice_target)

    response = client.post(
        f"/games/{code}/claims/{alice}/confirm",
        json={"confirmed": True},
        headers={HEADER: non_target},
    )
    assert response.status_code == 403
    assert response.json()["error"] == "NotTheClaimTarget"


def test_update_config_by_host_sets_caps_and_is_visible(client):
    code, host = new_game(client, "Alice")
    join(client, code, "Bob")
    response = client.patch(
        f"/games/{code}/config", json={"max_players": 6, "max_score": 5}, headers={HEADER: host}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["max_players"] == 6
    assert body["max_score"] == 5
    # visible to anyone reading the game state
    assert client.get(f"/games/{code}").json()["max_score"] == 5


def test_update_config_by_non_host_returns_403(client):
    code, _ = new_game(client, "Alice")
    bob = join(client, code, "Bob")
    response = client.patch(
        f"/games/{code}/config", json={"max_players": 6, "max_score": 5}, headers={HEADER: bob}
    )
    assert response.status_code == 403
    assert response.json()["error"] == "NotTheHost"


def test_join_beyond_max_players_returns_409(client):
    code, host = new_game(client, "Alice")
    join(client, code, "Bob")
    client.patch(f"/games/{code}/config", json={"max_players": 2}, headers={HEADER: host})
    response = client.post(f"/games/{code}/players", json={"name": "Carol"})
    assert response.status_code == 409
    assert response.json()["error"] == "TooManyPlayers"


def test_score_cap_ends_game_on_confirmation(client):
    code, alice = new_game(client, "Alice")
    bob = join(client, code, "Bob")
    client.patch(
        f"/games/{code}/config", json={"max_players": 12, "max_score": 1}, headers={HEADER: alice}
    )
    client.post(f"/games/{code}/start", json={"duration_min": 15}, headers={HEADER: alice})
    # Two players => Alice targets Bob. One confirmed kill reaches the cap of 1.
    client.post(f"/games/{code}/claims", headers={HEADER: alice})
    response = client.post(
        f"/games/{code}/claims/{alice}/confirm", json={"confirmed": True}, headers={HEADER: bob}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ended"


def test_swap_mission_decrements_score(client):
    code, alice = new_game(client, "Alice")
    join(client, code, "Bob")
    client.post(f"/games/{code}/start", json={"duration_min": 15}, headers={HEADER: alice})
    response = client.post(f"/games/{code}/swap-mission", headers={HEADER: alice})
    assert response.status_code == 200
    alice_player = next(p for p in response.json()["players"] if p["id"] == alice)
    assert alice_player["score"] == -1


def test_end_game_by_host_sets_ended(client):
    code, alice = new_game(client, "Alice")
    join(client, code, "Bob")
    client.post(f"/games/{code}/start", json={"duration_min": 15}, headers={HEADER: alice})
    response = client.post(f"/games/{code}/end", headers={HEADER: alice})
    assert response.status_code == 200
    assert response.json()["status"] == "ended"


def test_leave_game_removes_player(client):
    code, _ = new_game(client, "Alice")
    bob = join(client, code, "Bob")
    response = client.request("DELETE", f"/games/{code}/players/me", headers={HEADER: bob})
    assert response.status_code == 200
    assert all(p["id"] != bob for p in response.json()["players"])
