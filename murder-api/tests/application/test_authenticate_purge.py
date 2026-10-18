import pytest

from src.application._support import digest_secret
from src.application.authenticate_player import AuthenticatePlayer
from src.application.purge_stale_games import PurgeStaleGames
from src.domain.errors import GameNotFound, NotAuthenticated
from tests.builders import make_game

# --- AuthenticatePlayer ----------------------------------------------------------------


async def _game_with_secret(repo, secret: str = "s3cret"):
    game = make_game(["h", "p2"], code="ABCD", host="h")
    game.players["p2"].token_hash = digest_secret(secret)
    await repo.save(game)


async def test_authenticate_accepts_the_matching_secret(repo):
    await _game_with_secret(repo)
    assert await AuthenticatePlayer(repo=repo).execute("ABCD", "p2", "s3cret") == "p2"


async def test_authenticate_rejects_a_wrong_secret(repo):
    await _game_with_secret(repo)
    with pytest.raises(NotAuthenticated):
        await AuthenticatePlayer(repo=repo).execute("ABCD", "p2", "guess")


async def test_authenticate_rejects_a_player_without_secret(repo):
    # The public id alone (what other players can see) is not a credential.
    await _game_with_secret(repo)
    with pytest.raises(NotAuthenticated):
        await AuthenticatePlayer(repo=repo).execute("ABCD", "h", "")


async def test_authenticate_rejects_an_unknown_player(repo):
    await _game_with_secret(repo)
    with pytest.raises(NotAuthenticated):
        await AuthenticatePlayer(repo=repo).execute("ABCD", "ghost", "s3cret")


async def test_authenticate_unknown_game_raises_not_found(repo):
    with pytest.raises(GameNotFound):
        await AuthenticatePlayer(repo=repo).execute("NOPE", "p2", "s3cret")


# --- PurgeStaleGames -------------------------------------------------------------------


async def test_purge_deletes_only_games_older_than_the_ttl_and_disconnects_them(
    repo, clock, notifier
):
    old = make_game(["a"], code="OLD1")
    old.created_at = clock.now_ms() - 25 * 3_600_000
    fresh = make_game(["b"], code="NEW1")
    fresh.created_at = clock.now_ms() - 3_600_000
    await repo.save(old)
    await repo.save(fresh)

    purged = await PurgeStaleGames(
        repo=repo, clock=clock, notifier=notifier, ttl_ms=24 * 3_600_000
    ).execute()

    assert purged == ["OLD1"]
    assert await repo.get("OLD1") is None
    assert await repo.get("NEW1") is not None
    assert notifier.closed == ["OLD1"]
