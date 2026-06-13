import pytest

from src.application.claim_elimination import ClaimElimination
from src.application.confirm_claim import ConfirmClaim
from src.domain.errors import (
    ClaimNotFound,
    GameNotRunning,
    NoTargetAssigned,
    NotTheClaimTarget,
    PlayerNotFound,
)
from src.domain.models import ClaimStatus, GameStatus
from tests.application.conftest import make_running
from tests.builders import make_game

# --- ClaimElimination ------------------------------------------------------------------


async def test_claim_elimination_creates_pending_claim_and_publishes(repo, clock, picker, notifier):
    await repo.save(make_running(clock, picker))  # FirstPicker => h targets p2
    uc = ClaimElimination(repo=repo, clock=clock, notifier=notifier)

    claim = await uc.execute("ABCD", "h")

    assert claim.atk == "h"
    assert claim.target == "p2"
    assert claim.status is ClaimStatus.PENDING
    assert "h" in (await repo.get("ABCD")).claims
    assert len(notifier.published) == 1


async def test_claim_without_target_raises_no_target_assigned(repo, clock, picker, notifier):
    game = make_running(clock, picker)
    game.players["h"].target_id = None
    await repo.save(game)
    uc = ClaimElimination(repo=repo, clock=clock, notifier=notifier)
    with pytest.raises(NoTargetAssigned):
        await uc.execute("ABCD", "h")


async def test_claim_on_non_running_game_raises_game_not_running(repo, clock, notifier):
    await repo.save(make_game(["h", "p2"], code="ABCD", host="h"))  # still in lobby
    uc = ClaimElimination(repo=repo, clock=clock, notifier=notifier)
    with pytest.raises(GameNotRunning):
        await uc.execute("ABCD", "h")


async def test_claim_by_unknown_player_raises_player_not_found(repo, clock, picker, notifier):
    await repo.save(make_running(clock, picker))
    uc = ClaimElimination(repo=repo, clock=clock, notifier=notifier)
    with pytest.raises(PlayerNotFound):
        await uc.execute("ABCD", "ghost")


async def test_claim_overwrites_previous_for_same_attacker(repo, clock, picker, notifier):
    await repo.save(make_running(clock, picker))
    uc = ClaimElimination(repo=repo, clock=clock, notifier=notifier)
    await uc.execute("ABCD", "h")
    clock.advance(5000)
    await uc.execute("ABCD", "h")
    stored = await repo.get("ABCD")
    assert list(stored.claims) == ["h"]
    assert stored.claims["h"].ts == clock.now_ms()


# --- ConfirmClaim (the server-side authority) ------------------------------------------


async def test_confirm_claim_by_target_confirmed_scores_and_reassigns(
    repo, clock, picker, notifier
):
    await repo.save(make_running(clock, picker))
    await ClaimElimination(repo=repo, clock=clock, notifier=notifier).execute("ABCD", "h")
    confirm = ConfirmClaim(repo=repo, clock=clock, picker=picker, notifier=notifier)

    result = await confirm.execute("ABCD", attacker_id="h", confirmer_id="p2", confirmed=True)

    assert result.players["h"].score == 1
    assert result.players["h"].target_id != "p2"  # reassigned away from the eliminated target
    assert "h" not in result.claims
    assert (await repo.get("ABCD")).players["h"].score == 1


async def test_confirm_claim_reaching_score_cap_ends_the_game(repo, clock, picker, notifier):
    game = make_running(clock, picker)  # h targets p2 (FirstPicker)
    game.max_score = 1
    await repo.save(game)
    await ClaimElimination(repo=repo, clock=clock, notifier=notifier).execute("ABCD", "h")
    confirm = ConfirmClaim(repo=repo, clock=clock, picker=picker, notifier=notifier)

    result = await confirm.execute("ABCD", "h", "p2", confirmed=True)

    assert result.players["h"].score == 1
    assert result.status is GameStatus.ENDED  # cap reached -> ended in the same response
    assert (await repo.get("ABCD")).status is GameStatus.ENDED


async def test_confirm_claim_by_target_denied_changes_mission_only(repo, clock, picker, notifier):
    game = make_running(clock, picker)
    old_mission = game.players["h"].mission
    await repo.save(game)
    await ClaimElimination(repo=repo, clock=clock, notifier=notifier).execute("ABCD", "h")
    confirm = ConfirmClaim(repo=repo, clock=clock, picker=picker, notifier=notifier)

    result = await confirm.execute("ABCD", "h", "p2", confirmed=False)

    assert result.players["h"].score == 0
    assert result.players["h"].target_id == "p2"  # target unchanged on refusal
    assert result.players["h"].mission != old_mission
    assert "h" not in result.claims


async def test_confirm_claim_by_non_target_raises_not_the_claim_target(
    repo, clock, picker, notifier
):
    await repo.save(make_running(clock, picker))
    await ClaimElimination(repo=repo, clock=clock, notifier=notifier).execute("ABCD", "h")
    confirm = ConfirmClaim(repo=repo, clock=clock, picker=picker, notifier=notifier)
    with pytest.raises(NotTheClaimTarget):
        await confirm.execute("ABCD", "h", confirmer_id="p3", confirmed=True)


async def test_confirm_claim_missing_claim_raises_claim_not_found(repo, clock, picker, notifier):
    await repo.save(make_running(clock, picker))
    confirm = ConfirmClaim(repo=repo, clock=clock, picker=picker, notifier=notifier)
    with pytest.raises(ClaimNotFound):
        await confirm.execute("ABCD", "h", "p2", confirmed=True)


async def test_confirm_claim_after_time_up_raises_game_not_running(repo, clock, picker, notifier):
    game = make_running(clock, picker)
    await repo.save(game)
    await ClaimElimination(repo=repo, clock=clock, notifier=notifier).execute("ABCD", "h")
    clock.advance(game.end_at - clock.now_ms() + 1)  # game has now expired
    confirm = ConfirmClaim(repo=repo, clock=clock, picker=picker, notifier=notifier)
    with pytest.raises(GameNotRunning):
        await confirm.execute("ABCD", "h", "p2", confirmed=True)
    assert (await repo.get("ABCD")).players["h"].score == 0  # no scoring after the buzzer
