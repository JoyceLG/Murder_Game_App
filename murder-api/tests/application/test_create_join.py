import pytest

from src.application.create_game import CreateGame
from src.application.join_game import JoinGame
from src.domain.errors import DomainError, GameAlreadyStarted, GameNotFound, TooManyPlayers
from src.domain.models import GameStatus
from tests.builders import make_game
from tests.doubles import FixedCodes, SequenceIds

# --- CreateGame ------------------------------------------------------------------------


async def test_create_game_persists_lobby_with_host_as_first_player(repo, clock):
    uc = CreateGame(repo=repo, ids=SequenceIds("host-1"), codes=FixedCodes("ABCD"), clock=clock)
    game, player_id = await uc.execute("Alice")

    assert player_id == "host-1"
    assert game.code == "ABCD"
    assert game.status is GameStatus.LOBBY
    assert game.host_id == "host-1"
    assert game.players["host-1"].name == "Alice"
    assert game.players["host-1"].joined_at == clock.now_ms()

    stored = await repo.get("ABCD")
    assert stored is not None
    assert "host-1" in stored.players


async def test_create_game_retries_on_code_collision(repo, clock):
    await repo.save(make_game(["x"], code="TAKEN"))
    uc = CreateGame(repo=repo, ids=SequenceIds("h"), codes=FixedCodes("TAKEN", "FREE"), clock=clock)
    game, _ = await uc.execute("Alice")
    assert game.code == "FREE"


async def test_create_game_raises_when_no_free_code(repo, clock):
    await repo.save(make_game(["x"], code="DUP"))
    uc = CreateGame(repo=repo, ids=SequenceIds("h"), codes=FixedCodes(*(["DUP"] * 10)), clock=clock)
    with pytest.raises(DomainError):
        await uc.execute("Alice")


# --- JoinGame --------------------------------------------------------------------------


async def test_join_game_adds_player_and_publishes(repo, clock, notifier):
    await repo.save(make_game(["host"], code="ABCD", host="host"))
    uc = JoinGame(repo=repo, ids=SequenceIds("p2"), clock=clock, notifier=notifier)

    game, player_id = await uc.execute("ABCD", "Bob")

    assert player_id == "p2"
    assert game.players["p2"].name == "Bob"
    assert len(notifier.published) == 1
    assert "p2" in (await repo.get("ABCD")).players


async def test_join_unknown_code_raises_game_not_found(repo, clock, notifier):
    uc = JoinGame(repo=repo, ids=SequenceIds("p2"), clock=clock, notifier=notifier)
    with pytest.raises(GameNotFound):
        await uc.execute("NOPE", "Bob")


async def test_join_after_start_raises_already_started(repo, clock, notifier):
    game = make_game(["host"], code="ABCD", host="host")
    game.status = GameStatus.RUNNING
    await repo.save(game)
    uc = JoinGame(repo=repo, ids=SequenceIds("p2"), clock=clock, notifier=notifier)
    with pytest.raises(GameAlreadyStarted):
        await uc.execute("ABCD", "Bob")


async def test_join_when_lobby_full_raises_too_many_players(repo, clock, notifier):
    game = make_game(["h", "p2"], code="ABCD", host="h")
    game.max_players = 2
    await repo.save(game)
    uc = JoinGame(repo=repo, ids=SequenceIds("p3"), clock=clock, notifier=notifier)
    with pytest.raises(TooManyPlayers):
        await uc.execute("ABCD", "Carol")
