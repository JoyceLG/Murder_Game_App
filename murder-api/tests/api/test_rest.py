import re

from tests.api.conftest import Agent, join, new_game, start, state_for


def test_health_returns_ok(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_openapi_schema_served(client):
    schema = client.get("/openapi.json").json()
    assert "/games" in schema["paths"]
    assert "/games/{code}/live" not in schema["paths"]  # websocket is not in the REST schema


def test_create_game_returns_201_with_player_id_and_secret(client):
    response = client.post("/games", json={"host_name": "Alice"})
    assert response.status_code == 201
    body = response.json()
    assert body["player_id"]
    assert len(body["player_token"]) >= 32
    assert body["status"] == "lobby"
    assert len(body["players"]) == 1
    assert body["me"]["id"] == body["player_id"]
    assert body["version"] == 1
    assert body["server_now"] > 0


def test_create_game_rejects_blank_name(client):
    assert client.post("/games", json={"host_name": ""}).status_code == 422


def test_create_then_join_then_get_state(client):
    code, _ = new_game(client, "Alice")
    assert client.post(f"/games/{code}/players", json={"name": "Bob"}).status_code == 201
    state = state_for(client, code)
    assert {p["name"] for p in state["players"]} == {"Alice", "Bob"}


def test_join_unknown_game_returns_404(client):
    response = client.post("/games/NOPE/players", json={"name": "Bob"})
    assert response.status_code == 404
    assert response.json()["error"] == "GameNotFound"


def test_start_without_player_id_header_returns_422(client):
    code, _ = new_game(client)
    assert client.post(f"/games/{code}/start", json={"duration_min": 15}).status_code == 422


def test_start_with_malformed_player_id_returns_422(client):
    code, host = new_game(client)
    headers = {"X-Player-Id": "not a valid id!", "X-Player-Token": host.token}
    response = client.post(f"/games/{code}/start", json={"duration_min": 15}, headers=headers)
    assert response.status_code == 422


def test_start_by_non_host_returns_403(client):
    code, _ = new_game(client, "Alice")
    bob = join(client, code, "Bob")
    response = client.post(f"/games/{code}/start", json={"duration_min": 15}, headers=bob.headers)
    assert response.status_code == 403
    assert response.json()["error"] == "NotTheHost"


def test_start_with_one_player_returns_409(client):
    code, host = new_game(client)
    response = client.post(f"/games/{code}/start", json={"duration_min": 15}, headers=host.headers)
    assert response.status_code == 409
    assert response.json()["error"] == "NotEnoughPlayers"


def test_full_happy_path_two_players_kill_confirmed_score_increments(client):
    code, alice = new_game(client, "Alice")
    bob = join(client, code, "Bob")
    start(client, code, alice)

    # Two players => Alice's target is necessarily Bob. Alice claims, Bob confirms.
    assert client.post(f"/games/{code}/claims", headers=alice.headers).status_code == 201
    response = client.post(
        f"/games/{code}/claims/{alice.id}/confirm", json={"confirmed": True}, headers=bob.headers
    )
    assert response.status_code == 200
    alice_player = next(p for p in response.json()["players"] if p["id"] == alice.id)
    assert alice_player["score"] == 1


def test_confirm_by_non_target_returns_403(client):
    code, alice = new_game(client, "Alice")
    bob = join(client, code, "Bob")
    carol = join(client, code, "Carol")
    start(client, code, alice)
    client.post(f"/games/{code}/claims", headers=alice.headers)

    alice_target = state_for(client, code, alice)["me"]["target_id"]
    non_target = next(p for p in (bob, carol) if p.id != alice_target)

    response = client.post(
        f"/games/{code}/claims/{alice.id}/confirm",
        json={"confirmed": True},
        headers=non_target.headers,
    )
    assert response.status_code == 403
    assert response.json()["error"] == "NotTheClaimTarget"


# --- #14: the attacker acknowledges the result before the next mission ---------------


def _claimed(client):
    """Two players, started; Alice (whose target is necessarily Bob) has claimed."""
    code, alice = new_game(client, "Alice")
    bob = join(client, code, "Bob")
    start(client, code, alice)
    assert client.post(f"/games/{code}/claims", headers=alice.headers).status_code == 201
    return code, alice, bob


def _answer(client, code, alice, bob, confirmed):
    return client.post(
        f"/games/{code}/claims/{alice.id}/confirm",
        json={"confirmed": confirmed},
        headers=bob.headers,
    )


def test_attacker_sees_the_confirmation_then_acknowledges_it(client):
    code, alice, bob = _claimed(client)
    before = state_for(client, code, alice)["me"]

    _answer(client, code, alice, bob, True)
    waiting = state_for(client, code, alice)
    assert waiting["me"]["score"] == 1
    assert waiting["me"]["mission"] == before["mission"]  # nothing dealt yet
    assert [c["status"] for c in waiting["claims"]] == ["ok"]

    acked = client.post(f"/games/{code}/claims/{alice.id}/ack", headers=alice.headers)
    assert acked.status_code == 200
    assert acked.json()["claims"] == []
    assert acked.json()["me"]["mission"] != before["mission"]
    assert acked.json()["me"]["score"] == 1


def test_attacker_sees_the_refusal_then_acknowledges_it(client):
    code, alice, bob = _claimed(client)
    _answer(client, code, alice, bob, False)
    assert [c["status"] for c in state_for(client, code, alice)["claims"]] == ["no"]
    acked = client.post(f"/games/{code}/claims/{alice.id}/ack", headers=alice.headers)
    assert acked.status_code == 200
    assert acked.json()["me"]["score"] == 0


def test_only_the_attacker_may_acknowledge(client):
    code, alice, bob = _claimed(client)
    _answer(client, code, alice, bob, True)
    response = client.post(f"/games/{code}/claims/{alice.id}/ack", headers=bob.headers)
    assert response.status_code == 403
    assert response.json()["error"] == "NotTheClaimAttacker"


def test_acknowledging_a_pending_claim_is_refused(client):
    code, alice, _ = _claimed(client)
    response = client.post(f"/games/{code}/claims/{alice.id}/ack", headers=alice.headers)
    assert response.status_code == 409
    assert response.json()["error"] == "ClaimNotResolved"


def test_answering_twice_is_refused(client):
    code, alice, bob = _claimed(client)
    _answer(client, code, alice, bob, True)
    response = _answer(client, code, alice, bob, True)
    assert response.status_code == 409
    assert response.json()["error"] == "ClaimAlreadyResolved"


def test_no_new_claim_or_swap_before_acknowledging(client):
    code, alice, bob = _claimed(client)
    _answer(client, code, alice, bob, True)
    for path in ("claims", "swap-mission"):
        response = client.post(f"/games/{code}/{path}", headers=alice.headers)
        assert response.status_code == 409, path
        assert response.json()["error"] == "ClaimAwaitingAck"


# --- #20 ---------------------------------------------------------------------------------


def test_negative_or_zero_score_goal_is_rejected(client):
    code, alice = new_game(client, "Alice")
    for goal in (0, -2):
        response = client.patch(
            f"/games/{code}/config",
            json={"max_players": 12, "max_score": goal},
            headers=alice.headers,
        )
        assert response.status_code == 422, goal


def test_target_with_a_claim_to_answer_can_neither_claim_nor_swap(client):
    code, alice, bob = _claimed(client)  # Alice claimed Bob
    for path in ("claims", "swap-mission"):
        response = client.post(f"/games/{code}/{path}", headers=bob.headers)
        assert response.status_code == 409, path
        assert response.json()["error"] == "MustAnswerClaimFirst"


def test_last_player_left_in_a_running_game_ends_it(client):
    code, alice = new_game(client, "Alice")
    bob = join(client, code, "Bob")
    start(client, code, alice)
    client.request("DELETE", f"/games/{code}/players/me", headers=bob.headers)
    assert state_for(client, code, alice)["status"] == "ended"


# --- B2: the public id is not a credential ---------------------------------------------


def test_impersonating_the_target_with_its_public_id_is_refused(client):
    code, alice = new_game(client, "Alice")
    bob = join(client, code, "Bob")
    start(client, code, alice)
    client.post(f"/games/{code}/claims", headers=alice.headers)

    # Alice knows Bob's public id (it is in the roster) but not Bob's secret.
    forged = Agent(bob.id, alice.token)
    response = client.post(
        f"/games/{code}/claims/{alice.id}/confirm",
        json={"confirmed": True},
        headers=forged.headers,
    )
    assert response.status_code == 401
    assert response.json()["error"] == "NotAuthenticated"
    assert state_for(client, code, alice)["me"]["score"] == 0


def test_action_without_secret_returns_422(client):
    code, alice = new_game(client, "Alice")
    response = client.post(
        f"/games/{code}/missions", json={"text": "x"}, headers={"X-Player-Id": alice.id}
    )
    assert response.status_code == 422


def test_a_secret_from_another_game_is_refused(client):
    code_a, alice = new_game(client, "Alice")
    code_b, _ = new_game(client, "Zed")
    response = client.post(f"/games/{code_b}/missions", json={"text": "x"}, headers=alice.headers)
    assert response.status_code == 401


def test_get_with_bad_credentials_returns_401(client):
    code, alice = new_game(client, "Alice")
    response = client.get(f"/games/{code}", headers=Agent(alice.id, "wrong").headers)
    assert response.status_code == 401


# --- B3: each player sees only their own secrets ---------------------------------------


def test_state_never_exposes_other_players_missions_or_targets(client):
    code, alice = new_game(client, "Alice")
    bob = join(client, code, "Bob")
    carol = join(client, code, "Carol")
    start(client, code, alice)

    view = state_for(client, code, bob)

    assert view["me"]["id"] == bob.id
    assert view["me"]["mission"]
    assert view["me"]["target_id"] in {alice.id, carol.id}
    for player in view["players"] + view["ranking"]:
        assert set(player) == {"id", "name", "score"}


def test_claims_are_only_shown_to_the_attacker_and_the_target(client):
    code, alice = new_game(client, "Alice")
    bob = join(client, code, "Bob")
    carol = join(client, code, "Carol")
    start(client, code, alice)
    client.post(f"/games/{code}/claims", headers=alice.headers)
    target_id = state_for(client, code, alice)["me"]["target_id"]
    target = bob if bob.id == target_id else carol
    bystander = carol if target is bob else bob

    assert [c["atk"] for c in state_for(client, code, alice)["claims"]] == [alice.id]
    assert [c["atk"] for c in state_for(client, code, target)["claims"]] == [alice.id]
    assert state_for(client, code, bystander)["claims"] == []


def test_anonymous_view_has_no_secrets(client):
    code, alice = new_game(client, "Alice")
    join(client, code, "Bob")
    start(client, code, alice)
    view = state_for(client, code)
    assert view["me"] is None
    assert view["claims"] == []


# --- config, missions, swap, end, leave ------------------------------------------------


def test_update_config_by_host_sets_caps_and_is_visible(client):
    code, host = new_game(client, "Alice")
    join(client, code, "Bob")
    response = client.patch(
        f"/games/{code}/config", json={"max_players": 6, "max_score": 5}, headers=host.headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["max_players"] == 6
    assert body["max_score"] == 5
    # visible to anyone reading the game state
    assert state_for(client, code)["max_score"] == 5


def test_update_config_by_non_host_returns_403(client):
    code, _ = new_game(client, "Alice")
    bob = join(client, code, "Bob")
    response = client.patch(
        f"/games/{code}/config", json={"max_players": 6, "max_score": 5}, headers=bob.headers
    )
    assert response.status_code == 403
    assert response.json()["error"] == "NotTheHost"


def test_join_beyond_max_players_returns_409(client):
    code, host = new_game(client, "Alice")
    join(client, code, "Bob")
    client.patch(f"/games/{code}/config", json={"max_players": 2}, headers=host.headers)
    response = client.post(f"/games/{code}/players", json={"name": "Carol"})
    assert response.status_code == 409
    assert response.json()["error"] == "TooManyPlayers"


def test_join_after_start_returns_409_already_started(client):
    code, host = new_game(client, "Alice")
    join(client, code, "Bob")
    start(client, code, host)
    response = client.post(f"/games/{code}/players", json={"name": "Carol"})
    assert response.status_code == 409
    assert response.json()["error"] == "GameAlreadyStarted"


def test_score_cap_ends_game_on_confirmation(client):
    code, alice = new_game(client, "Alice")
    bob = join(client, code, "Bob")
    client.patch(
        f"/games/{code}/config", json={"max_players": 12, "max_score": 1}, headers=alice.headers
    )
    start(client, code, alice)
    # Two players => Alice targets Bob. One confirmed kill reaches the cap of 1.
    client.post(f"/games/{code}/claims", headers=alice.headers)
    response = client.post(
        f"/games/{code}/claims/{alice.id}/confirm", json={"confirmed": True}, headers=bob.headers
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ended"


def test_add_and_remove_pooled_mission(client):
    code, alice = new_game(client, "Alice")
    bob = join(client, code, "Bob")
    added = client.post(
        f"/games/{code}/missions", json={"text": "Custom mission"}, headers=bob.headers
    )
    assert added.status_code == 200
    pool = added.json()["mission_pool"]
    assert len(pool) == 1
    assert pool[0]["text"] == "Custom mission"
    assert pool[0]["by"] == bob.id
    mid = pool[0]["id"]

    # The host may remove a mission added by another player.
    removed = client.request("DELETE", f"/games/{code}/missions/{mid}", headers=alice.headers)
    assert removed.status_code == 200
    assert removed.json()["mission_pool"] == []


def test_add_mission_rejects_blank(client):
    code, alice = new_game(client, "Alice")
    response = client.post(f"/games/{code}/missions", json={"text": ""}, headers=alice.headers)
    assert response.status_code == 422


def test_add_mission_rejects_catalogue_key(client):
    code, alice = new_game(client, "Alice")
    response = client.post(
        f"/games/{code}/missions", json={"text": "core.03"}, headers=alice.headers
    )
    assert response.status_code == 422
    assert response.json()["error"] == "InvalidMission"


def test_started_game_deals_catalogue_keys(client):
    code, alice = new_game(client, "Alice")
    join(client, code, "Bob")
    view = start(client, code, alice)
    assert re.fullmatch(r"core\.\d{2}", view["me"]["mission"])


def test_custom_pool_in_replace_mode_deals_literal_text(client):
    code, alice = new_game(client, "Alice")
    join(client, code, "Bob")
    client.post(f"/games/{code}/missions", json={"text": "Chante en canon"}, headers=alice.headers)
    client.patch(
        f"/games/{code}/config",
        json={"max_players": 12, "mission_mode": "replace"},
        headers=alice.headers,
    )
    assert start(client, code, alice)["me"]["mission"] == "Chante en canon"


def test_config_mission_mode_round_trips(client):
    code, alice = new_game(client, "Alice")
    join(client, code, "Bob")
    response = client.patch(
        f"/games/{code}/config",
        json={"max_players": 12, "mission_mode": "replace"},
        headers=alice.headers,
    )
    assert response.status_code == 200
    assert response.json()["mission_mode"] == "replace"


def test_swap_mission_is_free_once_at_zero_points_then_refused(client):
    code, alice = new_game(client, "Alice")
    join(client, code, "Bob")
    assert start(client, code, alice)["me"]["swap_cost"] == 0
    response = client.post(f"/games/{code}/swap-mission", headers=alice.headers)
    assert response.status_code == 200
    assert response.json()["me"]["score"] == 0  # the free swap
    assert response.json()["me"]["swap_cost"] is None
    again = client.post(f"/games/{code}/swap-mission", headers=alice.headers)
    assert again.status_code == 409
    assert again.json()["error"] == "SwapNotAllowed"


def test_every_change_bumps_the_version(client):
    code, alice = new_game(client, "Alice")
    v1 = state_for(client, code, alice)["version"]
    join(client, code, "Bob")
    v2 = state_for(client, code, alice)["version"]
    assert v2 == v1 + 1


def test_end_game_by_host_sets_ended(client):
    code, alice = new_game(client, "Alice")
    join(client, code, "Bob")
    start(client, code, alice)
    response = client.post(f"/games/{code}/end", headers=alice.headers)
    assert response.status_code == 200
    assert response.json()["status"] == "ended"


def test_end_game_in_lobby_returns_409(client):
    code, alice = new_game(client, "Alice")
    response = client.post(f"/games/{code}/end", headers=alice.headers)
    assert response.status_code == 409
    assert response.json()["error"] == "GameNotRunning"


def test_leave_game_removes_player(client):
    code, _ = new_game(client, "Alice")
    bob = join(client, code, "Bob")
    response = client.request("DELETE", f"/games/{code}/players/me", headers=bob.headers)
    assert response.status_code == 200
    assert all(p["id"] != bob.id for p in response.json()["players"])


def test_leaving_an_ended_game_keeps_everyone_in_the_final_ranking(client):
    code, alice = new_game(client, "Alice")
    bob = join(client, code, "Bob")
    start(client, code, alice)
    client.post(f"/games/{code}/end", headers=alice.headers)

    for agent in (alice, bob):
        response = client.request("DELETE", f"/games/{code}/players/me", headers=agent.headers)
        assert response.status_code == 200

    final = state_for(client, code)
    assert {p["id"] for p in final["ranking"]} == {alice.id, bob.id}
