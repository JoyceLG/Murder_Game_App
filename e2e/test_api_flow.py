"""A whole game over the real network path: REST + WebSocket, PostgreSQL, (nginx)."""

import re
from collections import Counter

import pytest
from conftest import Agent, Live, join, new_game


@pytest.fixture
def table(api):
    """A lobby with three agents, each with an open live socket."""
    code, alice = new_game(api, "Alice")
    bob, carol = join(api, code, "Bob"), join(api, code, "Carol")
    agents = [alice, bob, carol]
    lives = {a.id: Live(code, a) for a in agents}
    for live in lives.values():
        assert live.next_state()["status"] == "lobby"
    yield code, agents, lives
    for live in lives.values():
        live.close()


def test_full_game(api, table):
    code, (alice, bob, carol), lives = table
    by_id = {a.id: a for a in (alice, bob, carol)}

    # --- start: everyone gets their own view, and the targets form one ring --------------
    assert api.post(
        f"/games/{code}/start", json={"duration_min": 10}, headers=alice.headers
    ).is_success
    views = {
        pid: live.next_state(lambda s: s["status"] == "running") for pid, live in lives.items()
    }
    targets = {pid: view["me"]["target_id"] for pid, view in views.items()}
    assert all(views[pid]["me"]["id"] == pid for pid in views)
    assert all(target != pid for pid, target in targets.items())
    assert Counter(targets.values()) == Counter({pid: 1 for pid in by_id})
    for view in views.values():  # nobody receives anybody else's secrets
        assert all(set(p) == {"id", "name", "score"} for p in view["players"])
        # default missions travel as catalogue keys, translated by each client
        assert re.fullmatch(r"core\.\d{2}", view["me"]["mission"])

    # --- Alice claims; only her target is asked to confirm --------------------------------
    victim = by_id[targets[alice.id]]
    bystander = next(a for a in (bob, carol) if a is not victim)
    assert api.post(f"/games/{code}/claims", headers=alice.headers).status_code == 201
    asked = lives[victim.id].next_state(lambda s: bool(s["claims"]))
    assert asked["claims"][0]["atk"] == alice.id
    assert lives[bystander.id].next_state()["claims"] == []

    # The bystander knows Alice's id and the victim's id, but cannot answer in the victim's name.
    forged = Agent(victim.id, bystander.token, "forged")
    response = api.post(
        f"/games/{code}/claims/{alice.id}/confirm",
        json={"confirmed": True},
        headers=forged.headers,
    )
    assert response.status_code == 401

    # --- the victim confirms: Alice scores at once, but waits to see it before moving on ----
    response = api.post(
        f"/games/{code}/claims/{alice.id}/confirm", json={"confirmed": True}, headers=victim.headers
    )
    assert response.status_code == 200
    scored = lives[alice.id].next_state(lambda s: s["me"]["score"] == 1)
    assert [c["status"] for c in scored["claims"]] == ["ok"]
    assert scored["me"]["target_id"] == victim.id  # nothing dealt before the ack
    # only Alice may acknowledge her result
    response = api.post(f"/games/{code}/claims/{alice.id}/ack", headers=victim.headers)
    assert response.status_code == 403
    assert api.post(f"/games/{code}/claims/{alice.id}/ack", headers=alice.headers).is_success
    moved_on = lives[alice.id].next_state(lambda s: not s["claims"])
    assert moved_on["me"]["target_id"] not in (alice.id, victim.id)
    assert moved_on["me"]["mission"] != scored["me"]["mission"]

    # --- the host ends it; leaving afterwards keeps everyone in the final ranking ----------
    assert api.post(f"/games/{code}/end", headers=alice.headers).is_success
    for live in lives.values():
        live.next_state(lambda s: s["status"] == "ended")
    for agent in (alice, bob, carol):
        assert api.request("DELETE", f"/games/{code}/players/me", headers=agent.headers).is_success
    final = api.get(f"/games/{code}").json()
    assert [p["name"] for p in final["ranking"]][0] == "Alice"
    assert len(final["ranking"]) == 3


def test_reconnecting_player_gets_a_fresh_snapshot(api):
    code, alice = new_game(api)
    first = Live(code, alice)
    v1 = first.next_state()["version"]
    first.close()
    join(api, code, "Bob")  # happens while Alice is offline
    again = Live(code, alice)
    snapshot = again.next_state()
    again.close()
    assert snapshot["version"] > v1
    assert {p["name"] for p in snapshot["players"]} == {"Alice", "Bob"}


def test_socket_with_a_wrong_secret_is_refused(api):
    code, alice = new_game(api)
    live = Live(code, None, hello={"player_id": alice.id, "token": "nope"})
    assert live.close_code() == 4401


def test_socket_on_an_unknown_game_is_refused(api):
    _, alice = new_game(api)
    live = Live("ZZZZ", alice)
    assert live.close_code() == 4404


def test_socket_answers_pings(api):
    code, alice = new_game(api)
    live = Live(code, alice)
    live.next_state()
    live.ws.send("ping")
    assert live.ws.recv(timeout=5) == "pong"
    live.close()


def test_player_who_leaves_is_disconnected(api):
    code, alice = new_game(api)
    bob = join(api, code, "Bob")
    live = Live(code, bob)
    live.next_state()
    assert api.request("DELETE", f"/games/{code}/players/me", headers=bob.headers).is_success
    assert live.close_code() == 4403


def test_concurrent_joins_all_land(api):
    import concurrent.futures

    code, _ = new_game(api)
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        agents = list(pool.map(lambda i: join(api, code, f"P{i}"), range(6)))
    state = api.get(f"/games/{code}").json()
    assert {a.id for a in agents} <= {p["id"] for p in state["players"]}
    assert len(state["players"]) == 7


def test_last_player_standing_ends_the_game(api):
    code, alice = new_game(api)
    bob = join(api, code, "Bob")
    assert api.post(
        f"/games/{code}/start", json={"duration_min": 10}, headers=alice.headers
    ).is_success
    live = Live(code, alice)
    live.next_state()
    assert api.request("DELETE", f"/games/{code}/players/me", headers=bob.headers).is_success
    assert live.next_state(lambda s: s["status"] == "ended")["status"] == "ended"
    live.close()
