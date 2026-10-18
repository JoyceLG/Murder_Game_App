import pytest

from src.application._support import digest_secret
from src.application.create_game import CreateGame
from src.application.join_game import JoinGame
from src.domain.errors import (
    CodeSpaceExhausted,
    GameAlreadyStarted,
    GameNotFound,
    TooManyPlayers,
)
from src.domain.models import GameStatus
from tests.builders import make_game
from tests.doubles import FixedCodes, SequenceIds

# --- CreateGame ------------------------------------------------------------------------


def _create(repo, clock, secrets, *codes: str, host_id: str = "host-1") -> CreateGame:
    return CreateGame(
        repo=repo, ids=SequenceIds(host_id), codes=FixedCodes(*codes), clock=clock, secrets=secrets
    )


async def test_create_game_persists_lobby_with_host_as_first_player(repo, clock, secrets):
    game, player_id, _ = await _create(repo, clock, secrets, "ABCD").execute("Alice")

    assert player_id == "host-1"
    assert game.code == "ABCD"
    assert game.status is GameStatus.LOBBY
    assert game.host_id == "host-1"
    assert game.players["host-1"].name == "Alice"
    assert game.players["host-1"].joined_at == clock.now_ms()
    assert game.created_at == clock.now_ms()

    stored = await repo.get("ABCD")
    assert stored is not None
    assert "host-1" in stored.players


async def test_create_game_hands_out_a_secret_and_stores_only_its_digest(repo, clock, secrets):
    game, _, secret = await _create(repo, clock, secrets, "ABCD").execute("Alice")

    assert secret == "secret-1"
    stored = (await repo.get("ABCD")).players["host-1"]
    assert stored.token_hash == digest_secret(secret)
    assert secret not in stored.token_hash


async def test_create_game_retries_on_code_collision(repo, clock, secrets):
    await repo.save(make_game(["x"], code="TAKEN"))
    game, _, _ = await _create(repo, clock, secrets, "TAKEN", "FREE").execute("Alice")
    assert game.code == "FREE"


async def test_create_game_raises_when_no_free_code(repo, clock, secrets):
    await repo.save(make_game(["x"], code="DUP"))
    with pytest.raises(CodeSpaceExhausted):
        await _create(repo, clock, secrets, *(["DUP"] * 10)).execute("Alice")


# --- JoinGame --------------------------------------------------------------------------


def _join(repo, clock, notifier, secrets, player_id: str = "p2") -> JoinGame:
    return JoinGame(
        repo=repo, ids=SequenceIds(player_id), clock=clock, notifier=notifier, secrets=secrets
    )


async def test_join_game_adds_player_and_publishes(repo, clock, notifier, secrets):
    await repo.save(make_game(["host"], code="ABCD", host="host"))

    game, player_id, secret = await _join(repo, clock, notifier, secrets).execute("ABCD", "Bob")

    assert player_id == "p2"
    assert game.players["p2"].name == "Bob"
    assert game.players["p2"].token_hash == digest_secret(secret)
    assert len(notifier.published) == 1
    assert "p2" in (await repo.get("ABCD")).players


async def test_join_unknown_code_raises_game_not_found(repo, clock, notifier, secrets):
    with pytest.raises(GameNotFound):
        await _join(repo, clock, notifier, secrets).execute("NOPE", "Bob")


async def test_join_after_start_raises_already_started(repo, clock, notifier, secrets):
    game = make_game(["host"], code="ABCD", host="host")
    game.status = GameStatus.RUNNING
    await repo.save(game)
    with pytest.raises(GameAlreadyStarted):
        await _join(repo, clock, notifier, secrets).execute("ABCD", "Bob")


async def test_join_when_lobby_full_raises_too_many_players(repo, clock, notifier, secrets):
    game = make_game(["h", "p2"], code="ABCD", host="h")
    game.max_players = 2
    await repo.save(game)
    with pytest.raises(TooManyPlayers):
        await _join(repo, clock, notifier, secrets, "p3").execute("ABCD", "Carol")
